from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.activity import record_activity
from auth.model import User, UserRole
from auth.repository import UserRepository
from auth.oauth_service import OAuthService
from auth.service import AuthService
from core.database import get_db
from core.exceptions import CustomException
from core.security import decode_access_token


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncIterator[AuthService]:
    """Dependency-injected AuthService factory; closes the OAuth HTTP client after the request."""
    oauth_service = OAuthService()
    try:
        yield AuthService(UserRepository(session), oauth_service)
    finally:
        await oauth_service.close()


async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise CustomException(
            message="Missing or invalid authorization header",
            code="UNAUTHORIZED",
            status_code=401,
        )

    token = auth_header[7:]
    payload = decode_access_token(token)
    if not payload:
        raise CustomException(
            message="Invalid or expired token",
            code="INVALID_TOKEN",
            status_code=401,
        )

    await record_activity(payload["sub"])
    return {"user_id": payload["sub"]}


async def get_current_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the caller and require the admin role.

    The role is read from the database on every request, not from the token, so
    revoking it takes effect immediately.
    """
    user = await UserRepository(session).get_user_by_id(current_user["user_id"])
    if not user or not user.is_active or user.role != UserRole.ADMIN:
        raise CustomException(message="Admin access required", code="FORBIDDEN", status_code=403)
    return user


# Annotated dependencies for route injection
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[dict, Depends(get_current_user)]
CurrentAdminDep = Annotated[User, Depends(get_current_admin)]
