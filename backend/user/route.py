from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from user.repository import UserRepository
from user.schema import UserProfileResponse
from user.service import UserService
from subscription.service import SubscriptionService


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    return UserService(UserRepository(session), SubscriptionService.for_session(session))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]

router = APIRouter(tags=["user"])


@router.post("/me/plan-notice/dismiss", status_code=204)
async def dismiss_plan_notice(current_user: CurrentUserDep, service: UserServiceDep):
    """Hide the one-time "features moved to Pro" notice for good."""
    await service.dismiss_plan_notice(current_user["user_id"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: CurrentUserDep, service: UserServiceDep) -> UserProfileResponse:
    user = await service.get_profile(current_user["user_id"])
    if not user:
        from core.exceptions import CustomException

        raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
    return await service.to_full_response(user)
