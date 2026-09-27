from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, String, cast, desc, func, nulls_last, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.schema import AdminUserSort
from auth.model import LoginEvent, User, UserActivityDay
from clip.model import VideoProject
from clip_generation.model import GeneratedClip
from subscription.model import (
    CreditLedger,
    PaymentStatus,
    PaymentTransaction,
    Plan,
    PlanSlug,
    SubscriptionStatus,
    UserSubscription,
)
from usage.model import LlmUsage

# Ledger rows a pipeline run writes against its project: the charge, a resume
# charge and any refund, so their sum is what the project really cost.
PROJECT_CREDIT_REFERENCES = ("video_project", "video_project_resume", "video_project_refund")
REVENUE_CURRENCY = "INR"


def _approved_payments():
    return (
        PaymentTransaction.status == PaymentStatus.SUCCESS,
        PaymentTransaction.currency == REVENUE_CURRENCY,
    )


def _sort_key(sort: AdminUserSort):
    """Per-user value to order the user list by; None orders by sign-up."""
    if sort == "last_active":
        column, value = UserActivityDay.user_id, func.max(UserActivityDay.day)
    elif sort == "projects":
        column, value = VideoProject.user_id, func.count(VideoProject.id)
    elif sort == "ai_cost":
        column, value = LlmUsage.user_id, func.sum(LlmUsage.cost_usd)
    else:
        return None
    return select(column.label("user_id"), value.label("key")).group_by(column).subquery()


def _paid_subscriptions(now: datetime):
    """Active paid subscriptions that have not ended, queued ones included."""
    return (
        select(UserSubscription.user_id)
        .join(Plan, Plan.id == UserSubscription.plan_id)
        .where(
            UserSubscription.status == SubscriptionStatus.ACTIVE,
            UserSubscription.current_period_end > now,
            Plan.slug != PlanSlug.FREE,
        )
    )


