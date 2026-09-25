"""TikTok via the Content Posting API (Direct Post).

Scopes: ``user.info.basic`` (id, name, avatar), ``user.info.profile``
(username), ``user.info.stats`` (follower count), ``video.publish`` (post).

Uploads use FILE_UPLOAD: PULL_FROM_URL requires a verified domain, and S3
presigned URLs cannot be verified. Until the app passes TikTok's audit, posts
are forced to SELF_ONLY, only private accounts can post, and at most five
users a day.

TikTok's UX rules require the post form to show the creator's nickname and
their current privacy options (with no preselected default), interaction
toggles and a commercial-content disclosure; creator_info() feeds that form
and publish() re-checks it at post time.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from core.config import get_settings
from social.model import SocialPlatform
from social.providers.base import (
    UPLOAD_TIMEOUT,
    ClipFile,
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

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API}/oauth/token/"
REVOKE_URL = f"{API}/oauth/revoke/"
USER_INFO_URL = f"{API}/user/info/"
CREATOR_INFO_URL = f"{API}/post/publish/creator_info/query/"
INIT_URL = f"{API}/post/publish/video/init/"
STATUS_URL = f"{API}/post/publish/status/fetch/"

MIN_CHUNK = 5 * 1024**2
CHUNK = 10 * 1024**2
STATUS_POLL_SECONDS = 5
STATUS_POLL_ATTEMPTS = 60

PRIVACY_LEVELS = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")

_PERMANENT_CODES = {
    "spam_risk_too_many_posts": "TikTok's daily post limit for this account has been reached.",
    "spam_risk_user_banned_from_posting": "TikTok has blocked this account from posting.",
    "reached_active_user_cap": "Clipnera has reached TikTok's daily limit of posting users. Try again tomorrow.",
    "unaudited_client_can_only_post_to_private_accounts": (
        "Until TikTok approves Clipnera, only private TikTok accounts can post. Set the account to private or wait."
    ),
    "privacy_level_option_mismatch": "The chosen TikTok privacy option is no longer available for this account.",
    "url_ownership_unverified": "TikTok could not verify the video source.",
}
_AUTH_CODES = {"access_token_invalid", "scope_not_authorized", "invalid_grant"}


def chunk_plan(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunk_count) per TikTok's rules: files under 5 MB go whole,
    otherwise 10 MB chunks with the remainder folded into the last one."""
    if size < MIN_CHUNK:
        return size, 1
    return CHUNK, max(1, size // CHUNK)


def chunk_ranges(size: int) -> list[tuple[int, int]]:
    """Inclusive (first, last) byte ranges matching chunk_plan."""
    chunk_size, count = chunk_plan(size)
    ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(count)]
    first, _ = ranges[-1]
    ranges[-1] = (first, size - 1)
    return ranges


