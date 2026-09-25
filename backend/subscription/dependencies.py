"""Route guards for plan features and usage limits.

Attach them to a route (``dependencies=[Depends(require_feature("depth_captions"))]``)
or take the returned Entitlements as a parameter. The UI hides what a plan
cannot use, but only these checks stop a direct API call.
"""

from __future__ import annotations

from typing import Annotated, Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from core.database import get_db
from subscription.entitlements import Entitlements, Feature, UsageKey
from subscription.service import SubscriptionService


async def get_subscription_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionService:
    return SubscriptionService.for_session(session)


SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]


def require_feature(feature: Feature) -> Callable[..., Awaitable[Entitlements]]:
    """403 ``PRO_REQUIRED`` unless the caller's effective plan includes ``feature``."""

    async def dependency(current_user: CurrentUserDep, service: SubscriptionServiceDep) -> Entitlements:
        return await service.require_feature(current_user["user_id"], feature)

    return dependency


def check_limit(key: UsageKey) -> Callable[..., Awaitable[int]]:
    """Count one use of ``key`` today; 429 ``LIMIT_REACHED`` once the plan's
    daily limit is used up."""

    async def dependency(current_user: CurrentUserDep, service: SubscriptionServiceDep) -> int:
        return await service.consume_daily_quota(current_user["user_id"], key)

    return dependency
