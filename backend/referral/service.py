"""The referral program.

A referral's progress is never pushed into it by the events it depends on.
Instead ``evaluate`` reads the payments and pipeline runs behind it and works
out where it stands, under a row lock, and pays whatever it has earned. So it
can be run any number of times, from anywhere: right after a payment is
approved or a run finishes, when either side opens their page, and from the
periodic sweep that catches anything those missed. Each reward is unique per
referral and kind in the database, so nothing is ever paid twice.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import User
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from feature_flags.registry import REFERRAL_PROGRAM
from feature_flags.service import FeatureFlagService
from notifications.service import notify_referral
from referral.model import (
    OPEN_STATUSES,
    FailReason,
    Referral,
    ReferralReward,
    ReferralSettings,
    ReferralSettingsChange,
    ReferralStatus,
    ReviewState,
    RewardKind,
)
from referral.repository import ReferralRepository
from referral.rules import (
    REMINDER_BEFORE,
    RUN_FINISH_GRACE,
    SHARED_IP_LOOKBACK,
    Rules,
    display_name,
    email_hash,
    mask_email,
    month_start_utc,
    new_code,
    normalize_code,
    normalize_email,
)
from referral.schema import (
    AdminReferralResponse,
    AdminReferralSettingsResponse,
    InvitedByResponse,
    MyReferralsResponse,
    ReferralItemResponse,
    ReferralRewardResponse,
    ReferralRulesResponse,
    ReferralSettingsChangeResponse,
    ReferralSettingsRequest,
    ReferralStatsResponse,
    ValidateCodeResponse,
)
from subscription.model import CreditGrant, PaymentStatus
from subscription.service import SubscriptionService

log = get_logger(__name__)

# Notifications are sent only after the change they describe is committed.
Notice = Callable[[], Awaitable[None]]

_REWARD_LABELS = {
    RewardKind.REFEREE_PRO.value: "for buying Pro",
    RewardKind.REFERRER_PRO.value: "bought Pro",
    RewardKind.REFERRER_VIDEO.value: "processed their first video",
}
_FAIL_MESSAGES = {
    FailReason.PRO_NOT_BOUGHT.value: "Pro wasn't bought within the time limit.",
    FailReason.PAYMENT_REJECTED.value: "The Pro payment was rejected.",
    FailReason.APPROVAL_TIMEOUT.value: "The Pro payment wasn't approved in time.",
    FailReason.NO_VIDEO.value: "No video was processed within the time limit.",
    FailReason.PAYMENT_REVERSED.value: "The Pro payment was reversed, so its rewards were taken back.",
    FailReason.ACCOUNT_DELETED.value: "The account was deleted.",
    FailReason.REFERRER_UNAVAILABLE.value: "The referrer's account is no longer active.",
    FailReason.VOIDED_BY_ADMIN.value: "This referral was cancelled after a review.",
}
_LIST_LIMIT = 200


def _rules_response(rules: Rules) -> ReferralRulesResponse:
    return ReferralRulesResponse(**rules.to_dict())


def _reward_response(reward: ReferralReward, grant: CreditGrant) -> ReferralRewardResponse:
    return ReferralRewardResponse(
        kind=reward.kind, credits=reward.credits, granted_at=reward.created_at, expires_at=grant.expires_at
    )


def _refused(message: str) -> CustomException:
    return CustomException(message=message, code="REFERRAL_CODE_INVALID", status_code=400)


class ReferralService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ReferralRepository(session)
        self._subscriptions = SubscriptionService.for_session(session)
        self._flags = FeatureFlagService(session)

    # Settings

    async def rules(self) -> Rules:
        row = await self._repo.settings()
        return Rules.from_row(row) if row else Rules()

    async def enabled(self) -> bool:
        return await self._flags.is_enabled(REFERRAL_PROGRAM)

    async def admin_settings(self) -> AdminReferralSettingsResponse:
        row = await self._repo.settings()
        return AdminReferralSettingsResponse(
            rules=_rules_response(await self.rules()),
            updated_at=row.updated_at if row else None,
            history=[
                ReferralSettingsChangeResponse(admin_email=email, changes=change.changes, created_at=change.created_at)
                for change, email in await self._repo.settings_changes(20)
            ],
        )

    async def update_settings(self, body: ReferralSettingsRequest, admin_id: str) -> AdminReferralSettingsResponse:
        """Change the rules for referrals that start from now on, recording what changed."""
        before = (await self.rules()).to_dict()
        after = body.model_dump()
        changes = {key: {"from": before[key], "to": value} for key, value in after.items() if before[key] != value}
        if changes:
            row = await self._repo.settings() or ReferralSettings(id=1)
            for key, value in after.items():
                setattr(row, key, value)
            row.updated_by, row.updated_at = admin_id, datetime.utcnow()
            await self._repo.save_settings(row, ReferralSettingsChange(admin_id=admin_id, changes=changes))
            log.info(f"Referral settings changed by admin={admin_id}: {changes}")
        return await self.admin_settings()

    # Codes

    async def code_for(self, user_id: str) -> str:
        """The user's code, made on first use."""
        for _ in range(5):
            if existing := await self._repo.code_of(user_id):
                return existing.code
            try:
                return (await self._repo.add_code(user_id, new_code())).code
            except IntegrityError:
                # Another request made it, or the random code was taken: look again.
                await self._repo.rollback()
        raise CustomException(message="Could not create a referral code. Please try again.", code="CODE_FAILED")

    async def can_use_code(self, user: User) -> bool:
        """Whether this account may still join through a code (codes are for
        brand-new accounts, before the time to buy Pro has run out)."""
        rules = await self.rules()
        return (
            await self.enabled()
            and datetime.utcnow() <= user.created_at + rules.pro_window
            and await self._repo.for_referee(user.id) is None
        )

    async def _check_code(self, user: User, raw_code: str) -> tuple[str, User]:
        """The referrer behind ``raw_code`` if ``user`` may use it, else a 400
        saying why. Run again under the locks when the code is attached."""
        if not await self.enabled():
            raise _refused("Referrals are paused right now.")
        code = normalize_code(raw_code)
        row = await self._repo.find_code(code)
        referrer = await self._repo.user(row.user_id) if row else None
        if not referrer or not referrer.is_active:
            raise _refused("That referral code doesn't exist.")
        if referrer.id == user.id or normalize_email(referrer.email) == normalize_email(user.email):
            raise _refused("You can't use your own referral code.")
        rules = await self.rules()
        if datetime.utcnow() > user.created_at + rules.pro_window:
            raise _refused("Referral codes can only be used by new accounts.")
        if await self._repo.for_referee(user.id):
            raise _refused("You've already used a referral code.")
        if await self._repo.email_was_referred(email_hash(user.email)):
            raise _refused("This email address has already been referred before.")
        if await self._repo.count_since(referrer.id, month_start_utc(datetime.utcnow())) >= rules.monthly_cap:
            raise _refused("This code has reached its limit for this month. Try again next month.")
        return code, referrer

    async def validate(self, user_id: str, raw_code: str) -> ValidateCodeResponse:
        user = await self._repo.user(user_id)
        if not user:
            raise CustomException(message="User not found", code="NOT_FOUND", status_code=404)
        try:
            _, referrer = await self._check_code(user, raw_code)
        except CustomException as exc:
            return ValidateCodeResponse(valid=False, reason=exc.message)
        rules = await self.rules()
        return ValidateCodeResponse(
            valid=True,
            referrer_name=display_name(referrer.full_name, referrer.email),
            bonus_credits=rules.referee_pro_credits,
            pro_window_hours=rules.pro_window_hours,
            bonus_expiry_days=rules.bonus_expiry_days,
        )

    async def attach(self, user: User, raw_code: str) -> tuple[Referral, list[Notice]]:
        """Start a referral for a new user. Only flushed: the caller commits it
        together with the rest of the onboarding form."""
        _, referrer = await self._check_code(user, raw_code)
        # The monthly cap and "one code per account" are checked again under
        # locks, so two sign-ups at once cannot both take the last place.
        await self._repo.lock(f"referrer:{referrer.id}")
        await self._repo.lock(f"referee:{user.id}")
        code, referrer = await self._check_code(user, raw_code)

        rules = await self.rules()
        flagged = await self._shared_ip_reason(user.id, referrer.id)
        referral = Referral(
            referrer_id=referrer.id,
            referee_id=user.id,
            code=code,
            referee_name=display_name(user.full_name, user.email),
            referee_email_masked=mask_email(user.email),
            status=ReferralStatus.PENDING_PRO.value,
            rules=rules.to_dict(),
            signed_up_at=user.created_at,
            pro_deadline_at=user.created_at + rules.pro_window,
            review_state=ReviewState.HELD.value if flagged else ReviewState.CLEAR.value,
            flagged_reason=flagged,
        )
        await self._repo.add(referral)
        await self._repo.remember_email(email_hash(user.email))
        log.info(f"Referral started: referral={referral.id} referrer={referrer.id} referee={user.id} held={bool(flagged)}")

        referrer_label = display_name(referrer.full_name, referrer.email)
        hours = rules.pro_window_hours
        notices = [
            lambda: notify_referral(
                user.id,
                f"Invited by {referrer_label}",
                f"Buy Pro within {hours} hours of signing up to get {rules.referee_pro_credits} bonus credits.",
            ),
            lambda: notify_referral(
                referrer.id,
                "Someone joined with your code",
                f"{referral.referee_name} signed up. You earn {rules.referrer_pro_credits} credits if they buy Pro "
                f"within {hours} hours, and {rules.referrer_video_credits} more for their first video after that.",
            ),
        ]
        return referral, notices

    async def _shared_ip_reason(self, referee_id: str, referrer_id: str) -> str | None:
        """Why this sign-up looks like the referrer's own second account, if it does."""
        since = datetime.utcnow() - SHARED_IP_LOOKBACK
        ips = await self._repo.login_ips(referee_id, since)
        if ips & await self._repo.login_ips(referrer_id, since):
            return "Signed up from an IP address the referrer also uses"
        if ips & await self._repo.other_referee_ips(referrer_id, referee_id, since):
            return "Signed up from the same IP address as another of this referrer's sign-ups"
        return None

    # Progress

    async def refresh_open(self, user_id: str) -> None:
        """Bring the user's open referrals up to date before showing them, so a
        deadline that passed shows as passed even if the sweep has not run yet."""
        for referral_id in await self._repo.open_ids_for(user_id):
            await self.evaluate(referral_id)

    async def evaluate(self, referral_id: str) -> None:
        """Bring one referral up to date and pay what it has earned. Idempotent."""
        referral = await self._repo.get(referral_id, for_update=True)
        if not referral:
            return
        notices: list[Notice] = []
        if referral.status in {s.value for s in OPEN_STATUSES}:
            notices += await self._advance(referral, datetime.utcnow())
        notices += await self._pay_earned(referral)
        await self._repo.commit()
        for notice in notices:
            await notice()

    async def _advance(self, referral: Referral, now: datetime) -> list[Notice]:
        rules = Rules.from_dict(referral.rules)
        referee = await self._repo.user(referral.referee_id)
        referrer = await self._repo.user(referral.referrer_id)
        if referee is None:
            ended = ReferralStatus.PARTIAL if referral.pro_activated_at else ReferralStatus.FAILED
            return self._end(referral, ended, FailReason.ACCOUNT_DELETED, now)
        if referrer is None or not referrer.is_active:
            return self._end(referral, ReferralStatus.VOID, FailReason.REFERRER_UNAVAILABLE, now)

        notices: list[Notice] = []
        if referral.status != ReferralStatus.PENDING_VIDEO.value:
            notices += await self._advance_pro(referral, rules, now)
        if referral.status == ReferralStatus.PENDING_VIDEO.value:
            notices += await self._advance_video(referral, rules, now)
        return notices

    async def _advance_pro(self, referral: Referral, rules: Rules, now: datetime) -> list[Notice]:
        # A payment counts when it was submitted in time and approved within the
        # wait allowed for approval: an admin's delay is not the user's fault.
        on_time = [p for p in await self._repo.pro_payments(referral.referee_id) if p.created_at <= referral.pro_deadline_at]
        approval_cutoff = referral.pro_deadline_at + rules.approval_wait
        approved = next(
            (p for p in on_time if p.status == PaymentStatus.SUCCESS and p.verified_at and p.verified_at <= approval_cutoff),
            None,
        )
        if approved:
            referral.pro_payment_id = approved.id
            referral.pro_submitted_at = approved.created_at
            referral.pro_activated_at = approved.verified_at
            referral.video_deadline_at = approved.verified_at + rules.video_window
            referral.status = ReferralStatus.PENDING_VIDEO.value
            return []

        pending = any(p.status == PaymentStatus.PENDING for p in on_time)
        if now <= referral.pro_deadline_at:
            referral.status = (ReferralStatus.AWAITING_APPROVAL if pending else ReferralStatus.PENDING_PRO).value
            return self._remind_pro(referral, rules, now)
        if pending and now <= approval_cutoff:
            referral.status = ReferralStatus.AWAITING_APPROVAL.value
            return []
        if pending or any(p.status == PaymentStatus.SUCCESS for p in on_time):
            reason = FailReason.APPROVAL_TIMEOUT
        elif any(p.status == PaymentStatus.REJECTED for p in on_time):
            reason = FailReason.PAYMENT_REJECTED
        else:
            reason = FailReason.PRO_NOT_BOUGHT
        return self._end(referral, ReferralStatus.FAILED, reason, now)

    async def _advance_video(self, referral: Referral, rules: Rules, now: datetime) -> list[Notice]:
        # Runs that start inside the window count, even if they finish after it.
        runs = await self._repo.runs_started_between(
            referral.referee_id, referral.pro_activated_at, referral.video_deadline_at, rules.min_video_seconds
        )
        done = next(((state, project) for state, project in runs if state.is_completed and not state.error), None)
        if done:
            state, project = done
            referral.video_project_id = project.id
            referral.video_started_at = state.created_at
            referral.video_completed_at = state.updated_at
            return self._end(referral, ReferralStatus.SUCCEEDED, None, now)

        live = [
            state for state, _ in runs
            if not state.is_completed and not state.error and not state.cancel_requested
            and now <= referral.video_deadline_at + RUN_FINISH_GRACE
        ]
        referral.video_started_at = live[0].created_at if live else None
        if now > referral.video_deadline_at and not live:
            return self._end(referral, ReferralStatus.PARTIAL, FailReason.NO_VIDEO, now)
        return self._remind_video(referral, now)

    def _remind_pro(self, referral: Referral, rules: Rules, now: datetime) -> list[Notice]:
        if referral.pro_reminder_sent_at or referral.status != ReferralStatus.PENDING_PRO.value:
            return []
        if now < referral.pro_deadline_at - REMINDER_BEFORE:
            return []
        referral.pro_reminder_sent_at = now
        referee_id = referral.referee_id
        return [lambda: notify_referral(
            referee_id,
            "Your referral bonus ends soon",
            f"Buy Pro before your sign-up bonus window closes to get {rules.referee_pro_credits} bonus credits.",
        )]

    def _remind_video(self, referral: Referral, now: datetime) -> list[Notice]:
        if referral.video_reminder_sent_at or referral.video_started_at:
            return []
        if now < referral.video_deadline_at - REMINDER_BEFORE:
            return []
        referral.video_reminder_sent_at = now
        referee_id = referral.referee_id
        return [lambda: notify_referral(
            referee_id, "Process your first video", "Start processing a video soon to complete your referral."
        )]

    def _end(self, referral: Referral, status: ReferralStatus, reason: FailReason | None, now: datetime) -> list[Notice]:
        referral.status = status.value
        referral.fail_reason = reason.value if reason else None
        referral.ended_at = now
        log.info(f"Referral ended: referral={referral.id} status={status.value} reason={referral.fail_reason}")
        if status in (ReferralStatus.SUCCEEDED, ReferralStatus.VOID) or reason is None:
            return []
        message = _FAIL_MESSAGES[reason.value]
        title = "Referral ended" if status == ReferralStatus.FAILED else "Referral partly completed"
        return [
            (lambda user_id=user_id: notify_referral(user_id, title, f"{referral.referee_name}: {message}"))
            for user_id in (referral.referrer_id, referral.referee_id)
            if user_id
        ]

    # Rewards

    async def _pay_earned(self, referral: Referral) -> list[Notice]:
        """Grant every reward the referral has reached and not yet received."""
        if (
            referral.status == ReferralStatus.VOID.value
            or referral.fail_reason == FailReason.PAYMENT_REVERSED.value
            or referral.review_state == ReviewState.HELD.value
            or not referral.pro_activated_at
        ):
            return []
        rules = Rules.from_dict(referral.rules)
        # The referred user first, then the referrer: the same order everywhere,
        # so two referrals paying at once take the users' balance locks in turn.
        earned = [
            (RewardKind.REFEREE_PRO, referral.referee_id, rules.referee_pro_credits),
            (RewardKind.REFERRER_PRO, referral.referrer_id, rules.referrer_pro_credits),
        ]
        if referral.status == ReferralStatus.SUCCEEDED.value:
            earned.append((RewardKind.REFERRER_VIDEO, referral.referrer_id, rules.referrer_video_credits))

        paid = {reward.kind for reward, _ in await self._repo.rewards([referral.id])}
        notices: list[Notice] = []
        for kind, recipient_id, credits in earned:
            if kind.value in paid or not recipient_id or credits <= 0:
                continue
            reason = (
                f"Referral bonus {_REWARD_LABELS[kind.value]}"
                if kind == RewardKind.REFEREE_PRO
                else f"Referral reward: {referral.referee_name} {_REWARD_LABELS[kind.value]}"
            )
            grant = await self._subscriptions.grant_bonus_credits(
                recipient_id, credits, rules.bonus_expiry_days, f"referral_{kind.value}", reason,
                reference_id=referral.id, commit=False,
            )
            await self._repo.add_reward(ReferralReward(
                referral_id=referral.id, recipient_id=recipient_id, kind=kind.value, credits=credits, grant_id=grant.id
            ))
            log.info(f"Referral reward paid: referral={referral.id} kind={kind.value} user={recipient_id} credits={credits}")
            expires = f"{grant.expires_at:%d %b %Y}"
            notices.append(
                lambda recipient_id=recipient_id, credits=credits, reason=reason, expires=expires: notify_referral(
                    recipient_id, f"+{credits} bonus credits", f"{reason}. They expire on {expires}.", reward=True
                )
            )
        return notices

    async def _take_back_rewards(self, referral: Referral, reason: str) -> None:
        for reward, grant in await self._repo.rewards([referral.id]):
            await self._subscriptions.void_grant(grant.id, reason, commit=False)

    async def reverse_pro(self, referee_id: str) -> None:
        """The referred user's Pro was revoked: the referral fails and the unspent
        part of its rewards is taken back."""
        found = await self._repo.for_referee(referee_id)
        referral = await self._repo.get(found.id, for_update=True) if found else None
        if (
            not referral
            or not referral.pro_activated_at
            or referral.status == ReferralStatus.VOID.value
            or referral.fail_reason == FailReason.PAYMENT_REVERSED.value
        ):
            return
        await self._take_back_rewards(referral, "Referral reward taken back: the Pro payment was reversed")
        notices = self._end(referral, ReferralStatus.FAILED, FailReason.PAYMENT_REVERSED, datetime.utcnow())
        await self._repo.commit()
        for notice in notices:
            await notice()

    # Admin

    async def admin_list(
        self, status: str | None, review_state: str | None, query: str | None, limit: int, offset: int
    ) -> list[AdminReferralResponse]:
        rows = await self._repo.admin_search(status, review_state, (query or "").strip() or None, limit, offset)
        rewards = await self._rewards_by_referral([referral.id for referral, _, _ in rows])
        return [
            AdminReferralResponse(
                id=referral.id,
                referrer_id=referral.referrer_id,
                referrer_email=referrer_email,
                referee_id=referral.referee_id,
                referee_email=referee_email,
                referee_name=referral.referee_name,
                code=referral.code,
                status=referral.status,
                fail_reason=referral.fail_reason,
                review_state=referral.review_state,
                flagged_reason=referral.flagged_reason,
                signed_up_at=referral.signed_up_at,
                pro_deadline_at=referral.pro_deadline_at,
                pro_activated_at=referral.pro_activated_at,
                video_deadline_at=referral.video_deadline_at,
                video_completed_at=referral.video_completed_at,
                rewards=rewards.get(referral.id, []),
                created_at=referral.created_at,
            )
            for referral, referrer_email, referee_email in rows
        ]

    async def _admin_referral(self, referral_id: str) -> Referral:
        referral = await self._repo.get(referral_id, for_update=True)
        if not referral:
            raise CustomException(message="Referral not found", code="NOT_FOUND", status_code=404)
        return referral

    async def admin_approve(self, referral_id: str, admin_id: str) -> None:
        """Clear a held referral: what it has earned is paid now, the rest as it comes."""
        referral = await self._admin_referral(referral_id)
        if referral.review_state != ReviewState.HELD.value:
            raise CustomException(message="This referral is not on hold", code="NOT_HELD", status_code=409)
        referral.review_state = ReviewState.APPROVED.value
        referral.reviewed_by, referral.reviewed_at = admin_id, datetime.utcnow()
        await self._repo.commit()
        log.info(f"Referral approved: referral={referral_id} by={admin_id}")
        await self.evaluate(referral_id)

    async def admin_void(self, referral_id: str, admin_id: str, reason: str) -> None:
        """End a referral for abuse, taking back what is left of its rewards."""
        referral = await self._admin_referral(referral_id)
        if referral.status == ReferralStatus.VOID.value:
            raise CustomException(message="This referral is already void", code="ALREADY_VOID", status_code=409)
        await self._take_back_rewards(referral, f"Referral reward taken back: {reason.strip()}")
        referral.reviewed_by, referral.reviewed_at = admin_id, datetime.utcnow()
        self._end(referral, ReferralStatus.VOID, FailReason.VOIDED_BY_ADMIN, datetime.utcnow())
        await self._repo.commit()
        log.info(f"Referral voided: referral={referral_id} by={admin_id} reason={reason.strip()}")
        message = _FAIL_MESSAGES[FailReason.VOIDED_BY_ADMIN.value]
        for user_id in (referral.referrer_id, referral.referee_id):
            if user_id:
                await notify_referral(user_id, "Referral cancelled", f"{referral.referee_name}: {message}")

    # Pages

    async def _rewards_by_referral(
        self, referral_ids: list[str], recipient_id: str | None = None
    ) -> dict[str, list[ReferralRewardResponse]]:
        grouped: dict[str, list[ReferralRewardResponse]] = {}
        for reward, grant in await self._repo.rewards(referral_ids):
            if recipient_id is None or reward.recipient_id == recipient_id:
                grouped.setdefault(reward.referral_id, []).append(_reward_response(reward, grant))
        return grouped

    async def my_referrals(self, user_id: str) -> MyReferralsResponse:
        enabled = await self.enabled()
        rules = await self.rules()
        referrals = await self._repo.for_referrer(user_id, _LIST_LIMIT)
        # The referrer only sees their own rewards, not what the other side got.
        rewards = await self._rewards_by_referral([r.id for r in referrals], recipient_id=user_id)
        statuses = [r.status for r in referrals]
        code = await self.code_for(user_id) if enabled else None
        return MyReferralsResponse(
            enabled=enabled,
            code=code,
            share_url=f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/?ref={code}" if code else None,
            rules=_rules_response(rules),
            used_this_month=await self._repo.count_since(user_id, month_start_utc(datetime.utcnow())),
            stats=ReferralStatsResponse(
                invited=len(referrals),
                in_progress=sum(s in {o.value for o in OPEN_STATUSES} for s in statuses),
                succeeded=statuses.count(ReferralStatus.SUCCEEDED.value),
                partial=statuses.count(ReferralStatus.PARTIAL.value),
                failed=statuses.count(ReferralStatus.FAILED.value) + statuses.count(ReferralStatus.VOID.value),
                credits_earned=sum(r.credits for items in rewards.values() for r in items),
            ),
            referrals=[
                ReferralItemResponse(
                    id=r.id,
                    name=r.referee_name,
                    email_masked=r.referee_email_masked,
                    status=r.status,
                    fail_reason=r.fail_reason,
                    signed_up_at=r.signed_up_at,
                    pro_deadline_at=r.pro_deadline_at,
                    pro_activated_at=r.pro_activated_at,
                    video_deadline_at=r.video_deadline_at,
                    video_completed_at=r.video_completed_at,
                    on_hold=r.review_state == ReviewState.HELD.value,
                    rewards=rewards.get(r.id, []),
                    rules=_rules_response(Rules.from_dict(r.rules)),
                )
                for r in referrals
            ],
        )

    async def invited_by(self, user_id: str) -> InvitedByResponse | None:
        referral = await self._repo.for_referee(user_id)
        if not referral:
            return None
        referrer = await self._repo.user(referral.referrer_id)
        rewards = (await self._rewards_by_referral([referral.id], recipient_id=user_id)).get(referral.id, [])
        return InvitedByResponse(
            referrer_name=display_name(referrer.full_name, referrer.email) if referrer else "A former member",
            status=referral.status,
            fail_reason=referral.fail_reason,
            signed_up_at=referral.signed_up_at,
            pro_deadline_at=referral.pro_deadline_at,
            pro_activated_at=referral.pro_activated_at,
            video_deadline_at=referral.video_deadline_at,
            bonus_credits=Rules.from_dict(referral.rules).referee_pro_credits,
            reward=rewards[0] if rewards else None,
        )


