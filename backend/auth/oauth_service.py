from __future__ import annotations

from typing import Any

import httpx

from core.config import get_settings
from core.exceptions import CustomException

settings = get_settings()


class OAuthService:
    """Handles Google/Microsoft OAuth token verification."""

    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
    MICROSOFT_USERINFO = "https://graph.microsoft.com/v1.0/me"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    async def verify_google(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token = await self._exchange_code(
            self.GOOGLE_TOKEN_URL,
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            code,
            redirect_uri,
        )
        user = await self._fetch_user(self.GOOGLE_USERINFO, token["access_token"], "Google")
        # Accounts are linked by email, so only trust an address Google has verified.
        if not user.get("email") or not user.get("email_verified"):
            raise CustomException(
                message="Your Google account has no verified email address",
                code="OAUTH_EMAIL_UNVERIFIED",
                status_code=400,
            )
        return user

    async def verify_microsoft(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token = await self._exchange_code(
            f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            settings.MICROSOFT_CLIENT_ID,
            settings.MICROSOFT_CLIENT_SECRET,
            code,
            redirect_uri,
        )
        return await self._fetch_user(self.MICROSOFT_USERINFO, token["access_token"], "Microsoft")

    async def _exchange_code(
        self, token_url: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        response = await self._client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if response.status_code != 200:
            raise CustomException(
                message="Sign-in could not be completed. Please try again.",
                code="OAUTH_ERROR",
                status_code=400,
            )
        return response.json()

    async def _fetch_user(self, url: str, access_token: str, provider_name: str) -> dict[str, Any]:
        response = await self._client.get(url, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            raise CustomException(
                message=f"Failed to fetch {provider_name} user info",
                code="OAUTH_ERROR",
                status_code=400,
            )
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