class AdminRepository:
    """Cross-user reads for the admin panel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_users(
        self, query: str | None, limit: int, offset: int, sort: AdminUserSort = "newest"
    ) -> list[tuple[User, str | None, datetime | None]]:
        """Users in ``sort`` order (newest first by default), each with the paid
        plan in force now (or None) and when paid access ends."""
        now = datetime.utcnow()
        paid = _paid_subscriptions(now)
        expires = (
            paid.add_columns(func.max(UserSubscription.current_period_end).label("expires_at"))
            .group_by(UserSubscription.user_id)
            .subquery()
        )
        current = (
            paid.add_columns(func.max(cast(Plan.slug, String)).label("plan"))
            .where(UserSubscription.current_period_start <= now)
            .group_by(UserSubscription.user_id)
            .subquery()
        )
        stmt = (
            select(User, current.c.plan, expires.c.expires_at)
            .outerjoin(current, current.c.user_id == User.id)
            .outerjoin(expires, expires.c.user_id == User.id)
        )
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
        key = _sort_key(sort)
        if key is not None:
            stmt = stmt.outerjoin(key, key.c.user_id == User.id).order_by(nulls_last(desc(key.c.key)))
        stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def user_stats(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Activity and money totals for each user, keyed by the AdminUserResponse field."""
        stats: dict[str, dict[str, Any]] = {user_id: {} for user_id in user_ids}
        if not user_ids:
            return stats
        queries = {
            "last_login_at": select(LoginEvent.user_id, func.max(LoginEvent.created_at))
            .where(LoginEvent.user_id.in_(user_ids))
            .group_by(LoginEvent.user_id),
            "last_active_on": select(UserActivityDay.user_id, func.max(UserActivityDay.day))
            .where(UserActivityDay.user_id.in_(user_ids))
            .group_by(UserActivityDay.user_id),
            "projects": select(VideoProject.user_id, func.count(VideoProject.id))
            .where(VideoProject.user_id.in_(user_ids))
            .group_by(VideoProject.user_id),
            "clips": select(GeneratedClip.user_id, func.count(GeneratedClip.id))
            .where(GeneratedClip.user_id.in_(user_ids))
            .group_by(GeneratedClip.user_id),
            "ai_cost_usd": select(LlmUsage.user_id, func.sum(LlmUsage.cost_usd))
            .where(LlmUsage.user_id.in_(user_ids))
            .group_by(LlmUsage.user_id),
            "total_paid": select(PaymentTransaction.user_id, func.sum(PaymentTransaction.amount))
            .where(PaymentTransaction.user_id.in_(user_ids), *_approved_payments())
            .group_by(PaymentTransaction.user_id),
            # The newest ledger row holds the balance, as get_latest_balance reads it.
            "credits_left": select(CreditLedger.user_id, CreditLedger.balance_after)
            .where(CreditLedger.user_id.in_(user_ids))
            .distinct(CreditLedger.user_id)
            .order_by(CreditLedger.user_id, desc(CreditLedger.created_at)),
        }
        for field, stmt in queries.items():
            for user_id, value in (await self._session.execute(stmt)).all():
                stats[user_id][field] = value
        return stats

    async def user_projects(self, user_id: str, limit: int) -> list[tuple[VideoProject, int, int, float]]:
        """The user's projects newest first, each with clips made, net credits
        charged and AI spend."""
        clips = (
            select(GeneratedClip.project_id, func.count(GeneratedClip.id).label("n"))
            .where(GeneratedClip.user_id == user_id)
            .group_by(GeneratedClip.project_id)
            .subquery()
        )
        credits = (
            select(CreditLedger.reference_id.label("project_id"), func.sum(CreditLedger.amount).label("net"))
            .where(CreditLedger.user_id == user_id, CreditLedger.reference_type.in_(PROJECT_CREDIT_REFERENCES))
            .group_by(CreditLedger.reference_id)
            .subquery()
        )
        cost = (
            select(LlmUsage.project_id, func.sum(LlmUsage.cost_usd).label("usd"))
            .where(LlmUsage.project_id.in_(select(VideoProject.id).where(VideoProject.user_id == user_id)))
            .group_by(LlmUsage.project_id)
            .subquery()
        )
        stmt = (
            select(
                VideoProject,
                func.coalesce(clips.c.n, 0).label("clips"),
                (-func.coalesce(credits.c.net, 0)).label("credits_charged"),
                func.coalesce(cost.c.usd, 0.0).label("ai_cost_usd"),
            )
            .outerjoin(clips, clips.c.project_id == VideoProject.id)
            .outerjoin(credits, credits.c.project_id == VideoProject.id)
            .outerjoin(cost, cost.c.project_id == VideoProject.id)
            .where(VideoProject.user_id == user_id)
            .order_by(desc(VideoProject.created_at))
            .limit(limit)
        )
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    async def user_logins(self, user_id: str, limit: int) -> list[LoginEvent]:
        stmt = select(LoginEvent).where(LoginEvent.user_id == user_id).order_by(desc(LoginEvent.created_at)).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def user_payments(self, user_id: str, limit: int) -> list[PaymentTransaction]:
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(desc(PaymentTransaction.created_at))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def user_credit_history(self, user_id: str, limit: int) -> list[CreditLedger]:
        stmt = select(CreditLedger).where(CreditLedger.user_id == user_id).order_by(desc(CreditLedger.created_at)).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_active_days(self, user_id: str) -> int:
        stmt = select(func.count()).select_from(UserActivityDay).where(UserActivityDay.user_id == user_id)
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_active_users_since(self, first_day: date) -> int:
        stmt = select(func.count(func.distinct(UserActivityDay.user_id))).where(UserActivityDay.day >= first_day)
        return int((await self._session.execute(stmt)).scalar_one())

    async def growth_series(self, first_day: date) -> dict[str, dict[date, float]]:
        """Per-day totals from ``first_day`` (UTC), keyed by the AdminDailyGrowth field."""
        since = datetime.combine(first_day, datetime.min.time())
        series = {
            "signups": (User.created_at, func.count(User.id), ()),
            "logins": (LoginEvent.created_at, func.count(LoginEvent.id), ()),
            "projects": (VideoProject.created_at, func.count(VideoProject.id), ()),
            "clips": (GeneratedClip.created_at, func.count(GeneratedClip.id), ()),
            "ai_cost_usd": (LlmUsage.created_at, func.sum(LlmUsage.cost_usd), ()),
            "revenue": (PaymentTransaction.verified_at, func.sum(PaymentTransaction.amount), _approved_payments()),
        }
        result: dict[str, dict[date, float]] = {}
        for field, (column, value, conditions) in series.items():
            day = cast(column, Date)
            stmt = select(day, value).where(column >= since, *conditions).group_by(day)
            result[field] = {d: float(v or 0) for d, v in (await self._session.execute(stmt)).all()}
        active = (
            select(UserActivityDay.day, func.count(UserActivityDay.user_id))
            .where(UserActivityDay.day >= first_day)
            .group_by(UserActivityDay.day)
        )
        result["active_users"] = {d: float(n) for d, n in (await self._session.execute(active)).all()}
        return result

    async def count_users(self) -> int:
        return int((await self._session.execute(select(func.count(User.id)))).scalar_one())

    async def count_paid_users(self) -> int:
        now = datetime.utcnow()
        paid = _paid_subscriptions(now).where(UserSubscription.current_period_start <= now).subquery()
        stmt = select(func.count(func.distinct(paid.c.user_id)))
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_pending_payments(self) -> int:
        stmt = select(func.count(PaymentTransaction.id)).where(PaymentTransaction.status == PaymentStatus.PENDING)
        return int((await self._session.execute(stmt)).scalar_one())

    async def revenue_since(self, since: datetime, currency: str) -> float:
        stmt = select(func.coalesce(func.sum(PaymentTransaction.amount), 0)).where(
            PaymentTransaction.status == PaymentStatus.SUCCESS,
            PaymentTransaction.currency == currency,
            PaymentTransaction.verified_at >= since,
        )
        return float((await self._session.execute(stmt)).scalar_one())
