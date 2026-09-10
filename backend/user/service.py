from __future__ import annotations

import re
from auth.model import User, AuthProvider
from user.repository import UserRepository
from subscription.service import SubscriptionService
from user.schema import UserProfileResponse


class UserService:
    """Profile related business logic."""

    def __init__(self, repository: UserRepository, subscription_service: SubscriptionService | None = None) -> None:
        self._repository = repository
        self._subscription_service = subscription_service

    async def get_profile(self, user_id: str) -> User | None:
        return await self._repository.get_by_id(user_id)

    @staticmethod
    def _get_initials(name: str | None, email: str) -> str:
        if name:
            parts = re.split(r"\s+", name.strip())
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            return name[:2].upper()
        return email[:2].upper() if email else "U"

    @staticmethod
    def to_response(user: User) -> "UserProfileResponse":  # type: ignore[name-defined]
        from user.schema import UserProfileResponse

        display_name = user.full_name or user.username or user.email.split("@")[0]
        return UserProfileResponse(
            id=user.id,
            name=display_name,
            email=user.email,
            avatar_url=user.avatar_url,
            avatar_initials=UserService._get_initials(display_name, user.email),
            active_workspace_id=None,
            providers=[a.provider.value for a in user.accounts],
        )

    async def to_full_response(self, user: User) -> "UserProfileResponse":
        from user.schema import UserProfileResponse

        display_name = user.full_name or user.username or user.email.split("@")[0]
        plan = "free"
        ai_credits_minutes_remaining = 0
        ai_credits_total = 0

        if self._subscription_service:
            credits = await self._subscription_service.get_user_credit_balance(user.id)
            sub = await self._subscription_service.get_user_subscription(user.id)
            if sub:
                plan = sub.plan.slug.value
                ai_credits_total = sub.plan.credit_minutes
                ai_credits_minutes_remaining = credits
            else:
                plan = "free"
                ai_credits_total = 0
                ai_credits_minutes_remaining = credits

        return UserProfileResponse(
            id=user.id,
            name=display_name,
            email=user.email,
            avatar_url=user.avatar_url,
            avatar_initials=UserService._get_initials(display_name, user.email),
            plan=plan,
            ai_credits_minutes_remaining=ai_credits_minutes_remaining,
            ai_credits_total=ai_credits_total,
            active_workspace_id=None,
            providers=[a.provider.value for a in user.accounts],
        )
