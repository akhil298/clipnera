from __future__ import annotations

from datetime import datetime

from admin.repository import AdminRepository
from admin.schema import AdminOverviewResponse, AdminUserPlanRequest, AdminUserResponse
from auth.model import User
from core.exceptions import CustomException
from core.logging_config import get_logger
from subscription.entitlements import PURCHASABLE_PLAN
from subscription.model import PlanSlug
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService

log = get_logger(__name__)


class AdminService:
    def __init__(
        self, repo: AdminRepository, plan_repo: PlanRepository, subscription_service: SubscriptionService
    ) -> None:
        self._repo = repo
        self._plan_repo = plan_repo
        self._subscription_service = subscription_service

    async def list_users(self, query: str | None, limit: int, offset: int) -> list[AdminUserResponse]:
        query = (query or "").strip() or None
        return [
            self._to_response(user, plan, expires_at)
            for user, plan, expires_at in await self._repo.list_users(query, limit, offset)
        ]

    async def set_plan(self, user_id: str, body: AdminUserPlanRequest, admin_id: str) -> AdminUserResponse:
        """Grant Pro for ``body.days`` (extending any current Pro) or revoke it."""
        if body.plan == PURCHASABLE_PLAN:
            plan = await self._plan_repo.get_by_slug(PURCHASABLE_PLAN)
            if not plan:
                raise CustomException(message="Pro plan is not configured", code="PLAN_MISSING", status_code=500)
            await self._require_user(user_id)
            await self._subscription_service.extend_plan(user_id, plan, body.days)
        else:
            await self._require_user(user_id)
            await self._subscription_service.revoke_paid_plan(user_id)
        log.info(f"Admin plan change: user={user_id} plan={body.plan} days={body.days} by={admin_id}")
        return await self._get_user(user_id)

    async def overview(self) -> AdminOverviewResponse:
        total = await self._repo.count_users()
        pro = await self._repo.count_paid_users()
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return AdminOverviewResponse(
            total_users=total,
            free_users=total - pro,
            pro_users=pro,
            pending_payments=await self._repo.count_pending_payments(),
            revenue_this_month=await self._repo.revenue_since(month_start, "INR"),
            currency="INR",
        )

    async def _require_user(self, user_id: str) -> None:
        if not await self._subscription_service.get_account(user_id):
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)

    async def _get_user(self, user_id: str) -> AdminUserResponse:
        summary = await self._subscription_service.get_plan_summary(user_id)
        user = await self._subscription_service.get_account(user_id)
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            name=user.full_name or user.username,
            role=user.role.value,
            plan=summary.entitlements.plan,
            plan_expires_at=summary.plan_expires_at,
            created_at=user.created_at,
        )

    @staticmethod
    def _to_response(user: User, plan: str | None, expires_at: datetime | None) -> AdminUserResponse:
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            name=user.full_name or user.username,
            role=user.role.value,
            plan=plan or PlanSlug.FREE.value,
            plan_expires_at=expires_at,
            created_at=user.created_at,
        )
