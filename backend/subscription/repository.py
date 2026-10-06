from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import NamedTuple
from uuid import uuid4
from sqlalchemy import select, desc, func, or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from subscription.model import (
    CreditGrant,
    CreditGrantSpend,
    CreditLedger,
    PaymentStatus,
    PaymentTransaction,
    Plan,
    PlanSlug,
    SubscriptionStatus,
    UsageTracking,
    UserSubscription,
)
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


class Balances(NamedTuple):
    """A user's credit balance and the parts of it that outlive a cycle reset."""

    total: int
    purchased: int = 0
    bonus: int = 0

    @property
    def plan(self) -> int:
        """The plan allowance part, which the next reset replaces."""
        return max(0, self.total - self.purchased - self.bonus)


def _open_grant(now: datetime):
    """Grants with credits left that can still be spent."""
    return (
        CreditGrant.remaining > 0,
        CreditGrant.expired_at.is_(None),
        CreditGrant.voided_at.is_(None),
        CreditGrant.expires_at > now,
    )


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

    async def get_latest_balances(self, user_id: str) -> Balances:
        entry = await self._latest_entry(user_id)
        if not entry:
            return Balances(0)
        return Balances(entry.balance_after, entry.purchased_balance_after, entry.bonus_balance_after)

    async def lock_user(self, user_id: str) -> None:
        """Hold the user's balance until this transaction ends, so two changes made
        at once cannot both read the same balance and spend the same credits."""
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(user_id))))

    async def net_charged(self, user_id: str, reference_id: str, reference_types: tuple[str, ...]) -> int:
        """Credits taken for ``reference_id`` minus those given back for it."""
        stmt = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
            CreditLedger.user_id == user_id,
            CreditLedger.reference_id == reference_id,
            CreditLedger.reference_type.in_(reference_types),
        )
        return -int((await self._session.execute(stmt)).scalar_one())

    async def purchased_spent(self, user_id: str, reference_id: str) -> int:
        """Bought credits the entries for ``reference_id`` used and did not give back."""
        stmt = select(func.coalesce(func.sum(CreditLedger.purchased_amount), 0)).where(
            CreditLedger.user_id == user_id, CreditLedger.reference_id == reference_id
        )
        return max(0, -int((await self._session.execute(stmt)).scalar_one()))

    async def grants_spent(self, user_id: str, reference_id: str) -> list[tuple[CreditGrant, int]]:
        """Each grant the entries for ``reference_id`` used and did not give back,
        with how much, latest-expiring first."""
        spent = func.sum(CreditGrantSpend.amount)
        stmt = (
            select(CreditGrant, spent)
            .join(CreditGrantSpend, CreditGrantSpend.grant_id == CreditGrant.id)
            .join(CreditLedger, CreditLedger.id == CreditGrantSpend.ledger_id)
            .where(CreditLedger.user_id == user_id, CreditLedger.reference_id == reference_id)
            .group_by(CreditGrant.id)
            .having(spent > 0)
            .order_by(desc(CreditGrant.expires_at))
        )
        return [(grant, int(amount)) for grant, amount in (await self._session.execute(stmt)).all()]

    async def open_grants(self, user_id: str, now: datetime) -> list[CreditGrant]:
        """Spendable grants, soonest to expire first."""
        stmt = (
            select(CreditGrant)
            .where(CreditGrant.user_id == user_id, *_open_grant(now))
            .order_by(CreditGrant.expires_at, CreditGrant.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def due_grants(self, user_id: str, now: datetime) -> list[CreditGrant]:
        """Grants past their expiry whose leftover has not been removed yet."""
        stmt = select(CreditGrant).where(
            CreditGrant.user_id == user_id,
            CreditGrant.expires_at <= now,
            CreditGrant.expired_at.is_(None),
            CreditGrant.voided_at.is_(None),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def users_with_due_grants(self, now: datetime) -> list[str]:
        stmt = select(CreditGrant.user_id).distinct().where(
            CreditGrant.expires_at <= now, CreditGrant.expired_at.is_(None), CreditGrant.voided_at.is_(None)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def refresh(self, obj: object) -> None:
        await self._session.refresh(obj)

    async def get_grant(self, grant_id: str) -> CreditGrant | None:
        return await self._session.get(CreditGrant, grant_id)

    async def add_grant(self, grant: CreditGrant) -> CreditGrant:
        self._session.add(grant)
        await self._session.flush()
        return grant

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

    async def add_entry(
        self,
        user_id: str,
        amount: int,
        balances_after: Balances,
        reason: str,
        reference_id: str | None = None,
        reference_type: str | None = None,
        commit: bool = True,
        created_by: str | None = None,
        purchased_amount: int = 0,
        bonus_amount: int = 0,
        grant_spends: list[tuple[CreditGrant, int]] = (),
    ) -> CreditLedger:
        """Write a ledger entry, with how much of each grant it used (positive)
        or gave back (negative); the grants' ``remaining`` is changed to match."""
        entry = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=balances_after.total,
            purchased_balance_after=balances_after.purchased,
            bonus_balance_after=balances_after.bonus,
            purchased_amount=purchased_amount,
            bonus_amount=bonus_amount,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
            created_by=created_by,
        )
        self._session.add(entry)
        await self._session.flush()
        for grant, used in grant_spends:
            grant.remaining -= used
            self._session.add(CreditGrantSpend(ledger_id=entry.id, grant_id=grant.id, amount=used))
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
