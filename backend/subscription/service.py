from __future__ import annotations

import math
from datetime import datetime, timedelta
from uuid import uuid4

from subscription.model import Plan, UserSubscription, PaymentTransaction, CreditLedger, PlanSlug, SubscriptionStatus, PaymentStatus
from subscription.entitlements import Entitlements, entitlements_for
from subscription.repository import (
    PlanRepository,
    UserSubscriptionRepository,
    PaymentTransactionRepository,
    CreditLedgerRepository,
)
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger

log = get_logger(__name__)


def pro_override_emails() -> frozenset[str]:
    """Emails always treated as paid, from PRO_OVERRIDE_EMAILS.

    Normalised to lowercase so a case difference between the settings value and
    the stored address cannot silently drop someone from the list.
    """
    raw = getattr(get_settings(), "PRO_OVERRIDE_EMAILS", "") or ""
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())

CREDIT_COST_PER_2_MINUTES = 1


# Plans that buy the higher-quality AI path. Listed explicitly so adding a tier
# is a deliberate decision rather than anything that merely is not "free".
PAID_PLAN_SLUGS = frozenset({PlanSlug.PRO.value, PlanSlug.PRO_PLUS.value})


class SubscriptionService:
    def __init__(self, plan_repo: PlanRepository, sub_repo: UserSubscriptionRepository, tx_repo: PaymentTransactionRepository, ledger_repo: CreditLedgerRepository) -> None:
        self._plan_repo = plan_repo
        self._sub_repo = sub_repo
        self._tx_repo = tx_repo
        self._ledger_repo = ledger_repo

    async def list_plans(self) -> list[Plan]:
        return await self._plan_repo.get_all_active()

    async def get_user_subscription(self, user_id: str) -> UserSubscription | None:
        return await self._sub_repo.get_active_by_user(user_id)

    async def is_pro_user(self, user_id: str) -> bool:
        """Whether this user is on a paid plan right now.

        Decides which AI provider their runs use, so it errs toward False: a
        lookup failure or a lapsed subscription gives the free provider, which
        still produces clips, rather than silently billing paid inference to
        someone who is not paying for it.
        """
        return (await self.get_entitlements(user_id)).pro_ai_provider

    async def _is_override_user(self, user_id: str) -> bool:
        """Whether this user is on the always-pro list.

        Its own session: this runs inside request handlers that hold a session
        already busy with other work, and a failed lookup must never upgrade
        someone, so any error here resolves to False.
        """
        overrides = pro_override_emails()
        if not overrides:
            return False
        try:
            from user.repository import UserRepository

            async with AsyncSessionLocal() as session:
                user = await UserRepository(session).get_by_id(user_id)
        except Exception as exc:
            log.warning("Could not check the pro override list for user=%s (%s)", user_id, exc)
            return False

        email = (getattr(user, "email", "") or "").strip().lower()
        if email and email in overrides:
            log.info("User %s is on the pro override list; treating as %s", email, PlanSlug.PRO.value)
            return True
        return False

    async def get_user_plan_slug(self, user_id: str) -> str:
        """The user's current plan slug, or "free" when there is no active one.

        Errs toward free for the same reason is_pro_user does: a lookup failure
        must not hand out paid capabilities. The override list is the one
        deliberate exception.
        """
        if await self._is_override_user(user_id):
            return PlanSlug.PRO.value

        try:
            subscription = await self._sub_repo.get_active_by_user(user_id)
        except Exception as exc:
            log.warning("Could not read subscription for user=%s (%s); treating as free", user_id, exc)
            return PlanSlug.FREE.value
        if not subscription:
            return PlanSlug.FREE.value

        plan = await self._plan_repo.get_by_id(subscription.plan_id)
        if not plan:
            log.warning("Subscription %s references a missing plan; treating as free", subscription.id)
            return PlanSlug.FREE.value
        return str(getattr(plan.slug, "value", plan.slug))

    async def get_entitlements(self, user_id: str) -> Entitlements:
        """Capabilities this user currently has. Used by the API and enforced
        by the pipeline routes, so the UI and the server agree on one table."""
        return entitlements_for(await self.get_user_plan_slug(user_id))

    async def get_user_credit_balance(self, user_id: str) -> int:
        return await self._ledger_repo.get_latest_balance(user_id)

    async def get_user_credit_history(self, user_id: str, limit: int = 50) -> list[CreditLedger]:
        return await self._ledger_repo.get_history(user_id, limit)

    async def get_user_transactions(self, user_id: str) -> list[PaymentTransaction]:
        return await self._tx_repo.get_by_user(user_id)

    async def initiate_payment(self, user_id: str, plan_slug: str, payment_method: str | None = None, notes: str | None = None) -> PaymentTransaction:
        plan = await self._plan_repo.get_by_slug(plan_slug)
        if not plan:
            raise ValueError(f"Plan not found: {plan_slug}")

        payment_uuid = str(uuid4())
        tx = await self._tx_repo.create(
            user_id=user_id,
            plan_id=plan.id,
            amount=float(plan.price_monthly),
            currency=plan.currency,
            payment_uuid=payment_uuid,
            payment_method=payment_method,
            notes=notes,
        )
        log.info(f"Payment initiated: user={user_id} plan={plan_slug} uuid={payment_uuid}")
        return tx

    async def activate_free_plan(self, user_id: str) -> UserSubscription:
        plan = await self._plan_repo.get_by_slug(PlanSlug.FREE)
        if not plan:
            raise ValueError("Free plan not found")

        now = datetime.utcnow()
        period_end = now + timedelta(days=30)

        existing = await self._sub_repo.get_active_by_user(user_id)
        if existing:
            existing.status = SubscriptionStatus.EXPIRED
            existing.current_period_end = now

        sub = await self._sub_repo.create(user_id, plan.id, now, period_end)

        current_balance = await self._ledger_repo.get_latest_balance(user_id)
        await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=plan.credit_minutes,
            balance_after=current_balance + plan.credit_minutes,
            reason=f"Free plan activated: {plan.name}",
            reference_id=sub.id,
            reference_type="subscription",
        )
        log.info(f"Free plan activated: user={user_id} credits={plan.credit_minutes}")
        return sub

    async def verify_payment(self, payment_uuid: str, status: str, notes: str | None = None) -> PaymentTransaction | None:
        if status not in ("success", "failed"):
            raise ValueError("Status must be 'success' or 'failed'")

        payment_status = PaymentStatus.SUCCESS if status == "success" else PaymentStatus.FAILED
        tx = await self._tx_repo.update_status(payment_uuid, payment_status, notes)

        if not tx:
            return None

        if payment_status == PaymentStatus.SUCCESS:
            plan = await self._plan_repo.get_by_id(tx.plan_id)
            if not plan:
                log.error(f"Plan not found for verified payment: {tx.plan_id}")
                return tx

            now = datetime.utcnow()
            period_end = now + timedelta(days=30)

            existing = await self._sub_repo.get_active_by_user(tx.user_id)
            if existing:
                existing.status = SubscriptionStatus.EXPIRED
                existing.current_period_end = now

            await self._sub_repo.create(tx.user_id, plan.id, now, period_end)

            current_balance = await self._ledger_repo.get_latest_balance(tx.user_id)
            await self._ledger_repo.add_entry(
                user_id=tx.user_id,
                amount=plan.credit_minutes,
                balance_after=current_balance + plan.credit_minutes,
                reason=f"Subscription payment verified: {plan.name}",
                reference_id=tx.id,
                reference_type="payment_transaction",
            )
            log.info(f"Payment verified and subscription activated: user={tx.user_id} plan={plan.name} credits={plan.credit_minutes}")

        return tx

    async def deduct_credits(self, user_id: str, amount: int, reason: str, reference_id: str | None = None, reference_type: str | None = None) -> CreditLedger:
        if amount <= 0:
            raise ValueError("Credit deduction amount must be positive")

        current_balance = await self._ledger_repo.get_latest_balance(user_id)
        if current_balance < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits: required={amount}, available={current_balance}"
            )

        new_balance = current_balance - amount
        entry = await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=-amount,
            balance_after=new_balance,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        log.info(f"Credits deducted: user={user_id} amount={amount} reason={reason} balance={new_balance}")
        return entry

    async def refund_credits(self, user_id: str, amount: int, reason: str, reference_id: str | None = None, reference_type: str | None = None) -> CreditLedger:
        if amount <= 0:
            raise ValueError("Refund amount must be positive")

        current_balance = await self._ledger_repo.get_latest_balance(user_id)
        new_balance = current_balance + amount
        entry = await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        log.info(f"Credits refunded: user={user_id} amount={amount} reason={reason} balance={new_balance}")
        return entry

    async def topup_credits(self, user_id: str, amount: int, reason: str, reference_id: str | None = None, reference_type: str | None = None) -> CreditLedger:
        if amount <= 0:
            raise ValueError("Top-up amount must be positive")

        current_balance = await self._ledger_repo.get_latest_balance(user_id)
        new_balance = current_balance + amount
        entry = await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            reason=reason,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        log.info(f"Credits topped up: user={user_id} amount={amount} reason={reason} balance={new_balance}")
        return entry

    def calculate_video_credit_cost(self, duration_seconds: int) -> int:
        return max(1, math.ceil(duration_seconds / 120))


class InsufficientCreditsError(Exception):
    pass
