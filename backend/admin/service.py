from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from admin.repository import REVENUE_CURRENCY, AdminRepository
from admin.schema import (
    AdminClip,
    AdminCreditEntry,
    AdminDailyGrowth,
    AdminGrowthResponse,
    AdminLoginEntry,
    AdminOverviewResponse,
    AdminProjectClipsResponse,
    AdminUserDetailResponse,
    AdminUserPayment,
    AdminUserPlanRequest,
    AdminUserProject,
    AdminUserResponse,
    AdminUserSort,
)
from auth.model import User
from clip_generation.service import ClipService
from core.exceptions import CustomException
from core.logging_config import get_logger
from subscription.entitlements import PURCHASABLE_PLAN
from subscription.model import PlanSlug
from subscription.repository import PlanRepository
from referral.service import reverse_referral_pro
from subscription.service import SubscriptionService

log = get_logger(__name__)

# How much history the user detail page shows.
DETAIL_PROJECTS = 200
DETAIL_LOGINS = 100
DETAIL_PAYMENTS = 50
DETAIL_CREDIT_ENTRIES = 200


class AdminService:
    def __init__(
        self, repo: AdminRepository, plan_repo: PlanRepository, subscription_service: SubscriptionService
    ) -> None:
        self._repo = repo
        self._plan_repo = plan_repo
        self._subscription_service = subscription_service

    async def list_users(
        self, query: str | None, limit: int, offset: int, sort: AdminUserSort = "newest"
    ) -> list[AdminUserResponse]:
        query = (query or "").strip() or None
        rows = await self._repo.list_users(query, limit, offset, sort)
        stats = await self._repo.user_stats([user.id for user, _, _ in rows])
        return [self._to_response(user, plan, expires_at, stats[user.id]) for user, plan, expires_at in rows]

    async def user_detail(self, user_id: str) -> AdminUserDetailResponse:
        """Everything the user has done: projects, logins, payments and credits."""
        await self._require_user(user_id)
        summary = await self._subscription_service.get_plan_summary(user_id)
        projects = await self._repo.user_projects(user_id, DETAIL_PROJECTS)
        return AdminUserDetailResponse(
            user=await self._get_user(user_id),
            credits_total=summary.entitlements.credit_minutes,
            next_credit_reset_at=summary.next_credit_reset_at,
            active_days=await self._repo.count_active_days(user_id),
            projects=[
                AdminUserProject(
                    id=project.id,
                    title=project.title,
                    source_type=project.source_type,
                    source_url=project.source_url,
                    status=project.status.value,
                    duration_seconds=project.duration_seconds,
                    clips=clips,
                    credits_charged=credits,
                    ai_cost_usd=cost,
                    created_at=project.created_at,
                )
                for project, clips, credits, cost in projects
            ],
            logins=[
                AdminLoginEntry.model_validate(event, from_attributes=True)
                for event in await self._repo.user_logins(user_id, DETAIL_LOGINS)
            ],
            payments=[
                AdminUserPayment(
                    id=payment.id,
                    amount=float(payment.amount),
                    currency=payment.currency,
                    status=payment.status.value,
                    plan_type=payment.plan_type.value if payment.plan_type else None,
                    credit_pack=payment.credit_pack,
                    credits=payment.credits,
                    created_at=payment.created_at,
                    verified_at=payment.verified_at,
                )
                for payment in await self._repo.user_payments(user_id, DETAIL_PAYMENTS)
            ],
            credit_history=[
                AdminCreditEntry.model_validate(entry, from_attributes=True)
                for entry in await self._repo.user_credit_history(user_id, DETAIL_CREDIT_ENTRIES)
            ],
        )

    async def project_clips(self, user_id: str, project_id: str) -> AdminProjectClipsResponse:
        """A user's project with playable links to its source video and every clip."""
        project = await self._repo.user_project(user_id, project_id)
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)
        media = ClipService()
        return AdminProjectClipsResponse(
            project_id=project.id,
            title=project.title,
            source_video_url=media.source_video_url(project),
            clips=[
                AdminClip(
                    id=clip.id,
                    title=clip.title,
                    duration_seconds=clip.duration_seconds,
                    score=clip.score,
                    status=clip.status,
                    video_url=media.video_url(clip),
                    captioned_video_url=media.burned_url(clip),
                    poster_url=media.poster_url(clip),
                    created_at=clip.created_at,
                )
                for clip in await self._repo.project_clips(project.id)
            ],
        )

    async def growth(self, days: int) -> AdminGrowthResponse:
        """Sign-ups, activity, output and money per UTC day over the last ``days`` days."""
        today = datetime.utcnow().date()
        first_day = today - timedelta(days=days - 1)
        series = await self._repo.growth_series(first_day)
        daily = [
            AdminDailyGrowth(day=day, **{field: values.get(day, 0) for field, values in series.items()})
            for day in (first_day + timedelta(days=offset) for offset in range(days))
        ]

        def total(field: str) -> float:
            return sum(getattr(point, field) for point in daily)

        return AdminGrowthResponse(
            days=days,
            total_users=await self._repo.count_users(),
            new_users=int(total("signups")),
            active_in_window=await self._repo.count_active_users_since(first_day),
            active_today=await self._repo.count_active_users_since(today),
            active_7d=await self._repo.count_active_users_since(today - timedelta(days=6)),
            active_30d=await self._repo.count_active_users_since(today - timedelta(days=29)),
            pro_users=await self._repo.count_paid_users(),
            projects=int(total("projects")),
            clips=int(total("clips")),
            revenue=total("revenue"),
            currency=REVENUE_CURRENCY,
            ai_cost_usd=total("ai_cost_usd"),
            daily=daily,
        )

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
            # Pro taken away: a referral it completed no longer counts.
            await reverse_referral_pro(user_id)
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
            revenue_this_month=await self._repo.revenue_since(month_start, REVENUE_CURRENCY),
            currency=REVENUE_CURRENCY,
        )

    async def _require_user(self, user_id: str) -> None:
        if not await self._subscription_service.get_account(user_id):
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)

    async def _get_user(self, user_id: str) -> AdminUserResponse:
        summary = await self._subscription_service.get_plan_summary(user_id)
        user = await self._subscription_service.get_account(user_id)
        stats = (await self._repo.user_stats([user_id]))[user_id]
        return self._to_response(user, summary.entitlements.plan, summary.plan_expires_at, stats)

    @staticmethod
    def _to_response(
        user: User, plan: str | None, expires_at: datetime | None, stats: dict[str, Any]
    ) -> AdminUserResponse:
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            name=user.full_name or user.username,
            role=user.role.value,
            plan=plan or PlanSlug.FREE.value,
            plan_expires_at=expires_at,
            created_at=user.created_at,
            **stats,
        )
