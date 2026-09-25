from __future__ import annotations

import math
from datetime import datetime, timedelta

from subscription.model import Plan, UserSubscription, PaymentTransaction, CreditLedger, PlanSlug, SubscriptionStatus
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

# Ledger reference_type for credits an admin added by hand.
ADMIN_TOPUP_REFERENCE = "admin_topup"


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

    async def activate_free_plan(self, user_id: str) -> UserSubscription:
        plan = await self._plan_repo.get_by_slug(PlanSlug.FREE)
        if not plan:
            raise ValueError("Free plan not found")
        return await self.start_subscription(
            user_id,
            plan,
            reason=f"Free plan activated: {plan.name}",
            reference_type="subscription",
        )

    async def start_subscription(
        self,
        user_id: str,
        plan: Plan,
        reason: str,
        reference_type: str,
        reference_id: str | None = None,
        commit: bool = True,
    ) -> UserSubscription:
        """Replace the user's active subscription with a fresh 30-day ``plan``
        and credit its minutes.

        With ``commit=False`` everything is only flushed, so the caller can make
        it part of a larger transaction (e.g. approving a payment).
        """
        now = datetime.utcnow()
        existing = await self._sub_repo.get_active_by_user(user_id)
        if existing:
            existing.status = SubscriptionStatus.EXPIRED
            existing.current_period_end = now

        sub = await self._sub_repo.create(user_id, plan.id, now, now + timedelta(days=30), commit=commit)

        current_balance = await self._ledger_repo.get_latest_balance(user_id)
        await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=plan.credit_minutes,
            balance_after=current_balance + plan.credit_minutes,
            reason=reason,
            reference_id=reference_id or sub.id,
            reference_type=reference_type,
            commit=commit,
        )
        log.info(f"Subscription started: user={user_id} plan={plan.name} credits={plan.credit_minutes}")
        return sub

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

    async def topup_credits(self, user_id: str, amount: int, reason: str, reference_id: str | None = None, reference_type: str | None = None, created_by: str | None = None) -> CreditLedger:
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
            created_by=created_by,
        )
        log.info(f"Credits topped up: user={user_id} amount={amount} reason={reason} balance={new_balance} by={created_by}")
        return entry

    async def admin_topup(self, user_id: str, amount: int, reason: str, admin_id: str) -> CreditLedger:
        """Credit a user by hand. The ledger entry records which admin did it."""
        return await self.topup_credits(
            user_id, amount, reason, reference_type=ADMIN_TOPUP_REFERENCE, created_by=admin_id
        )

    async def list_admin_topups(self, query: str | None, limit: int, offset: int) -> list[CreditLedger]:
        return await self._ledger_repo.search_by_reference_type(ADMIN_TOPUP_REFERENCE, query, limit, offset)

    def calculate_video_credit_cost(self, duration_seconds: int) -> int:
        return max(1, math.ceil(duration_seconds / 120))


class InsufficientCreditsError(Exception):
    pass
