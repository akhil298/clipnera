from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from subscription.model import PaymentStatus, PaymentTransaction, Plan, PlanSlug, SubscriptionStatus, UserSubscription


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
        self, query: str | None, limit: int, offset: int
    ) -> list[tuple[User, str | None, datetime | None]]:
        """Users newest first, each with the paid plan in force now (or None)
        and when paid access ends."""
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
        stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [tuple(row) for row in result.all()]

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