class TikTokProvider(PlatformProvider):
    platform = SocialPlatform.TIKTOK
    label = "TikTok"
    scopes = ("user.info.basic", "user.info.profile", "user.info.stats", "video.publish")
    caption_max_chars = 2200
    refresh_margin = timedelta(hours=1)
    limits = ClipLimits(
        max_duration_seconds=600,
        min_duration_seconds=3,
        max_size_bytes=4 * 1024**3,
        containers=("mp4", "mov", "webm"),
        video_codecs=("h264", "hevc", "vp8", "vp9"),
        min_fps=23,
        max_fps=60,
        min_side=360,
        max_side=4096,
    )
    pending_review_note = (
        "Until TikTok approves Clipnera, posts are visible only to you and the TikTok account must be private."
    )

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET)

    # -- OAuth -------------------------------------------------------------

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_key": get_settings().TIKTOK_CLIENT_KEY,
            "scope": ",".join(self.scopes),
            "response_type": "code",
            "redirect_uri": self.redirect_uri(),
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet:
        response = await self.request(
            "POST",
            TOKEN_URL,
            data={
                **self._client_credentials(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri(),
            },
        )
        tokens = self._tokens(json_of(response))
        granted = set((tokens.scopes or "").split(","))
        if not set(self.scopes) <= granted:
            raise PlatformError(
                ErrorKind.PERMANENT,
                "scopes_missing",
                "Please allow every requested TikTok permission so Clipnera can post and show your profile.",
            )
        return tokens

    async def refresh(self, tokens: TokenSet) -> TokenSet:
        if not tokens.refresh_token:
            raise PlatformError(ErrorKind.AUTH, "no_refresh_token", "TikTok access expired. Reconnect the account.")
        response = await self.request(
            "POST",
            TOKEN_URL,
            data={
                **self._client_credentials(),
                "grant_type": "refresh_token",
                "refresh_token": tokens.refresh_token,
            },
        )
        # TikTok may rotate the refresh token; the new one must replace the old.
        return self._tokens(json_of(response))

    async def revoke(self, tokens: TokenSet) -> None:
        await self.request("POST", REVOKE_URL, data={**self._client_credentials(), "token": tokens.access_token})

    async def fetch_profile(self, tokens: TokenSet) -> Profile:
        response = await self.request(
            "GET",
            USER_INFO_URL,
            params={"fields": "open_id,avatar_url,display_name,username,follower_count"},
            headers=self._auth(tokens),
        )
        user = (json_of(response).get("data") or {}).get("user") or {}
        if not user.get("open_id"):
            raise PlatformError(ErrorKind.TRANSIENT, "no_profile", "TikTok did not return the profile.")
        username = user.get("username")
        return Profile(
            platform_user_id=user["open_id"],
            handle=f"@{username}" if username else None,
            display_name=user.get("display_name"),
            avatar_url=user.get("avatar_url"),
            follower_count=user.get("follower_count"),
        )

    async def creator_info(self, tokens: TokenSet) -> dict[str, Any]:
        """The creator's current posting options, for the post form and the pre-post check."""
        response = await self.request(
            "POST", CREATOR_INFO_URL, headers={**self._auth(tokens), "Content-Type": "application/json"}, json={}
        )
        data = json_of(response).get("data") or {}
        return {
            "nickname": data.get("creator_nickname"),
            "username": data.get("creator_username"),
            "avatar_url": data.get("creator_avatar_url"),
            "privacy_level_options": data.get("privacy_level_options") or [],
            "comment_disabled": bool(data.get("comment_disabled")),
            "duet_disabled": bool(data.get("duet_disabled")),
            "stitch_disabled": bool(data.get("stitch_disabled")),
            "max_video_post_duration_sec": data.get("max_video_post_duration_sec"),
        }

    # -- publishing ----------------------------------------------------------

    def validate_options(self, options: dict[str, Any]) -> list[str]:
        problems: list[str] = []
        if options.get("privacy_level") not in PRIVACY_LEVELS:
            problems.append("Choose who can view the TikTok post.")
        for toggle in ("disable_comment", "disable_duet", "disable_stitch", "brand_content_toggle", "brand_organic_toggle"):
            if not isinstance(options.get(toggle), bool):
                problems.append("Set every TikTok interaction and disclosure option.")
                break
        if options.get("brand_content_toggle") and options.get("privacy_level") == "SELF_ONLY":
            problems.append("Branded content on TikTok cannot be private (Only me).")
        return problems

    async def publish(
        self, tokens: TokenSet, request: PublishRequest, save_checkpoint: SaveCheckpoint
    ) -> PublishResult:
        options = request.options
        clip = request.clip
        await self._check_creator(tokens, options, clip)

        chunk_size, chunk_count = chunk_plan(clip.size_bytes)
        response = await self.request(
            "POST",
            INIT_URL,
            headers={**self._auth(tokens), "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": request.caption,
                    "privacy_level": options["privacy_level"],
                    "disable_comment": options["disable_comment"],
                    "disable_duet": options["disable_duet"],
                    "disable_stitch": options["disable_stitch"],
                    "brand_content_toggle": options["brand_content_toggle"],
                    "brand_organic_toggle": options["brand_organic_toggle"],
                    "is_aigc": bool(options.get("is_aigc", False)),
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": clip.size_bytes,
                    "chunk_size": chunk_size,
                    "total_chunk_count": chunk_count,
                },
            },
        )
        data = json_of(response).get("data") or {}
        publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
        if not publish_id or not upload_url:
            raise PlatformError(ErrorKind.TRANSIENT, "no_upload_url", "TikTok did not start the upload.")
        # Once the upload completes TikTok posts on its own, so checkpoint first.
        await save_checkpoint(publish_id)
        await self._upload(upload_url, clip)
        return await self._await_publish(tokens, publish_id, request.account_handle)

    async def resolve_checkpoint(
        self, tokens: TokenSet, checkpoint: str, account_handle: str | None
    ) -> PublishResult | None:
        status, result = await self._status(tokens, checkpoint, account_handle)
        if result:
            return result
        if status == "PROCESSING_UPLOAD":
            # The upload never finished and its URL has expired: nothing was posted.
            raise NotPublished()
        raise PlatformError(
            ErrorKind.TRANSIENT, "still_processing", "TikTok is still processing the video; checking again shortly."
        )

    async def _check_creator(self, tokens: TokenSet, options: dict[str, Any], clip: ClipFile) -> None:
        info = await self.creator_info(tokens)
        if options["privacy_level"] not in info["privacy_level_options"]:
            raise PlatformError(ErrorKind.PERMANENT, "privacy_level_option_mismatch", _PERMANENT_CODES["privacy_level_option_mismatch"])
        max_duration = info.get("max_video_post_duration_sec")
        if max_duration and clip.duration_seconds > max_duration:
            raise PlatformError(
                ErrorKind.PERMANENT, "too_long", f"This TikTok account can post videos up to {max_duration} seconds."
            )

    async def _upload(self, upload_url: str, clip: ClipFile) -> None:
        with clip.path.open("rb") as handle:
            for first, last in chunk_ranges(clip.size_bytes):
                handle.seek(first)
                body = handle.read(last - first + 1)
                try:
                    response = await self.client().put(
                        upload_url,
                        content=body,
                        headers={
                            "Content-Type": "video/mp4",
                            "Content-Range": f"bytes {first}-{last}/{clip.size_bytes}",
                        },
                        timeout=UPLOAD_TIMEOUT,
                    )
                except httpx.HTTPError as exc:
                    raise PlatformError(ErrorKind.TRANSIENT, "network_error", "Could not reach TikTok.") from exc
                if response.status_code not in (200, 201, 206):
                    raise default_error(self.label, response, code=f"upload_{response.status_code}")

    async def _await_publish(self, tokens: TokenSet, publish_id: str, handle: str | None) -> PublishResult:
        for _ in range(STATUS_POLL_ATTEMPTS):
            _, result = await self._status(tokens, publish_id, handle)
            if result:
                return result
            await asyncio.sleep(STATUS_POLL_SECONDS)
        raise PlatformError(
            ErrorKind.TRANSIENT, "still_processing", "TikTok is still processing the video; checking again shortly."
        )

    async def _status(
        self, tokens: TokenSet, publish_id: str, handle: str | None
    ) -> tuple[str | None, PublishResult | None]:
        """One status check: (status, result once published). Raises when TikTok rejected it."""
        response = await self.request(
            "POST",
            STATUS_URL,
            headers={**self._auth(tokens), "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
        )
        data = json_of(response).get("data") or {}
        status = data.get("status")
        if status == "FAILED":
            reason = data.get("fail_reason") or "unknown"
            raise PlatformError(ErrorKind.PERMANENT, f"publish_{reason}", f"TikTok rejected the video ({reason}).")
        if status != "PUBLISH_COMPLETE":
            return status, None
        # TikTok's field name is misspelled in the API itself.
        public_ids = data.get("publicaly_available_post_id") or []
        if not public_ids:
            # Private (Only me) posts have no public id or URL.
            return status, PublishResult(platform_post_id=publish_id, post_url=None)
        post_id = str(public_ids[0])
        url = f"https://www.tiktok.com/{handle}/video/{post_id}" if handle else None
        return status, PublishResult(platform_post_id=post_id, post_url=url)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _client_credentials() -> dict[str, str]:
        settings = get_settings()
        return {"client_key": settings.TIKTOK_CLIENT_KEY, "client_secret": settings.TIKTOK_CLIENT_SECRET}

    @staticmethod
    def _auth(tokens: TokenSet) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    @staticmethod
    def _tokens(body: dict[str, Any]) -> TokenSet:
        if not body.get("access_token"):
            raise PlatformError(ErrorKind.AUTH, str(body.get("error") or "bad_token_response"), "TikTok did not issue a token.")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=expires_in(body.get("expires_in")),
            refresh_expires_at=expires_in(body.get("refresh_expires_in")),
            scopes=body.get("scope"),
            platform_user_id=body.get("open_id"),
        )

    def map_error(self, response: httpx.Response) -> PlatformError:
        body = json_of(response)
        error = body.get("error")
        if isinstance(error, str):  # OAuth endpoints
            if error in _AUTH_CODES:
                return PlatformError(ErrorKind.AUTH, error, "TikTok access was revoked or expired. Reconnect the account.")
            return default_error(self.label, response, code=error)
        code = (error or {}).get("code") if isinstance(error, dict) else None
        if code in _AUTH_CODES:
            return PlatformError(ErrorKind.AUTH, code, "TikTok access was revoked or expired. Reconnect the account.")
        if code in _PERMANENT_CODES:
            return PlatformError(ErrorKind.PERMANENT, code, _PERMANENT_CODES[code])
        if code == "rate_limit_exceeded":
            return PlatformError(ErrorKind.TRANSIENT, code, "TikTok asked us to slow down; will retry.", timedelta(minutes=1))
        message = str((error or {}).get("message") or "")[:200] if isinstance(error, dict) else ""
        return default_error(self.label, response, code=code, detail=f"TikTok rejected the request: {message}".strip())
