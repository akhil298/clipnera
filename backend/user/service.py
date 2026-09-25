from __future__ import annotations

import re
from auth.model import User, AuthProvider
from core.exceptions import CustomException
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

    async def get_me(self, user_id: str) -> UserProfileResponse:
        user = await self.get_profile(user_id)
        if not user:
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
        return await self.to_full_response(user)

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
            role=user.role.value,
        )

    async def to_full_response(self, user: User) -> "UserProfileResponse":
        from user.schema import UserProfileResponse

        display_name = user.full_name or user.username or user.email.split("@")[0]
        plan_fields = {}
        if self._subscription_service:
            summary = await self._subscription_service.get_plan_summary(user.id)
            ent = summary.entitlements
            plan_fields = {
                "plan": ent.plan,
                "plan_expires_at": summary.plan_expires_at,
                "ai_credits_minutes_remaining": summary.credit_minutes_remaining,
                "ai_credits_total": ent.credit_minutes,
                "features": ent.features(),
                "daily_limits": ent.daily_limits,
                "usage_today": summary.usage_today,
            }

        return UserProfileResponse(
            id=user.id,
            name=display_name,
            email=user.email,
            avatar_url=user.avatar_url,
            avatar_initials=UserService._get_initials(display_name, user.email),
            active_workspace_id=None,
            providers=[a.provider.value for a in user.accounts],
            role=user.role.value,
            **plan_fields,
        )

    async def dismiss_plan_notice(self, user_id: str) -> None:
        await self._repository.clear_plan_notice(user_id)
