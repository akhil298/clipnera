from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession

from subscription.model import Plan, UserSubscription, PaymentTransaction, CreditLedger, PlanSlug, SubscriptionStatus
from subscription.entitlements import (
    CREDIT_CYCLE_DAYS,
    Entitlements,
    Feature,
    UsageKey,
    entitlements_for,
)
from subscription.repository import (
    PlanRepository,
    UserSubscriptionRepository,
    PaymentTransactionRepository,
    CreditLedgerRepository,
    UsageRepository,
)
from core.exceptions import CustomException
from core.logging_config import get_logger

log = get_logger(__name__)


CREDIT_COST_PER_2_MINUTES = 1

# Ledger reference_type for credits an admin added by hand.
ADMIN_TOPUP_REFERENCE = "admin_topup"
# Ledger reference_type for the balance being reset at the start of a cycle.
CREDIT_REFILL_REFERENCE = "credit_refill"

USAGE_KEYS: tuple[str, ...] = get_args(UsageKey)
_USAGE_LABELS = {"exports": "exports", "audio_enhancements": "audio enhancements"}
_CYCLE_SECONDS = CREDIT_CYCLE_DAYS * 24 * 60 * 60


def cycle_start(anchor: datetime, now: datetime) -> datetime:
    """Start of the credit cycle containing ``now``, counted in whole cycles
    from ``anchor``. Must match _cycle_start in the plans migration."""
    cycles = max(0, int((now - anchor).total_seconds() // _CYCLE_SECONDS))
    return anchor + timedelta(days=CREDIT_CYCLE_DAYS * cycles)


def plan_slug(plan: Plan) -> str:
    return str(getattr(plan.slug, "value", plan.slug))


def pro_required(feature: str) -> CustomException:
    return CustomException(
        message="Upgrade to Pro to use this feature.",
        code="PRO_REQUIRED",
        status_code=403,
        extra={"feature": feature},
    )


@dataclass(frozen=True)
class PlanSummary:
    """Everything the UI needs about a user's plan, from one place."""

    entitlements: Entitlements
    # When paid access ends, counting renewals queued after the current period.
    plan_expires_at: datetime | None
    current_period_end: datetime | None
    subscription_status: str
    credit_minutes_remaining: int
    next_credit_reset_at: datetime | None
    usage_today: dict[str, int]
    has_pending_payment: bool
    show_plan_notice: bool


# Plans that buy the higher-quality AI path. Listed explicitly so adding a tier
# is a deliberate decision rather than anything that merely is not "free".
PAID_PLAN_SLUGS = frozenset({PlanSlug.PRO.value, PlanSlug.PRO_PLUS.value})


class SubscriptionService:
    def __init__(self, plan_repo: PlanRepository, sub_repo: UserSubscriptionRepository, tx_repo: PaymentTransactionRepository, ledger_repo: CreditLedgerRepository, usage_repo: UsageRepository | None = None) -> None:
        self._plan_repo = plan_repo
        self._sub_repo = sub_repo
        self._tx_repo = tx_repo
        self._ledger_repo = ledger_repo
        self._usage_repo = usage_repo

    @classmethod
    def for_session(cls, session: AsyncSession) -> "SubscriptionService":
        return cls(
            PlanRepository(session),
            UserSubscriptionRepository(session),
            PaymentTransactionRepository(session),
            CreditLedgerRepository(session),
            UsageRepository(session),
        )

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

    async def get_user_plan_slug(self, user_id: str) -> str:
        """The user's current plan slug, or "free" when there is no active one.

        Errs toward free for the same reason is_pro_user does: a lookup failure
        must not hand out paid capabilities.
        """
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

    async def get_effective_plan(self, user_id: str) -> str:
        """The plan whose rules apply to this user right now.

        Paid only while a paid subscription is in force: an expired period drops
        back to free on the very next request, with no job needed. Every access
        check goes through here, via get_entitlements, never a stored plan.
        """
        return await self.get_user_plan_slug(user_id)

    async def get_entitlements(self, user_id: str) -> Entitlements:
        """Capabilities this user currently has. Used by the API and enforced
        by the pipeline routes, so the UI and the server agree on one table."""
        return entitlements_for(await self.get_effective_plan(user_id))

    async def require_feature(self, user_id: str, feature: Feature) -> Entitlements:
        """The user's entitlements, or 403 PRO_REQUIRED if they lack ``feature``."""
        entitlements = await self.get_entitlements(user_id)
        if not entitlements.allows(feature):
            raise pro_required(feature)
        return entitlements

    async def consume_daily_quota(self, user_id: str, key: UsageKey, amount: int = 1) -> int:
        """Count ``amount`` uses of ``key`` today; 429 LIMIT_REACHED if that
        would pass the plan's daily limit. Returns today's new count."""
        limit = (await self.get_entitlements(user_id)).daily_limit(key)
        count = await self._usage_repo.increment(user_id, key, datetime.utcnow().date(), amount, limit)
        if count is None:
            raise CustomException(
                message=(
                    f"You've reached today's limit of {limit} {_USAGE_LABELS[key]} on the Free plan. "
                    "Upgrade to Pro for unlimited use, or try again tomorrow."
                ),
                code="LIMIT_REACHED",
                status_code=429,
                extra={"feature": key, "limit": limit},
            )
        return count

    async def get_plan_summary(self, user_id: str) -> PlanSummary:
        await self.refresh_credits(user_id)
        entitlements = await self.get_entitlements(user_id)
        subscription = await self._sub_repo.get_active_by_user(user_id)
        paid_ends = [
            s.current_period_end
            for s in await self._sub_repo.get_open_by_user(user_id)
            if plan_slug(s.plan) != PlanSlug.FREE.value
        ]
        anchor, _ = await self._credit_cycle(user_id, subscription)
        account = await self._sub_repo.get_account(user_id)
        now = datetime.utcnow()
        return PlanSummary(
            entitlements=entitlements,
            plan_expires_at=max(paid_ends, default=None),
            current_period_end=subscription.current_period_end if subscription else None,
            subscription_status=subscription.status.value if subscription else "none",
            credit_minutes_remaining=await self._ledger_repo.get_latest_balance(user_id),
            next_credit_reset_at=(
                cycle_start(anchor, now) + timedelta(days=CREDIT_CYCLE_DAYS) if anchor else None
            ),
            usage_today=await self._usage_repo.get_counts(user_id, list(USAGE_KEYS), now.date()),
            has_pending_payment=await self._tx_repo.has_pending(user_id),
            show_plan_notice=bool(
                account and account.plan_notice_pending and entitlements.plan == PlanSlug.FREE.value
            ),
        )

    async def get_account(self, user_id: str):
        return await self._sub_repo.get_account(user_id)

    async def get_user_credit_balance(self, user_id: str) -> int:
        return await self._ledger_repo.get_latest_balance(user_id)

    async def get_user_credit_history(self, user_id: str, limit: int = 50) -> list[CreditLedger]:
        return await self._ledger_repo.get_history(user_id, limit)

    async def get_user_transactions(self, user_id: str) -> list[PaymentTransaction]:
        return await self._tx_repo.get_by_user(user_id)

    async def activate_free_plan(self, user_id: str) -> None:
        """Give a new account its first Free credits. Free needs no
        subscription row, so this only runs the (idempotent) credit reset."""
        await self.refresh_credits(user_id)

    async def _credit_cycle(
        self, user_id: str, subscription: UserSubscription | None
    ) -> tuple[datetime | None, str]:
        """The anchor date and usage key of the user's credit cycle: the paid
        subscription's start, or the signup date on Free."""
        if subscription and plan_slug(subscription.plan) != PlanSlug.FREE.value:
            return subscription.current_period_start, f"{CREDIT_REFILL_REFERENCE}:{subscription.id}"
        return await self._sub_repo.get_account_created_at(user_id), f"{CREDIT_REFILL_REFERENCE}:free"

    async def refresh_credits(self, user_id: str, commit: bool = True) -> bool:
        """Reset the balance to the plan's allowance once per credit cycle.

        Unused minutes do not roll over. Safe to call any number of times, from
        requests and the daily job at once: each cycle is claimed in
        usage_tracking under a unique key, so only the first call applies it.
        Returns whether a reset was applied.
        """
        subscription = await self._sub_repo.get_active_by_user(user_id)
        anchor, key = await self._credit_cycle(user_id, subscription)
        if anchor is None:
            return False
        start = cycle_start(anchor, datetime.utcnow())
        if not await self._usage_repo.claim(user_id, key, start.date()):
            return False

        allowance = (await self.get_entitlements(user_id)).credit_minutes
        balance = await self._ledger_repo.get_latest_balance(user_id)
        await self._ledger_repo.add_entry(
            user_id=user_id,
            amount=allowance - balance,
            balance_after=allowance,
            reason=f"Credits reset to {allowance} min for the cycle starting {start:%d %b %Y}",
            reference_id=subscription.id if subscription else None,
            reference_type=CREDIT_REFILL_REFERENCE,
            commit=commit,
        )
        log.info(f"Credits reset: user={user_id} key={key} cycle={start.date()} balance={allowance}")
        return True

    async def extend_plan(self, user_id: str, plan: Plan, days: int, commit: bool = True) -> UserSubscription:
        """Add ``days`` of ``plan`` for the user.

        Renewing the same plan extends its current end date, so paying early
        never loses time. Buying while a different paid plan is running (a Pro
        Plus subscriber buying Pro) queues the new period to start when that
        one ends, leaving its row untouched. Otherwise the plan starts now and
        its first credits are granted.

        With ``commit=False`` everything is only flushed, so the caller can make
        it part of a larger transaction (e.g. approving a payment).
        """
        now = datetime.utcnow()
        open_subs = await self._sub_repo.get_open_by_user(user_id)

        same = next((s for s in open_subs if s.plan_id == plan.id), None)
        if same:
            same.current_period_end += timedelta(days=days)
            await self._flush_or_commit(commit)
            log.info(f"Plan extended: user={user_id} plan={plan.name} days={days} until={same.current_period_end}")
            return same

        paid = [s for s in open_subs if plan_slug(s.plan) != PlanSlug.FREE.value]
        start = paid[0].current_period_end if paid else now
        if not paid:
            for legacy_free in open_subs:
                legacy_free.status = SubscriptionStatus.EXPIRED
                legacy_free.current_period_end = now

        sub = await self._sub_repo.create(user_id, plan.id, start, start + timedelta(days=days), commit=False)
        if start <= now:
            await self.refresh_credits(user_id, commit=False)
        await self._flush_or_commit(commit)
        log.info(f"Plan started: user={user_id} plan={plan.name} days={days} from={start}")
        return sub

    async def revoke_paid_plan(self, user_id: str) -> int:
        """End every paid period now, including queued ones, and cap the
        balance at the Free allowance. Returns how many periods were ended."""
        now = datetime.utcnow()
        revoked = [s for s in await self._sub_repo.get_open_by_user(user_id) if plan_slug(s.plan) != PlanSlug.FREE.value]
        for sub in revoked:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = now

        free_allowance = entitlements_for(PlanSlug.FREE.value).credit_minutes
        balance = await self._ledger_repo.get_latest_balance(user_id)
        if revoked and balance > free_allowance:
            await self._ledger_repo.add_entry(
                user_id=user_id,
                amount=free_allowance - balance,
                balance_after=free_allowance,
                reason="Pro revoked: balance capped at the Free allowance",
                reference_type=CREDIT_REFILL_REFERENCE,
                commit=False,
            )
        await self._flush_or_commit(True)
        log.info(f"Paid plan revoked: user={user_id} periods={len(revoked)}")
        return len(revoked)

    async def _flush_or_commit(self, commit: bool) -> None:
        if commit:
            await self._usage_repo.commit()

    async def deduct_credits(self, user_id: str, amount: int, reason: str, reference_id: str | None = None, reference_type: str | None = None) -> CreditLedger:
        if amount <= 0:
            raise ValueError("Credit deduction amount must be positive")

        # A new cycle may have started since the balance was last touched.
        await self.refresh_credits(user_id)
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
