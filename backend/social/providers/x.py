"""X via API v2: chunked media upload, then a post with the media attached.

Scopes: ``tweet.write`` (post), ``tweet.read`` + ``users.read`` (both required
by /2/users/me for the handle and follower count), ``media.write`` (upload),
``offline.access`` (refresh token). Confidential client with PKCE.

X bills per call with no free tier; social/quota.py stops publishing once
X_MONTHLY_BUDGET_USD is spent. Refresh tokens are single use: every refresh
returns a new one that must replace the old.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from core.config import get_settings
from social.model import SocialPlatform
from social.providers.base import (
    UPLOAD_TIMEOUT,
    ClipLimits,
    ErrorKind,
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
    retry_after_of,
)

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
API = "https://api.x.com/2"
TOKEN_URL = f"{API}/oauth2/token"
REVOKE_URL = f"{API}/oauth2/revoke"
ME_URL = f"{API}/users/me"
MEDIA_URL = f"{API}/media/upload"
POSTS_URL = f"{API}/tweets"

SEGMENT_BYTES = 4 * 1024**2  # X recommends at most 5 MB per segment.
STATUS_POLL_ATTEMPTS = 60
CAPTION_MAX = 280
# Billed per request (USD micros), from X's published pay-per-use prices.
POST_COST_MICROS = 15_000


class XProvider(PlatformProvider):
    platform = SocialPlatform.X
    label = "X"
    scopes = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")
    uses_pkce = True
    caption_max_chars = CAPTION_MAX
    limits = ClipLimits(
        max_duration_seconds=1200,
        min_duration_seconds=0.5,
        max_size_bytes=512 * 1024**2,
        containers=("mp4", "mov"),
        video_codecs=("h264",),
        max_fps=60,
    )

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.X_CLIENT_ID and settings.X_CLIENT_SECRET)

    # -- OAuth -------------------------------------------------------------

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "response_type": "code",
            "client_id": get_settings().X_CLIENT_ID,
            "redirect_uri": self.redirect_uri(),
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str | None) -> TokenSet:
        response = await self.request(
            "POST",
            TOKEN_URL,
            headers=self._basic_auth(),
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri(),
                "code_verifier": code_verifier,
            },
        )
        tokens = self._tokens(json_of(response))
        if not set(self.scopes) <= set((tokens.scopes or "").split()):
            raise PlatformError(
                ErrorKind.PERMANENT,
                "scopes_missing",
                "Please allow every requested X permission so Clipnera can post and show your profile.",
            )
        return tokens

    async def refresh(self, tokens: TokenSet) -> TokenSet:
        if not tokens.refresh_token:
            raise PlatformError(ErrorKind.AUTH, "no_refresh_token", "X access expired. Reconnect the account.")
        response = await self.request(
            "POST",
            TOKEN_URL,
            headers=self._basic_auth(),
            data={"grant_type": "refresh_token", "refresh_token": tokens.refresh_token},
        )
        return self._tokens(json_of(response))

    async def revoke(self, tokens: TokenSet) -> None:
        token, hint = (
            (tokens.refresh_token, "refresh_token") if tokens.refresh_token else (tokens.access_token, "access_token")
        )
        await self.request(
            "POST", REVOKE_URL, headers=self._basic_auth(), data={"token": token, "token_type_hint": hint}
        )

    async def fetch_profile(self, tokens: TokenSet) -> Profile:
        response = await self.request(
            "GET",
            ME_URL,
            params={"user.fields": "profile_image_url,public_metrics"},
            headers=self._auth(tokens),
        )
        user = json_of(response).get("data") or {}
        if not user.get("id"):
            raise PlatformError(ErrorKind.TRANSIENT, "no_profile", "X did not return the profile.")
        return Profile(
            platform_user_id=str(user["id"]),
            handle=f"@{user['username']}" if user.get("username") else None,
            display_name=user.get("name"),
            avatar_url=user.get("profile_image_url"),
            follower_count=(user.get("public_metrics") or {}).get("followers_count"),
        )

    # -- publishing ----------------------------------------------------------

    async def publish(
        self, tokens: TokenSet, request: PublishRequest, save_checkpoint: SaveCheckpoint
    ) -> PublishResult:
        media_id = await self._upload(tokens, request)
        # The post is the only public step; an upload nobody attaches expires unseen.
        await save_checkpoint(media_id)
        response = await self.request(
            "POST",
            POSTS_URL,
            headers=self._auth(tokens),
            json={"text": request.caption, "media": {"media_ids": [media_id]}},
        )
        post_id = (json_of(response).get("data") or {}).get("id")
        if not post_id:
            raise PlatformError(ErrorKind.PERMANENT, "post_unconfirmed", "X did not confirm the post.")
        handle = (request.account_handle or "").lstrip("@") or "i/web"
        return PublishResult(platform_post_id=str(post_id), post_url=f"https://x.com/{handle}/status/{post_id}")

    async def _upload(self, tokens: TokenSet, request: PublishRequest) -> str:
        clip = request.clip
        init = await self.request(
            "POST",
            f"{MEDIA_URL}/initialize",
            headers=self._auth(tokens),
            json={"media_type": "video/mp4", "total_bytes": clip.size_bytes, "media_category": "tweet_video"},
        )
        media_id = (json_of(init).get("data") or {}).get("id")
        if not media_id:
            raise PlatformError(ErrorKind.TRANSIENT, "no_media_id", "X did not start the upload.")
        for index, (_, segment) in enumerate(clip.chunks(SEGMENT_BYTES)):
            await self.request(
                "POST",
                f"{MEDIA_URL}/{media_id}/append",
                headers=self._auth(tokens),
                data={"segment_index": str(index)},
                files={"media": ("clip.mp4", segment, "video/mp4")},
                timeout=UPLOAD_TIMEOUT,
            )
        finalized = await self.request("POST", f"{MEDIA_URL}/{media_id}/finalize", headers=self._auth(tokens))
        await self._await_processing(tokens, media_id, (json_of(finalized).get("data") or {}).get("processing_info"))
        return str(media_id)

    async def _await_processing(self, tokens: TokenSet, media_id: str, info: dict[str, Any] | None) -> None:
        for _ in range(STATUS_POLL_ATTEMPTS):
            state = (info or {}).get("state")
            if state in (None, "succeeded"):
                return
            if state == "failed":
                detail = ((info or {}).get("error") or {}).get("message") or "processing failed"
                raise PlatformError(ErrorKind.PERMANENT, "media_failed", f"X could not process the video: {detail}")
            await asyncio.sleep(max(1, int((info or {}).get("check_after_secs") or 5)))
            response = await self.request(
                "GET", MEDIA_URL, params={"command": "STATUS", "media_id": media_id}, headers=self._auth(tokens)
            )
            info = (json_of(response).get("data") or {}).get("processing_info")
        raise PlatformError(ErrorKind.TRANSIENT, "still_processing", "X is still processing the video; will retry.")

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _basic_auth() -> dict[str, str]:
        settings = get_settings()
        pair = f"{settings.X_CLIENT_ID}:{settings.X_CLIENT_SECRET}".encode()
        return {"Authorization": f"Basic {base64.b64encode(pair).decode()}"}

    @staticmethod
    def _auth(tokens: TokenSet) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}"}

    @staticmethod
    def _tokens(body: dict[str, Any]) -> TokenSet:
        if not body.get("access_token"):
            raise PlatformError(ErrorKind.AUTH, "bad_token_response", "X did not issue a token.")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=expires_in(body.get("expires_in")),
            scopes=body.get("scope"),
        )

    def map_error(self, response: httpx.Response) -> PlatformError:
        body = json_of(response)
        status = response.status_code
        oauth_error = body.get("error")
        if isinstance(oauth_error, str):
            if oauth_error in ("invalid_request", "invalid_grant") and "token" in str(body.get("error_description", "")):
                return PlatformError(ErrorKind.AUTH, oauth_error, "X access was revoked or expired. Reconnect the account.")
            return default_error(self.label, response, code=oauth_error)
        detail = str(body.get("detail") or next(
            (e.get("message") for e in body.get("errors") or [] if isinstance(e, dict)), ""
        ))[:200]
        if status == 401:
            return PlatformError(ErrorKind.AUTH, "unauthorized", "X access was revoked or expired. Reconnect the account.")
        if status == 402 or "credit" in detail.lower():
            return PlatformError(
                ErrorKind.QUOTA, "credits_depleted", "Posting to X is paused for now; will retry.", timedelta(hours=1)
            )
        if status == 429:
            return PlatformError(ErrorKind.QUOTA, "rate_limited", "X rate limit reached; will retry.", retry_after_of(response))
        if "duplicate" in detail.lower():
            return PlatformError(ErrorKind.PERMANENT, "duplicate", "X rejected this as a duplicate of an earlier post.")
        return default_error(self.label, response, detail=f"X rejected the request: {detail}".strip())
