from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep, get_db
from core.responses import ApiResponse, ok
from sqlalchemy.ext.asyncio import AsyncSession
from social.service import SocialAccountService
from user.repository import UserRepository
from user.schema import DeleteAccountRequest, EmailPreferencesRequest, UnsubscribeRequest, UserProfileResponse
from user.service import UserService
from subscription.service import SubscriptionService


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    return UserService(
        UserRepository(session), SubscriptionService.for_session(session), SocialAccountService(session)
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]

router = APIRouter(tags=["user"])


@router.post("/me/plan-notice/dismiss", status_code=204)
async def dismiss_plan_notice(current_user: CurrentUserDep, service: UserServiceDep):
    """Hide the one-time "features moved to Pro" notice for good."""
    await service.dismiss_plan_notice(current_user["user_id"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: CurrentUserDep, service: UserServiceDep) -> UserProfileResponse:
    return await service.get_me(current_user["user_id"])


@router.put("/me/email-preferences", response_model=ApiResponse[UserProfileResponse])
async def set_email_preferences(
    data: EmailPreferencesRequest, current_user: CurrentUserDep, service: UserServiceDep
):
    profile = await service.set_email_notifications(current_user["user_id"], data.email_notifications)
    return ok(profile, message="Email preferences saved")


@router.post("/email/unsubscribe", response_model=ApiResponse[None])
async def unsubscribe(data: UnsubscribeRequest, service: UserServiceDep):
    """Public: the signed token in an email's unsubscribe link identifies the user."""
    await service.unsubscribe(data.token)
    return ok(None, message="You will no longer receive account emails from Clipnera.")


@router.post("/me/delete", response_model=ApiResponse[None])
async def delete_account(data: DeleteAccountRequest, current_user: CurrentUserDep, service: UserServiceDep):
    """Permanently delete the signed-in user's account and everything in it."""
    await service.delete_account(current_user["user_id"], data.confirm_email)
    return ok(None, message="Your account and its data have been deleted.")
