"""Instagram Reels via the Instagram API with Instagram Login.

Scopes: ``instagram_business_basic`` (username, picture, followers) and
``instagram_business_content_publish`` (post). Only professional (Business or
Creator) accounts can connect.

There is no refresh token: the 60-day long-lived token is itself refreshed
(once it is at least a day old), so the worker renews it well before expiry.
Meta pulls the video from a URL; it gets a presigned S3 URL to that one file,
valid for 15 minutes. Resumable upload is only offered with Facebook Login.
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

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
API = f"{GRAPH}/v26.0"

# Meta downloads the video while the container processes; 15 minutes is ample.
VIDEO_URL_TTL_SECONDS = 15 * 60
STATUS_POLL_SECONDS = 5
STATUS_POLL_ATTEMPTS = 60
PROFESSIONAL_ACCOUNT_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}

_AUTH_CODES = {190, 102, 10, 200}
_RATE_CODES = {4, 17, 32, 613}
# error_subcode for "account has reached its 24-hour publishing limit".
_PUBLISH_LIMIT_SUBCODE = 2207042


class InstagramProvider(PlatformProvider):
    platform = SocialPlatform.INSTAGRAM
    label = "Instagram"
    scopes = ("instagram_business_basic", "instagram_business_content_publish")
    caption_max_chars = 2200
    # Long-lived tokens last 60 days; renew with plenty of slack.
    refresh_margin = timedelta(days=10)
    limits = ClipLimits(
        max_duration_seconds=900,
        min_duration_seconds=3,
        max_size_bytes=300 * 1024**2,
        containers=("mp4", "mov"),
        video_codecs=("h264", "hevc"),
        min_fps=23,
        max_fps=60,
        max_width=1920,
    )
    pending_review_note = "Until Meta approves Clipnera, only Instagram accounts added as app testers can connect."

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET)

    # -- OAuth -------------------------------------------------------------

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_id": get_settings().INSTAGRAM_APP_ID,
            "redirect_uri": self.redirect_uri(),
            "response_type": "code",
            "scope": ",".join(self.scopes),
            "state": state,
            "enable_fb_login": "0",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet:
        settings = get_settings()
        # Instagram appends "#_" to the code in the redirect.
        code = code.removesuffix("#_")
        response = await self.request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": settings.INSTAGRAM_APP_ID,
                "client_secret": settings.INSTAGRAM_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri(),
                "code": code,
            },
        )
        body = json_of(response)
        data = body.get("data")
        short = data[0] if isinstance(data, list) and data else body
        if not short.get("access_token"):
            raise PlatformError(ErrorKind.TRANSIENT, "bad_token_response", "Instagram did not issue a token.")
        permissions = short.get("permissions")
        granted = set(permissions.split(",") if isinstance(permissions, str) else permissions or [])
        if granted and not set(self.scopes) <= granted:
            raise PlatformError(
                ErrorKind.PERMANENT,
                "scopes_missing",
                "Please allow every requested Instagram permission so Clipnera can post and show your profile.",
            )
        # Swap the one-hour token for a 60-day one straight away.
        long_lived = await self.request(
            "GET",
            f"{GRAPH}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": settings.INSTAGRAM_APP_SECRET,
                "access_token": short["access_token"],
            },
        )
        tokens = self._tokens(json_of(long_lived))
        tokens.scopes = ",".join(sorted(granted)) or ",".join(self.scopes)
        return tokens

    async def refresh(self, tokens: TokenSet) -> TokenSet:
        response = await self.request(
            "GET",
            f"{GRAPH}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": tokens.access_token},
        )
        refreshed = self._tokens(json_of(response))
        refreshed.scopes = tokens.scopes
        return refreshed

    async def revoke(self, tokens: TokenSet) -> None:
        # Instagram Login has no revoke endpoint; users remove the app in Instagram settings.
        return None

    async def fetch_profile(self, tokens: TokenSet) -> Profile:
        response = await self.request(
            "GET",
            f"{API}/me",
            params={"fields": "id,user_id,username,name,profile_picture_url,followers_count,account_type"},
            headers=self._auth(tokens),
        )
        me = json_of(response)
        account_type = str(me.get("account_type") or "").upper()
        if account_type and account_type not in PROFESSIONAL_ACCOUNT_TYPES:
            raise PlatformError(
                ErrorKind.PERMANENT,
                "not_professional",
                "Only Instagram Business or Creator accounts can publish. Switch the account type in Instagram.",
            )
        if not me.get("id"):
            raise PlatformError(ErrorKind.TRANSIENT, "no_profile", "Instagram did not return the profile.")
        username = me.get("username")
        return Profile(
            platform_user_id=str(me["id"]),
            handle=f"@{username}" if username else None,
            display_name=me.get("name") or username,
            avatar_url=me.get("profile_picture_url"),
            follower_count=me.get("followers_count"),
        )

    # -- publishing ----------------------------------------------------------

    def validate(self, clip: ClipFile, caption: str, options: dict[str, Any]) -> list[str]:
        problems = super().validate(clip, caption, options)
        if clip.audio_codec and clip.audio_codec != "aac":
            problems.append("Instagram needs AAC audio.")
        if clip.audio_sample_rate and clip.audio_sample_rate > 48000:
            problems.append("Instagram accepts audio up to 48 kHz.")
        if caption.count("#") > 30:
            problems.append("Instagram captions can have at most 30 hashtags.")
        offset = options.get("thumb_offset")
        if isinstance(offset, int) and offset > clip.duration_seconds * 1000:
            problems.append("The Reels cover frame is past the end of the video.")
        return problems

    def validate_options(self, options: dict[str, Any]) -> list[str]:
        problems: list[str] = []
        if "share_to_feed" in options and not isinstance(options["share_to_feed"], bool):
            problems.append("Choose whether the reel also appears in the Instagram feed.")
        if "thumb_offset" in options:
            offset = options["thumb_offset"]
            # bool is an int subclass; a checkbox value is never a frame position.
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                problems.append("The Reels cover frame must be a position in the video, in milliseconds.")
        return problems

    async def publish(
        self, tokens: TokenSet, request: PublishRequest, save_checkpoint: SaveCheckpoint
    ) -> PublishResult:
        if request.clip.presign is None:
            raise PlatformError(ErrorKind.PERMANENT, "no_source_url", "This clip is not stored where Instagram can fetch it.")
        await self._check_publishing_limit(tokens)
        data = {
            "media_type": "REELS",
            "video_url": request.clip.presign(VIDEO_URL_TTL_SECONDS),
            "caption": request.caption,
            "share_to_feed": "true" if request.options.get("share_to_feed", True) else "false",
        }
        # The Reels cover: the frame shown in the profile grid and on the feed
        # before playback. Instagram picks one itself when this is absent.
        if isinstance(request.options.get("thumb_offset"), int):
            data["thumb_offset"] = str(request.options["thumb_offset"])
        response = await self.request("POST", f"{API}/me/media", headers=self._auth(tokens), data=data)
        container_id = json_of(response).get("id")
        if not container_id:
            raise PlatformError(ErrorKind.TRANSIENT, "no_container", "Instagram did not accept the video.")
        await save_checkpoint(str(container_id))
        await self._await_container(tokens, str(container_id))
        return await self._publish_container(tokens, str(container_id))

    async def resolve_checkpoint(
        self, tokens: TokenSet, checkpoint: str, account_handle: str | None
    ) -> PublishResult | None:
        status = await self._container_status(tokens, checkpoint)
        if status == "PUBLISHED":
            # Published, but the container does not say which media it became.
            return PublishResult(platform_post_id=checkpoint, post_url=None)
        if status in ("FINISHED", "EXPIRED"):
            # Never published; a fresh container is the clean way to continue.
            raise NotPublished()
        if status == "ERROR":
            raise PlatformError(ErrorKind.PERMANENT, "container_error", "Instagram could not process the video.")
        raise PlatformError(ErrorKind.TRANSIENT, "still_processing", "Instagram is still processing the video.")

    async def _check_publishing_limit(self, tokens: TokenSet) -> None:
        response = await self.request(
            "GET",
            f"{API}/me/content_publishing_limit",
            params={"fields": "quota_usage,config"},
            headers=self._auth(tokens),
        )
        entries = json_of(response).get("data") or []
        usage = entries[0] if entries else {}
        total = (usage.get("config") or {}).get("quota_total")
        if total is not None and usage.get("quota_usage", 0) >= total:
            raise PlatformError(
                ErrorKind.QUOTA,
                "publishing_limit",
                "This Instagram account reached its 24-hour posting limit; will retry later.",
                timedelta(hours=1),
            )

    async def _await_container(self, tokens: TokenSet, container_id: str) -> None:
        for _ in range(STATUS_POLL_ATTEMPTS):
            status = await self._container_status(tokens, container_id)
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise PlatformError(ErrorKind.PERMANENT, "container_error", "Instagram could not process the video.")
            if status == "EXPIRED":
                raise PlatformError(ErrorKind.TRANSIENT, "container_expired", "Instagram's upload expired; will retry.")
            await asyncio.sleep(STATUS_POLL_SECONDS)
        raise PlatformError(ErrorKind.TRANSIENT, "still_processing", "Instagram is still processing the video.")

    async def _container_status(self, tokens: TokenSet, container_id: str) -> str | None:
        response = await self.request(
            "GET", f"{API}/{container_id}", params={"fields": "status_code"}, headers=self._auth(tokens)
        )
        return json_of(response).get("status_code")

    async def _publish_container(self, tokens: TokenSet, container_id: str) -> PublishResult:
        response = await self.request(
            "POST", f"{API}/me/media_publish", headers=self._auth(tokens), data={"creation_id": container_id}
        )
        media_id = json_of(response).get("id")
        if not media_id:
            raise PlatformError(ErrorKind.TRANSIENT, "publish_unconfirmed", "Instagram did not confirm the post.")
        permalink = None
        try:
            details = await self.request(
                "GET", f"{API}/{media_id}", params={"fields": "permalink"}, headers=self._auth(tokens)
            )
            permalink = json_of(details).get("permalink")
        except PlatformError:
            pass  # The post is live; a missing link is not worth failing it over.
        return PublishResult(platform_post_id=str(media_id), post_url=permalink)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _auth(tokens: TokenSet) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    @staticmethod
    def _tokens(body: dict[str, Any]) -> TokenSet:
        if not body.get("access_token"):
            raise PlatformError(ErrorKind.AUTH, "bad_token_response", "Instagram did not issue a token.")
        return TokenSet(access_token=body["access_token"], expires_at=expires_in(body.get("expires_in")))

    def map_error(self, response: httpx.Response) -> PlatformError:
        error = json_of(response).get("error")
        if not isinstance(error, dict):
            return default_error(self.label, response)
        code = error.get("code")
        subcode = error.get("error_subcode")
        label = f"ig_{code}" + (f"_{subcode}" if subcode else "")
        if code in _AUTH_CODES or response.status_code == 401:
            return PlatformError(ErrorKind.AUTH, label, "Instagram access was revoked or expired. Reconnect the account.")
        if subcode == _PUBLISH_LIMIT_SUBCODE:
            return PlatformError(
                ErrorKind.QUOTA, label, "This Instagram account reached its 24-hour posting limit.", timedelta(hours=1)
            )
        if code in _RATE_CODES:
            return PlatformError(ErrorKind.TRANSIENT, label, "Instagram asked us to slow down; will retry.", timedelta(minutes=5))
        if error.get("is_transient") or response.status_code >= 500:
            return PlatformError(ErrorKind.TRANSIENT, label, "Instagram is having problems; will retry.")
        message = str(error.get("error_user_msg") or error.get("message") or "")[:200]
        return PlatformError(ErrorKind.PERMANENT, label, f"Instagram rejected the request: {message}".strip())
