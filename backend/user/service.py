from __future__ import annotations

import asyncio
import re
from auth.model import User, AuthProvider
from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from payment.service import SCREENSHOT_PREFIX
from social.service import SocialAccountService
from user.repository import UserRepository
from subscription.service import SubscriptionService
from user.schema import UserProfileResponse
from user.unsubscribe import user_id_from_token

log = get_logger(__name__)

# Every S3 folder that holds a user's files, each keyed "<prefix>/<user_id>/...".
USER_FILE_PREFIXES = ("videos", "clips", "social", "reels", SCREENSHOT_PREFIX)


def _delete_user_files(user_id: str) -> int:
    s3 = S3()
    bucket = get_settings().S3_BUCKET_NAME
    return sum(s3.delete_prefix(bucket, f"{prefix}/{user_id}/") for prefix in USER_FILE_PREFIXES)


class UserService:
    """Profile related business logic."""

    def __init__(
        self,
        repository: UserRepository,
        subscription_service: SubscriptionService | None = None,
        social_service: SocialAccountService | None = None,
    ) -> None:
        self._repository = repository
        self._subscription_service = subscription_service
        self._social_service = social_service

    async def get_profile(self, user_id: str) -> User | None:
        return await self._repository.get_by_id(user_id)

    async def _require_user(self, user_id: str) -> User:
        user = await self.get_profile(user_id)
        if not user:
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
        return user

    async def get_me(self, user_id: str) -> UserProfileResponse:
        return await self.to_full_response(await self._require_user(user_id))

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
            email_notifications=user.email_notifications,
            **plan_fields,
        )

    async def dismiss_plan_notice(self, user_id: str) -> None:
        await self._repository.clear_plan_notice(user_id)

    async def set_email_notifications(self, user_id: str, enabled: bool) -> UserProfileResponse:
        await self._require_user(user_id)
        await self._repository.set_email_notifications(user_id, enabled)
        return await self.get_me(user_id)

    async def unsubscribe(self, token: str) -> None:
        """Turn off account emails for the user an unsubscribe link was sent to."""
        user_id = user_id_from_token(token)
        if not user_id:
            raise CustomException(message="This unsubscribe link is invalid.", code="INVALID_TOKEN", status_code=400)
        # A deleted account has nothing left to unsubscribe; the link still succeeds.
        if await self.get_profile(user_id):
            await self._repository.set_email_notifications(user_id, False)

    async def delete_account(self, user_id: str, confirm_email: str) -> None:
        """Permanently delete the user, their files and their connected accounts.

        Files go first: if S3 fails nothing else has changed and the user can
        retry, rather than being left with a deleted account and orphaned videos.
        """
        user = await self._require_user(user_id)
        if confirm_email.strip().lower() != user.email.lower():
            raise CustomException(
                message="Type your account email exactly to confirm.",
                code="CONFIRMATION_MISMATCH",
                status_code=400,
            )
        files = await asyncio.to_thread(_delete_user_files, user_id)
        if self._social_service:
            await self._social_service.purge_user(user_id)
        await self._repository.delete(user_id)
        log.info(f"Account deleted: user_id={user_id} files={files}")
