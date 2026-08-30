from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from core.config import get_settings
from core.exceptions import CustomException

settings = get_settings()


class OAuthService:
    """Handles Google/Microsoft OAuth token verification."""

    GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
    MICROSOFT_USERINFO = "https://graph.microsoft.com/v1.0/me"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    async def verify_google(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token = await self._exchange_google_token(code, redirect_uri)
        return await self._fetch_google_user(token["access_token"])

    async def verify_microsoft(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token = await self._exchange_microsoft_token(code, redirect_uri)
        return await self._fetch_microsoft_user(token["access_token"])

    async def _exchange_google_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        client = AsyncOAuth2Client(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )
        token = await asyncio.to_thread(
            client.fetch_token,
            "https://oauth2.googleapis.com/token",
            code=code,
            redirect_uri=redirect_uri,
        )
        return token

    async def _exchange_microsoft_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        client = AsyncOAuth2Client(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_secret=settings.MICROSOFT_CLIENT_SECRET,
        )
        token = await asyncio.to_thread(
            client.fetch_token,
            f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            code=code,
            redirect_uri=redirect_uri,
        )
        return token

    async def _fetch_google_user(self, access_token: str) -> dict[str, Any]:
        response = await self._client.get(
            self.GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            raise CustomException(
                message="Failed to fetch Google user info",
                code="OAUTH_ERROR",
                status_code=400,
            )
        return response.json()

    async def _fetch_microsoft_user(self, access_token: str) -> dict[str, Any]:
        response = await self._client.get(
            self.MICROSOFT_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            raise CustomException(
                message="Failed to fetch Microsoft user info",
                code="OAUTH_ERROR",
                status_code=400,
            )
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