# Entry points for other modules. Each runs in its own session and never
# raises: a referral problem must not fail the payment or run that triggered
# it, and the periodic sweep retries whatever these miss.


async def refresh_referrals_of(user_id: str) -> None:
    """Re-check the open referrals the user is on either side of."""
    try:
        async with AsyncSessionLocal() as session:
            referral_ids = await ReferralRepository(session).open_ids_for(user_id)
    except Exception:
        log.exception("Could not look up referrals: user=%s", user_id)
        return
    await refresh_referrals(referral_ids)


async def refresh_referrals(referral_ids: list[str]) -> None:
    for referral_id in referral_ids:
        async with AsyncSessionLocal() as session:
            try:
                await ReferralService(session).evaluate(referral_id)
            except Exception:
                await session.rollback()
                log.exception("Referral check failed: referral=%s", referral_id)


async def reverse_referral_pro(referee_id: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await ReferralService(session).reverse_pro(referee_id)
        except Exception:
            await session.rollback()
            log.exception("Referral reversal failed: user=%s", referee_id)


async def referral_ids_of(user_id: str) -> list[str]:
    """Every referral the user is on either side of; empty if that cannot be
    read, so it never stops what asked (deleting the account)."""
    try:
        async with AsyncSessionLocal() as session:
            return await ReferralRepository(session).ids_for(user_id)
    except Exception:
        log.exception("Could not look up referrals: user=%s", user_id)
        return []


async def sweep_open_referrals(batch: int = 200) -> int:
    """Re-check every open referral: deadlines that passed, reminders due, and
    rewards a missed event never triggered. Returns how many were checked."""
    async with AsyncSessionLocal() as session:
        referral_ids = await ReferralRepository(session).open_ids(batch)
    await refresh_referrals(referral_ids)
    return len(referral_ids)
