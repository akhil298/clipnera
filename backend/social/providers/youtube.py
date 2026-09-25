"""YouTube Shorts via the YouTube Data API v3.

Scopes: ``youtube.upload`` to post, ``youtube.readonly`` for the channel's
handle and subscriber count (``channels.list?mine=true`` needs it; no narrower
scope covers it).

Until the API project passes YouTube's compliance audit, every upload is
forced private, and the project shares 100 ``videos.insert`` calls a day
across all users (see social/quota.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from core.config import get_settings
from social.model import SocialPlatform
from social.providers.base import (
    UPLOAD_TIMEOUT,
    ClipLimits,
    ErrorKind,
    NotPublished,
    PlatformError,
    PlatformProvider,
    Profile,
    PublishRequest,
    PublishResult,
    SaveCheckpoint,
    TokenSet,
    default_error,
    expires_in,
    json_of,
)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"

# Resumable chunks must be multiples of 256 KiB.
CHUNK_BYTES = 32 * 256 * 1024
PACIFIC = ZoneInfo("America/Los_Angeles")
PRIVACY_OPTIONS = ("public", "unlisted", "private")
TITLE_MAX = 100

_QUOTA_REASONS = {"quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded"}
_RATE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded"}
_AUTH_REASONS = {"authError", "insufficientPermissions", "forbidden"}


def until_pacific_midnight(now: datetime | None = None) -> timedelta:
    """Time until YouTube's daily quota resets (midnight Pacific)."""
    current = (now or datetime.utcnow()).replace(tzinfo=ZoneInfo("UTC")).astimezone(PACIFIC)
    tomorrow = (current + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return tomorrow - current


class YouTubeProvider(PlatformProvider):
    platform = SocialPlatform.YOUTUBE
    label = "YouTube"
    scopes = (SCOPE_UPLOAD, SCOPE_READONLY)
    uses_pkce = True
    caption_max_chars = 5000
    # Square or vertical and at most three minutes, or YouTube files it as a long video.
    limits = ClipLimits(
        max_duration_seconds=180,
        video_codecs=("h264", "hevc", "vp9", "av1"),
        max_aspect=1.0,
        max_size_bytes=10 * 1024**3,
    )
    pending_review_note = (
        "Until Clipnera passes YouTube's API audit, uploads are private and a daily upload cap applies."
    )

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.YOUTUBE_CLIENT_ID and settings.YOUTUBE_CLIENT_SECRET)

    # -- OAuth -------------------------------------------------------------

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_id": get_settings().YOUTUBE_CLIENT_ID,
            "redirect_uri": self.redirect_uri(),
            "response_type": "code",
            "scope": " ".join(self.scopes),
            # offline + consent: Google only returns a refresh token on explicit consent.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "false",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet:
        settings = get_settings()
        response = await self.request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri(),
            },
        )
        tokens = self._tokens(json_of(response))
        granted = set((tokens.scopes or "").split())
        if not set(self.scopes) <= granted:
            raise PlatformError(
                ErrorKind.PERMANENT,
                "scopes_missing",
                "Please allow every requested YouTube permission so Clipnera can upload and show your channel.",
            )
        if not tokens.refresh_token:
            raise PlatformError(
                ErrorKind.PERMANENT, "no_refresh_token", "Google did not grant offline access. Please try again."
            )
        return tokens

    async def refresh(self, tokens: TokenSet) -> TokenSet:
        if not tokens.refresh_token:
            raise PlatformError(ErrorKind.AUTH, "no_refresh_token", "YouTube access expired. Reconnect the account.")
        settings = get_settings()
        response = await self.request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "refresh_token": tokens.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        refreshed = self._tokens(json_of(response))
        # Google keeps the same refresh token unless it sends a new one.
        refreshed.refresh_token = refreshed.refresh_token or tokens.refresh_token
        return refreshed

    async def revoke(self, tokens: TokenSet) -> None:
        # Revoking the refresh token also invalidates every access token from it.
        await self.request("POST", REVOKE_URL, data={"token": tokens.refresh_token or tokens.access_token})

    async def fetch_profile(self, tokens: TokenSet) -> Profile:
        response = await self.request(
            "GET",
            CHANNELS_URL,
            params={"part": "snippet,statistics", "mine": "true"},
            headers=self._auth(tokens),
        )
        items = json_of(response).get("items") or []
        if not items:
            raise PlatformError(
                ErrorKind.PERMANENT,
                "no_channel",
                "This Google account has no YouTube channel. Create one on YouTube, then connect again.",
            )
        channel = items[0]
        snippet = channel.get("snippet") or {}
        stats = channel.get("statistics") or {}
        subscribers = None if stats.get("hiddenSubscriberCount") else _int(stats.get("subscriberCount"))
        thumbnails = snippet.get("thumbnails") or {}
        avatar = (thumbnails.get("default") or thumbnails.get("medium") or {}).get("url")
        return Profile(
            platform_user_id=channel["id"],
            handle=snippet.get("customUrl"),
            display_name=snippet.get("title"),
            avatar_url=avatar,
            follower_count=subscribers,
        )

    # -- publishing ----------------------------------------------------------

    def validate_options(self, options: dict[str, Any]) -> list[str]:
        problems: list[str] = []
        title = str(options.get("title") or "").strip()
        if not title:
            problems.append("YouTube needs a title.")
        elif len(title) > TITLE_MAX or "<" in title or ">" in title:
            problems.append(f"YouTube titles must be at most {TITLE_MAX} characters, without < or >.")
        if options.get("privacy_status") not in PRIVACY_OPTIONS:
            problems.append("Choose whether the YouTube video is public, unlisted or private.")
        if not isinstance(options.get("made_for_kids"), bool):
            problems.append("Say whether the YouTube video is made for kids (YouTube requires this).")
        return problems

    async def publish(
        self, tokens: TokenSet, request: PublishRequest, save_checkpoint: SaveCheckpoint
    ) -> PublishResult:
        options = request.options
        clip = request.clip
        metadata = {
            "snippet": {
                "title": str(options["title"]).strip()[:TITLE_MAX],
                "description": request.caption,
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": options["privacy_status"],
                "selfDeclaredMadeForKids": options["made_for_kids"],
            },
        }
        started = await self.request(
            "POST",
            UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                **self._auth(tokens),
                "X-Upload-Content-Length": str(clip.size_bytes),
                "X-Upload-Content-Type": "video/mp4",
            },
            json=metadata,
        )
        session_uri = started.headers.get("location")
        if not session_uri:
            raise PlatformError(ErrorKind.TRANSIENT, "no_upload_session", "YouTube did not start the upload.")
        # The upload completing is what creates the video, so the session is the checkpoint.
        await save_checkpoint(f"{clip.size_bytes} {session_uri}")

        video: dict[str, Any] = {}
        for offset, chunk in clip.chunks(CHUNK_BYTES):
            end = offset + len(chunk) - 1
            response = await self._put_chunk(
                session_uri, tokens, chunk, f"bytes {offset}-{end}/{clip.size_bytes}"
            )
            if response.status_code in (200, 201):
                video = json_of(response)
        if not video.get("id"):
            raise PlatformError(ErrorKind.TRANSIENT, "upload_incomplete", "The YouTube upload did not finish.")
        return self._result(video["id"])

    async def resolve_checkpoint(
        self, tokens: TokenSet, checkpoint: str, account_handle: str | None
    ) -> PublishResult | None:
        """Ask the upload session how far it got. The video only exists once the
        session is complete, so an unfinished session means nothing was posted."""
        size, _, session_uri = checkpoint.partition(" ")
        try:
            response = await self._put_chunk(session_uri, tokens, b"", f"bytes */{size}")
        except PlatformError as exc:
            # An expired or unknown session never became a video.
            if exc.code in ("http_404", "http_410"):
                raise NotPublished() from exc
            raise
        if response.status_code == 308:
            raise NotPublished()
        video = json_of(response)
        return self._result(video["id"]) if video.get("id") else None

    async def _put_chunk(
        self, session_uri: str, tokens: TokenSet, chunk: bytes, content_range: str
    ) -> httpx.Response:
        try:
            response = await self.client().put(
                session_uri,
                content=chunk,
                headers={**self._auth(tokens), "Content-Range": content_range},
                timeout=UPLOAD_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise PlatformError(ErrorKind.TRANSIENT, "network_error", "Could not reach YouTube.") from exc
        # 308 means "keep going"; httpx treats it as a redirect, not a success.
        if response.status_code == 308 or response.is_success:
            return response
        raise self.map_error(response)

    @staticmethod
    def _result(video_id: str) -> PublishResult:
        return PublishResult(platform_post_id=video_id, post_url=f"https://www.youtube.com/shorts/{video_id}")

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _auth(tokens: TokenSet) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    @staticmethod
    def _tokens(body: dict[str, Any]) -> TokenSet:
        if not body.get("access_token"):
            raise PlatformError(ErrorKind.TRANSIENT, "bad_token_response", "Google returned no access token.")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=expires_in(body.get("expires_in")),
            scopes=body.get("scope"),
        )

    def map_error(self, response: httpx.Response) -> PlatformError:
        body = json_of(response)
        error = body.get("error")
        # OAuth endpoints: {"error": "invalid_grant", "error_description": ...}
        if isinstance(error, str):
            if error == "invalid_grant":
                return PlatformError(
                    ErrorKind.AUTH, error, "YouTube access was revoked or expired. Reconnect the account."
                )
            if error in ("invalid_client", "unauthorized_client"):
                return PlatformError(ErrorKind.PERMANENT, error, "Clipnera's YouTube app is misconfigured.")
            return default_error(self.label, response, code=error)
        # Data API: {"error": {"code": 403, "errors": [{"reason": ...}], "message": ...}}
        details = error if isinstance(error, dict) else {}
        reasons = {item.get("reason") for item in details.get("errors") or [] if isinstance(item, dict)}
        reason = next(iter(reasons), None) or f"http_{response.status_code}"
        if reasons & _QUOTA_REASONS:
            return PlatformError(
                ErrorKind.QUOTA,
                reason,
                "YouTube's daily upload limit for Clipnera is used up. The post will go out after it resets.",
                until_pacific_midnight(),
            )
        if reasons & _RATE_REASONS:
            return PlatformError(ErrorKind.TRANSIENT, reason, "YouTube asked us to slow down; will retry.")
        if response.status_code == 401 or reasons & _AUTH_REASONS:
            return PlatformError(
                ErrorKind.AUTH, reason, "YouTube access is missing a permission or was revoked. Reconnect the account."
            )
        if "youtubeSignupRequired" in reasons:
            return PlatformError(ErrorKind.PERMANENT, reason, "Create a YouTube channel for this account first.")
        message = str(details.get("message") or "")[:200]
        return default_error(self.label, response, code=reason, detail=f"YouTube rejected the video: {message}".strip())


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
