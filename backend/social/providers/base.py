"""The contract every publishing platform implements.

Providers are stateless and never touch the database: the caller hands them
plaintext tokens (decrypted just before the call) and stores what they return.
Every failure is raised as a PlatformError whose message is safe to show a user
and to log -- never a raw response, URL or token.
"""

from __future__ import annotations

import base64
import enum
import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator

import httpx

from core.config import get_settings
from core.log_redaction import redact
from social.model import SocialPlatform

HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
UPLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


class ErrorKind(str, enum.Enum):
    # Worth retrying later: network, 5xx, rate limits.
    TRANSIENT = "transient"
    # The grant is gone (revoked, expired): the user must reconnect.
    AUTH = "auth"
    # A platform quota is used up; retry after ``retry_after``.
    QUOTA = "quota"
    # Retrying cannot help: rejected content, bad options, policy.
    PERMANENT = "permanent"


class NotPublished(Exception):
    """Raised by resolve_checkpoint when the platform confirms nothing was posted,
    so starting the upload over cannot create a duplicate."""


class PlatformError(Exception):
    def __init__(
        self, kind: ErrorKind, code: str, message: str, retry_after: timedelta | None = None
    ) -> None:
        self.kind = kind
        self.code = code[:64]
        self.message = redact(message)[:500]
        self.retry_after = retry_after
        super().__init__(f"{kind.value}:{self.code}: {self.message}")


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    scopes: str | None = None
    # Some platforms identify the user in the token response (TikTok open_id, IG user_id).
    platform_user_id: str | None = None

    def __repr__(self) -> str:  # never print secrets, even in a debugger or traceback
        return f"TokenSet(expires_at={self.expires_at!r}, has_refresh={self.refresh_token is not None})"


@dataclass(frozen=True)
class Profile:
    platform_user_id: str
    handle: str | None
    display_name: str | None
    avatar_url: str | None
    follower_count: int | None


@dataclass(frozen=True)
class ClipFile:
    """A rendered clip downloaded for upload, with its probed properties."""

    path: Path
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    audio_sample_rate: int | None
    container: str
    # Fetches a short-lived URL to this exact file, for platforms that pull.
    presign: Callable[[int], str] | None = None

    def chunks(self, chunk_size: int) -> Iterator[tuple[int, bytes]]:
        """(offset, bytes) pairs covering the file in order."""
        with self.path.open("rb") as handle:
            offset = 0
            while chunk := handle.read(chunk_size):
                yield offset, chunk
                offset += len(chunk)


@dataclass
class PublishRequest:
    caption: str
    options: dict[str, Any]
    clip: ClipFile
    account_handle: str | None = None


@dataclass(frozen=True)
class PublishResult:
    platform_post_id: str
    post_url: str | None


SaveCheckpoint = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class ClipLimits:
    max_duration_seconds: float
    min_duration_seconds: float = 1.0
    max_size_bytes: int = 4 * 1024**3
    containers: tuple[str, ...] = ("mp4", "mov")
    video_codecs: tuple[str, ...] = ("h264", "hevc")
    min_fps: float = 0.0
    max_fps: float = 1000.0
    max_width: int | None = None
    min_side: int = 0
    max_side: int | None = None
    # Width/height must not exceed this, e.g. 1.0 keeps Shorts square or vertical.
    max_aspect: float | None = None

    def problems(self, clip: ClipFile, label: str) -> list[str]:
        found: list[str] = []
        if clip.duration_seconds > self.max_duration_seconds:
            found.append(f"{label} accepts videos up to {self.max_duration_seconds:g} seconds.")
        if clip.duration_seconds < self.min_duration_seconds:
            found.append(f"{label} needs videos of at least {self.min_duration_seconds:g} seconds.")
        if clip.size_bytes > self.max_size_bytes:
            found.append(f"{label} accepts files up to {self.max_size_bytes // 1024**2} MB.")
        if not any(c in clip.container for c in self.containers):
            found.append(f"{label} needs an {'/'.join(self.containers).upper()} file.")
        if clip.video_codec not in self.video_codecs:
            found.append(f"{label} needs {' or '.join(c.upper() for c in self.video_codecs)} video.")
        if not self.min_fps <= clip.fps <= self.max_fps:
            found.append(f"{label} needs {self.min_fps:g}-{self.max_fps:g} frames per second.")
        if self.max_width and clip.width > self.max_width:
            found.append(f"{label} accepts videos up to {self.max_width}px wide.")
        if min(clip.width, clip.height) < self.min_side:
            found.append(f"{label} needs at least {self.min_side}px on each side.")
        if self.max_side and max(clip.width, clip.height) > self.max_side:
            found.append(f"{label} accepts at most {self.max_side}px on each side.")
        if self.max_aspect and clip.height and clip.width / clip.height > self.max_aspect:
            found.append(f"{label} needs a vertical or square video.")
        return found


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> "PkcePair":
        verifier = secrets.token_urlsafe(64)[:96]
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return cls(verifier=verifier, challenge=challenge)


