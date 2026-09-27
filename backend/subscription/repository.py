from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4
from sqlalchemy import select, desc, or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from subscription.model import Plan, UserSubscription, PaymentTransaction, CreditLedger, PlanSlug, SubscriptionStatus, PaymentStatus, UsageTracking
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
        """The subscription in force right now. A period queued to start later
        (a renewal bought while another plan runs) is not active yet."""
        now = datetime.utcnow()
        stmt = (
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.current_period_start <= now,
                UserSubscription.current_period_end > now,
            )
            .order_by(desc(UserSubscription.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_by_user(self, user_id: str) -> list[UserSubscription]:
        """Active subscriptions that have not ended, including queued ones,
        latest-ending first."""
        stmt = (
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end > datetime.utcnow(),
            )
            .order_by(desc(UserSubscription.current_period_end))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def expire_lapsed(self) -> int:
        """Mark active subscriptions whose period has ended as expired."""
        stmt = (
            update(UserSubscription)
            .where(
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end <= datetime.utcnow(),
            )
            .values(status=SubscriptionStatus.EXPIRED, updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

    async def get_account(self, user_id: str) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_account_created_at(self, user_id: str) -> datetime | None:
        result = await self._session.execute(select(User.created_at).where(User.id == user_id))
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

    async def has_pending(self, user_id: str) -> bool:
        """Whether a plan payment awaits approval. Credit-pack payments do not
        count: they change no plan, so nothing should say activation is pending."""
        stmt = select(PaymentTransaction.id).where(
            PaymentTransaction.user_id == user_id,
            PaymentTransaction.status == PaymentStatus.PENDING,
            PaymentTransaction.plan_id.is_not(None),
        )
        result = await self._session.execute(stmt.limit(1))
        return result.first() is not None

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

    async def _latest_entry(self, user_id: str) -> CreditLedger | None:
        stmt = (
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id)
            .order_by(desc(CreditLedger.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_balance(self, user_id: str) -> int:
        entry = await self._latest_entry(user_id)
        return entry.balance_after if entry else 0

    async def get_latest_balances(self, user_id: str) -> tuple[int, int]:
        """The total balance and the bought part of it."""
        entry = await self._latest_entry(user_id)
        return (entry.balance_after, entry.purchased_balance_after) if entry else (0, 0)

    async def get_latest_charge(self, user_id: str, reference_id: str) -> CreditLedger | None:
        """The newest deduction made for ``reference_id``."""
        stmt = (
            select(CreditLedger)
            .where(
                CreditLedger.user_id == user_id,
                CreditLedger.reference_id == reference_id,
                CreditLedger.amount < 0,
            )
            .order_by(desc(CreditLedger.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def add_entry(self, user_id: str, amount: int, balance_after: int, purchased_balance_after: int, reason: str, reference_id: str | None = None, reference_type: str | None = None, commit: bool = True, created_by: str | None = None, purchased_amount: int = 0) -> CreditLedger:
        entry = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=balance_after,
            purchased_balance_after=purchased_balance_after,
            purchased_amount=purchased_amount,
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


_USAGE_CONSTRAINT = "uq_usage_tracking_user_feature_period"


class UsageRepository:
    """Per-user counters keyed by feature and period (see UsageTracking)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _insert(self, user_id: str, feature_key: str, period_start: date, count: int):
        now = datetime.utcnow()
        return pg_insert(UsageTracking).values(
            id=str(uuid4()),
            user_id=user_id,
            feature_key=feature_key,
            count=count,
            period_start=period_start,
            created_at=now,
            updated_at=now,
        )

    async def claim(self, user_id: str, feature_key: str, period_start: date) -> bool:
        """Record that something happened once for this period. Does not commit.

        True for the first caller only; any repeat, even a concurrent one, hits
        the unique constraint and gets False.
        """
        stmt = (
            self._insert(user_id, feature_key, period_start, 1)
            .on_conflict_do_nothing(constraint=_USAGE_CONSTRAINT)
            .returning(UsageTracking.id)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def increment(
        self, user_id: str, feature_key: str, period_start: date, amount: int, limit: int | None
    ) -> int | None:
        """Add ``amount`` to the counter and commit; the new count, or None if
        that would exceed ``limit``. Checked and applied in one statement, so
        concurrent requests cannot overshoot the limit together."""
        if limit is not None and amount > limit:
            return None
        stmt = self._insert(user_id, feature_key, period_start, amount)
        new_count = UsageTracking.count + amount
        stmt = stmt.on_conflict_do_update(
            constraint=_USAGE_CONSTRAINT,
            set_={"count": new_count, "updated_at": datetime.utcnow()},
            where=(new_count <= limit) if limit is not None else None,
        ).returning(UsageTracking.count)
        result = await self._session.execute(stmt)
        row = result.first()
        await self._session.commit()
        return row[0] if row else None

    async def get_counts(self, user_id: str, feature_keys: list[str], period_start: date) -> dict[str, int]:
        stmt = select(UsageTracking.feature_key, UsageTracking.count).where(
            UsageTracking.user_id == user_id,
            UsageTracking.feature_key.in_(feature_keys),
            UsageTracking.period_start == period_start,
        )
        result = await self._session.execute(stmt)
        counts = {key: 0 for key in feature_keys}
        counts.update({key: count for key, count in result.all()})
        return counts

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
