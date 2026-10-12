from __future__ import annotations

from typing import Annotated, Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep

from core.database import get_db
from feature_flags.service import FeatureFlagService


async def get_feature_flag_service(session: Annotated[AsyncSession, Depends(get_db)]) -> FeatureFlagService:
    return FeatureFlagService(session)


FeatureFlagServiceDep = Annotated[FeatureFlagService, Depends(get_feature_flag_service)]


def require_user_flag(key: str) -> Callable[..., Awaitable[None]]:
    """403 FEATURE_DISABLED unless ``key`` is on for everyone or for the signed-in user (staged rollout)."""

    async def dependency(user: CurrentUserDep, service: FeatureFlagServiceDep) -> None:
        await service.require(key, user_id=user["user_id"])

    return dependency


def require_flag(key: str) -> Callable[..., Awaitable[None]]:
    """403 FEATURE_DISABLED while ``key`` (or its parent) is off."""

    async def dependency(service: FeatureFlagServiceDep) -> None:
        await service.require(key)

    return dependency