class PlatformProvider(ABC):
    platform: SocialPlatform
    label: str
    scopes: tuple[str, ...]
    uses_pkce: bool = False
    limits: ClipLimits
    caption_max_chars: int = 2200
    # Refresh this long before the access token expires.
    refresh_margin: timedelta = timedelta(minutes=10)
    # A note shown to users while the app is waiting on platform review.
    pending_review_note: str | None = None

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    # -- configuration -----------------------------------------------------

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the client id and secret are set."""

    def redirect_uri(self) -> str:
        """Exact, fixed callback URL. Never built from request input."""
        return f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/dashboard/connect/{self.platform.value}"

    # -- OAuth -------------------------------------------------------------

    @abstractmethod
    def authorize_url(self, state: str, code_challenge: str | None) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet: ...

    @abstractmethod
    async def refresh(self, tokens: TokenSet) -> TokenSet:
        """New tokens. Raises PlatformError(AUTH) when the grant is gone."""

    @abstractmethod
    async def revoke(self, tokens: TokenSet) -> None:
        """Best effort; platforms without a revoke endpoint do nothing."""

    @abstractmethod
    async def fetch_profile(self, tokens: TokenSet) -> Profile: ...

    def refresh_due(self, tokens_expires_at: datetime | None, now: datetime) -> bool:
        return tokens_expires_at is not None and tokens_expires_at - self.refresh_margin <= now

    # -- publishing ----------------------------------------------------------

    def validate(self, clip: ClipFile, caption: str, options: dict[str, Any]) -> list[str]:
        """Human-readable reasons this clip cannot be published here (empty when fine)."""
        problems = self.limits.problems(clip, self.label)
        if len(caption) > self.caption_max_chars:
            problems.append(f"{self.label} captions can be at most {self.caption_max_chars} characters.")
        return problems + self.validate_options(options)

    def validate_options(self, options: dict[str, Any]) -> list[str]:
        return []

    def precheck(self, duration_seconds: float, caption: str, options: dict[str, Any]) -> list[str]:
        """What can be checked when a post is created, before the file is fetched.
        The worker runs the full ``validate`` against the probed file."""
        problems: list[str] = []
        if duration_seconds > self.limits.max_duration_seconds:
            problems.append(f"{self.label} accepts videos up to {self.limits.max_duration_seconds:g} seconds.")
        if duration_seconds < self.limits.min_duration_seconds:
            problems.append(f"{self.label} needs videos of at least {self.limits.min_duration_seconds:g} seconds.")
        if len(caption) > self.caption_max_chars:
            problems.append(f"{self.label} captions can be at most {self.caption_max_chars} characters.")
        return problems + self.validate_options(options)

    @abstractmethod
    async def publish(
        self, tokens: TokenSet, request: PublishRequest, save_checkpoint: SaveCheckpoint
    ) -> PublishResult:
        """Upload and publish. Calls ``save_checkpoint`` with the platform's id for the
        in-flight upload before the step that makes the post public."""

    async def resolve_checkpoint(
        self, tokens: TokenSet, checkpoint: str, account_handle: str | None
    ) -> PublishResult | None:
        """After an interrupted run: the finished post for this checkpoint, None when
        the outcome cannot be confirmed, NotPublished when it certainly was not
        posted, or PlatformError (TRANSIENT while still processing). Never publishes."""
        return None

    # -- HTTP ----------------------------------------------------------------

    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "PlatformProvider":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One HTTP call with failures mapped to PlatformError. Returns 2xx responses only."""
        try:
            response = await self.client().request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise PlatformError(ErrorKind.TRANSIENT, "timeout", f"{self.label} did not respond in time.") from exc
        except httpx.HTTPError as exc:
            raise PlatformError(
                ErrorKind.TRANSIENT, "network_error", f"Could not reach {self.label}."
            ) from exc
        if response.is_success:
            return response
        raise self.map_error(response)

    def map_error(self, response: httpx.Response) -> PlatformError:
        """Classify a non-2xx response. Providers override to read platform error codes."""
        return default_error(self.label, response)


def default_error(label: str, response: httpx.Response, code: str | None = None, detail: str | None = None) -> PlatformError:
    status = response.status_code
    code = code or f"http_{status}"
    detail = detail or f"{label} returned an error ({status})."
    if status == 429:
        return PlatformError(ErrorKind.QUOTA, code, f"{label} rate limit reached; will retry.", retry_after_of(response))
    if status >= 500:
        return PlatformError(ErrorKind.TRANSIENT, code, f"{label} is having problems; will retry.")
    if status == 401:
        return PlatformError(ErrorKind.AUTH, code, f"{label} access has expired or was revoked. Reconnect the account.")
    return PlatformError(ErrorKind.PERMANENT, code, detail)


def retry_after_of(response: httpx.Response) -> timedelta | None:
    value = response.headers.get("retry-after")
    if value and value.isdigit():
        return timedelta(seconds=int(value))
    reset = response.headers.get("x-rate-limit-reset")
    if reset and reset.isdigit():
        seconds = int(reset) - int(datetime.utcnow().timestamp())
        return timedelta(seconds=max(seconds, 60))
    return None


def json_of(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def expires_in(seconds: Any) -> datetime | None:
    try:
        return datetime.utcnow() + timedelta(seconds=int(seconds))
    except (TypeError, ValueError):
        return None

