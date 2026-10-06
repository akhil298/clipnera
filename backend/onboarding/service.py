from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from core.exceptions import CustomException
from core.logging_config import get_logger
from onboarding.model import UserOnboarding
from onboarding.schema import OnboardingRequest, OnboardingResponse, OnboardingStatusResponse
from referral.service import ReferralService

log = get_logger(__name__)


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


class OnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._referrals = ReferralService(session)

    async def _user(self, user_id: str) -> User:
        user = await self._session.get(User, user_id)
        if not user:
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
        return user

    async def is_completed(self, user_id: str) -> bool:
        return await self._session.get(UserOnboarding, user_id) is not None

    async def status(self, user_id: str) -> OnboardingStatusResponse:
        completed = await self.is_completed(user_id)
        return OnboardingStatusResponse(
            completed=completed,
            can_use_referral_code=not completed and await self._referrals.can_use_code(await self._user(user_id)),
        )

    async def complete(self, user_id: str, body: OnboardingRequest) -> OnboardingResponse:
        """Save the form once. A referral code in it starts the referral in the
        same transaction, so a refused code saves nothing and can be fixed."""
        user = await self._user(user_id)
        if await self.is_completed(user_id):
            raise CustomException(message="You've already completed this.", code="ALREADY_ONBOARDED", status_code=409)

        row = UserOnboarding(
            user_id=user_id,
            role=body.role,
            role_other=_clean(body.role_other) if body.role == "other" else None,
            heard_from=body.heard_from,
            heard_from_other=_clean(body.heard_from_other) if body.heard_from == "other" else None,
        )
        self._session.add(row)
        notices = []
        if code := _clean(body.referral_code):
            _, notices = await self._referrals.attach(user, code)
        try:
            await self._session.commit()
        except IntegrityError:
            # Submitted twice at once: the first one won.
            await self._session.rollback()
            raise CustomException(message="You've already completed this.", code="ALREADY_ONBOARDED", status_code=409)
        log.info(f"Onboarding completed: user={user_id} role={body.role} heard_from={body.heard_from} referral={bool(code)}")

        for notice in notices:
            await notice()
        return OnboardingResponse(completed_at=row.completed_at, referral=await self._referrals.invited_by(user_id))
