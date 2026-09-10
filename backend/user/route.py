from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from user.repository import UserRepository
from user.schema import UserProfileResponse
from user.service import UserService
from subscription.repository import PlanRepository, UserSubscriptionRepository, PaymentTransactionRepository, CreditLedgerRepository
from subscription.service import SubscriptionService


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    user_repo = UserRepository(session)
    plan_repo = PlanRepository(session)
    sub_repo = UserSubscriptionRepository(session)
    tx_repo = PaymentTransactionRepository(session)
    ledger_repo = CreditLedgerRepository(session)
    subscription_service = SubscriptionService(plan_repo, sub_repo, tx_repo, ledger_repo)
    return UserService(user_repo, subscription_service)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]

router = APIRouter(tags=["user"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: CurrentUserDep, service: UserServiceDep) -> UserProfileResponse:
    user = await service.get_profile(current_user["user_id"])
    if not user:
        from core.exceptions import CustomException

        raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
    return await service.to_full_response(user)
