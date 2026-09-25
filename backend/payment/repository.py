from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, cast, func, or_, select, update, desc

from auth.model import User
from subscription.model import BillingPeriod, PaymentStatus, PaymentTransaction
from subscription.repository import PaymentTransactionRepository


class ManualPaymentRepository(PaymentTransactionRepository):
    """Payment transactions submitted with UPI proof and reviewed by an admin."""

    async def create(
        self,
        user_id: str,
        plan_id: str,
        amount: float,
        currency: str,
        utr_number: str,
        screenshot_key: str,
        payment_method: str,
        plan_type: BillingPeriod,
    ) -> PaymentTransaction:
        tx = PaymentTransaction(
            user_id=user_id,
            plan_id=plan_id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.PENDING,
            payment_uuid=str(uuid4()),
            payment_method=payment_method,
            utr_number=utr_number,
            screenshot_key=screenshot_key,
            plan_type=plan_type,
        )
        self._session.add(tx)
        await self._session.commit()
        await self._session.refresh(tx)
        return tx

    async def get_by_id(self, tx_id: str) -> PaymentTransaction | None:
        # populate_existing: reload after resolve_pending, whose bulk UPDATE
        # bypasses any copy already in the session.
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def utr_exists(self, utr_number: str) -> bool:
        stmt = select(PaymentTransaction.id).where(PaymentTransaction.utr_number == utr_number)
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def count_created_since(self, user_id: str, since: datetime) -> int:
        stmt = select(func.count(PaymentTransaction.id)).where(
            PaymentTransaction.user_id == user_id,
            PaymentTransaction.created_at >= since,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def search(
        self,
        status: PaymentStatus | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[PaymentTransaction]:
        """Transactions for the admin review list, newest first.

        ``query`` matches the UTR, the payer's email or name, or the amount.
        """
        stmt = select(PaymentTransaction).join(User, User.id == PaymentTransaction.user_id)
        if status:
            stmt = stmt.where(PaymentTransaction.status == status)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    PaymentTransaction.utr_number.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                    cast(PaymentTransaction.amount, String).ilike(pattern),
                )
            )
        stmt = stmt.order_by(desc(PaymentTransaction.created_at)).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_pending(
        self,
        tx_id: str,
        status: PaymentStatus,
        verified_by: str,
        rejection_reason: str | None = None,
    ) -> bool:
        """Move a PENDING transaction to its final status. Does not commit.

        The status check is in the UPDATE itself, so two admins acting at once
        cannot both resolve it: the loser matches no row and gets False.
        """
        stmt = (
            update(PaymentTransaction)
            .where(PaymentTransaction.id == tx_id, PaymentTransaction.status == PaymentStatus.PENDING)
            .values(
                status=status,
                verified_by=verified_by,
                verified_at=datetime.utcnow(),
                rejection_reason=rejection_reason,
                updated_at=datetime.utcnow(),
            )
            .returning(PaymentTransaction.id)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
