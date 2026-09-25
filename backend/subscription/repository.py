from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from subscription.model import Plan, UserSubscription, PaymentTransaction, CreditLedger, PlanSlug, SubscriptionStatus, PaymentStatus
from core.logging_config import get_logger

log = get_logger(__name__)


async def _save(session: AsyncSession, obj: object, commit: bool) -> None:
    """Commit and reload ``obj``, or only flush it when the caller owns the transaction."""
    if commit:
        await session.commit()
        await session.refresh(obj)
    else:
        await session.flush()


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.price_monthly)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: PlanSlug | str) -> Plan | None:
        stmt = select(Plan).where(Plan.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, plan_id: str) -> Plan | None:
        stmt = select(Plan).where(Plan.id == plan_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class UserSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_user(self, user_id: str) -> UserSubscription | None:
        stmt = (
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end > datetime.utcnow(),
            )
            .order_by(desc(UserSubscription.created_at))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: str) -> list[UserSubscription]:
        stmt = (
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .order_by(desc(UserSubscription.created_at))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, user_id: str, plan_id: str, period_start: datetime, period_end: datetime, commit: bool = True) -> UserSubscription:
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        self._session.add(sub)
        await _save(self._session, sub, commit)
        return sub

    async def cancel(self, subscription_id: str) -> UserSubscription | None:
        stmt = select(UserSubscription).where(UserSubscription.id == subscription_id)
        result = await self._session.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = datetime.utcnow()
            await self._session.commit()
            await self._session.refresh(sub)
        return sub


class PaymentTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: str) -> list[PaymentTransaction]:
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(desc(PaymentTransaction.created_at))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CreditLedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_balance(self, user_id: str) -> int:
        stmt = (
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id)
            .order_by(desc(CreditLedger.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()
        return entry.balance_after if entry else 0

    async def get_balance_at_time(self, user_id: str, at: datetime) -> int:
        stmt = (
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id, CreditLedger.created_at <= at)
            .order_by(desc(CreditLedger.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()
        return entry.balance_after if entry else 0

    async def add_entry(self, user_id: str, amount: int, balance_after: int, reason: str, reference_id: str | None = None, reference_type: str | None = None, commit: bool = True, created_by: str | None = None) -> CreditLedger:
        entry = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=balance_after,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
            created_by=created_by,
        )
        self._session.add(entry)
        await _save(self._session, entry, commit)
        return entry

    async def get_history(self, user_id: str, limit: int = 50) -> list[CreditLedger]:
        stmt = (
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id)
            .order_by(desc(CreditLedger.created_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_reference_type(
        self, reference_type: str, query: str | None, limit: int, offset: int
    ) -> list[CreditLedger]:
        """Entries of one kind, newest first; ``query`` matches the user's email or name."""
        stmt = select(CreditLedger).where(CreditLedger.reference_type == reference_type)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.join(User, User.id == CreditLedger.user_id).where(
                or_(User.email.ilike(pattern), User.full_name.ilike(pattern))
            )
        stmt = stmt.order_by(desc(CreditLedger.created_at)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
