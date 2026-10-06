"""The referral program end to end, against a real database: who may use a
code, each milestone and its deadline, every way a referral can end, and that
no reward is ever paid twice or to the wrong side."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from billing_db import maker, requires_db  # noqa: F401  maker is a fixture (imports main first)
import notifications.service
import referral.service as referral_service
from auth.model import LoginEvent, User
from clip.model import ProjectStatus, VideoProject
from core.exceptions import CustomException
from feature_flags.model import FeatureFlag
from feature_flags.registry import REFERRAL_PROGRAM
from onboarding.schema import OnboardingRequest
from onboarding.service import OnboardingService
from payment.repository import ManualPaymentRepository
from pipeline.model import PipelineState
from referral.model import Referral, ReferralReward, ReferralSettings, ReferredEmail
from referral.rules import Rules, email_hash
from referral.schema import ReferralSettingsRequest
from referral.service import ReferralService
from subscription.model import BillingPeriod, CreditGrant, PaymentStatus, PaymentTransaction
from subscription.service import SubscriptionService

pytestmark = requires_db

_real_datetime = datetime
T0 = _real_datetime.utcnow()
H = timedelta(hours=1)


@pytest.fixture(autouse=True)
def _wiring(monkeypatch, maker):
    monkeypatch.setattr(referral_service, "AsyncSessionLocal", maker)
    monkeypatch.setattr(notifications.service, "AsyncSessionLocal", maker)


@pytest.fixture
def clock(monkeypatch):
    """Move "now" for the referral code: ``clock(hours=50)``."""
    state = {"delta": timedelta(0)}

    class _Shifted(_real_datetime):
        @classmethod
        def utcnow(cls):
            return _real_datetime.utcnow() + state["delta"]

    monkeypatch.setattr(referral_service, "datetime", _Shifted)

    def set_to(hours: float) -> None:
        state["delta"] = timedelta(hours=hours)

    return set_to


@pytest_asyncio.fixture
async def program(maker):
    async with maker() as session:
        session.add(FeatureFlag(key=REFERRAL_PROGRAM, enabled=True))
        await session.commit()


async def _user(maker, email: str, name: str = "Test User", hours_old: float = 0, ip: str | None = None) -> str:
    async with maker() as session:
        user = User(email=email, full_name=name, created_at=T0 - timedelta(hours=hours_old))
        session.add(user)
        await session.flush()
        if ip:
            session.add(LoginEvent(user_id=user.id, method="google", ip=ip))
        await session.commit()
        await SubscriptionService.for_session(session).activate_free_plan(user.id)
        return user.id


async def _code(maker, user_id: str) -> str:
    async with maker() as session:
        return await ReferralService(session).code_for(user_id)


async def _join(maker, user_id: str, code: str | None):
    async with maker() as session:
        return await OnboardingService(session).complete(
            user_id, OnboardingRequest(role="youtuber", heard_from="friend", referral_code=code)
        )


async def _pair(maker, referrer_email="akhil@gmail.com", referee_email="claude@gmail.com", **referee) -> tuple[str, str, str]:
    """A referrer and a new user who joined with their code. Returns ids and the referral id."""
    referrer = await _user(maker, referrer_email, "Akhil Silveru", hours_old=24 * 90)
    referee_id = await _user(maker, referee_email, "Claude Anthropic", **referee)
    await _join(maker, referee_id, await _code(maker, referrer))
    async with maker() as session:
        referral = await session.scalar(select(Referral).where(Referral.referee_id == referee_id))
    return referrer, referee_id, referral.id


async def _admin(maker) -> str:
    return await _user(maker, f"admin-{_real_datetime.utcnow().timestamp()}@example.com", "Admin")


async def _pay(maker, user_id: str, at_hours: float, status=PaymentStatus.PENDING, verified_hours: float | None = None) -> str:
    """A Pro payment submitted ``at_hours`` after T0, optionally resolved later."""
    async with maker() as session:
        tx = await ManualPaymentRepository(session).create(
            user_id=user_id, amount=699, currency="INR", utr_number=f"UTR{_real_datetime.utcnow().timestamp()}"[:30],
            screenshot_key="k", payment_method="upi_manual", plan_id="plan-pro", plan_type=BillingPeriod.MONTHLY,
        )
        await session.execute(
            update(PaymentTransaction).where(PaymentTransaction.id == tx.id).values(
                created_at=T0 + timedelta(hours=at_hours),
                status=status,
                verified_at=T0 + timedelta(hours=verified_hours) if verified_hours is not None else None,
            )
        )
        await session.commit()
        return tx.id


async def _run(maker, user_id: str, at_hours: float, done: bool = True, error: str | None = None, seconds: int = 300) -> None:
    async with maker() as session:
        project = VideoProject(user_id=user_id, title="Talk", source_type="youtube", status=ProjectStatus.COMPLETED,
                               duration_seconds=seconds)
        session.add(project)
        await session.flush()
        started = T0 + timedelta(hours=at_hours)
        session.add(PipelineState(project_id=project.id, current_step="transcription", is_completed=done, error=error,
                                  created_at=started, updated_at=started + H))
        await session.commit()


async def _check(maker, referral_id: str) -> Referral:
    async with maker() as session:
        await ReferralService(session).evaluate(referral_id)
    async with maker() as session:
        return await session.get(Referral, referral_id)


async def _rewards(maker, referral_id: str) -> dict[str, tuple[str, int]]:
    async with maker() as session:
        rows = (await session.execute(select(ReferralReward).where(ReferralReward.referral_id == referral_id))).scalars()
        return {r.kind: (r.recipient_id, r.credits) for r in rows}


async def _bonus(maker, user_id: str) -> int:
    async with maker() as session:
        return (await SubscriptionService.for_session(session).get_plan_summary(user_id)).bonus_credits_remaining


# The whole journey


@pytest.mark.asyncio
async def test_pro_then_a_video_in_time_pays_150_to_the_new_user_and_300_to_the_referrer(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=10, status=PaymentStatus.SUCCESS, verified_hours=12)

    clock(13)
    referral = await _check(maker, referral_id)
    assert referral.status == "pending_video"
    assert referral.video_deadline_at == T0 + timedelta(hours=12 + 48)
    assert await _rewards(maker, referral_id) == {"referee_pro": (referee, 150), "referrer_pro": (referrer, 150)}

    await _run(maker, referee, at_hours=40)
    clock(42)
    referral = await _check(maker, referral_id)
    assert referral.status == "succeeded"

    # Checking again, from anywhere, never pays again.
    for _ in range(3):
        await _check(maker, referral_id)
    assert await _rewards(maker, referral_id) == {
        "referee_pro": (referee, 150), "referrer_pro": (referrer, 150), "referrer_video": (referrer, 150),
    }
    assert await _bonus(maker, referrer) == 300
    assert await _bonus(maker, referee) == 150


@pytest.mark.asyncio
async def test_rewards_expire_after_the_configured_days(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=2)
    await _check(maker, referral_id)
    async with maker() as session:
        grants = (await session.execute(select(CreditGrant).where(CreditGrant.reference_id == referral_id))).scalars().all()
    assert len(grants) == 2
    for grant in grants:
        assert abs(grant.expires_at - (_real_datetime.utcnow() + timedelta(days=30))) < timedelta(minutes=1)


# Pro milestone


@pytest.mark.asyncio
async def test_no_pro_within_48_hours_fails_with_nothing_paid(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    clock(47)
    assert (await _check(maker, referral_id)).status == "pending_pro"
    clock(49)
    referral = await _check(maker, referral_id)
    assert (referral.status, referral.fail_reason) == ("failed", "pro_not_bought")
    assert await _rewards(maker, referral_id) == {}


@pytest.mark.asyncio
async def test_paid_in_time_but_approved_late_still_counts(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    tx = await _pay(maker, referee, at_hours=47)

    clock(50)
    assert (await _check(maker, referral_id)).status == "awaiting_approval"

    async with maker() as session:
        await session.execute(update(PaymentTransaction).where(PaymentTransaction.id == tx).values(
            status=PaymentStatus.SUCCESS, verified_at=T0 + timedelta(hours=60)))
        await session.commit()
    referral = await _check(maker, referral_id)
    assert referral.status == "pending_video"
    # The video window starts when Pro actually started.
    assert referral.video_deadline_at == T0 + timedelta(hours=60 + 48)


@pytest.mark.asyncio
async def test_a_payment_made_after_the_deadline_does_not_count(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=49, status=PaymentStatus.SUCCESS, verified_hours=50)
    clock(51)
    referral = await _check(maker, referral_id)
    assert (referral.status, referral.fail_reason) == ("failed", "pro_not_bought")


@pytest.mark.asyncio
async def test_a_rejected_payment_can_be_retried_inside_the_window(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=5, status=PaymentStatus.REJECTED, verified_hours=6)
    clock(7)
    assert (await _check(maker, referral_id)).status == "pending_pro"

    await _pay(maker, referee, at_hours=20, status=PaymentStatus.SUCCESS, verified_hours=21)
    assert (await _check(maker, referral_id)).status == "pending_video"


@pytest.mark.asyncio
async def test_only_a_rejected_payment_fails_as_rejected(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=5, status=PaymentStatus.REJECTED, verified_hours=6)
    clock(49)
    referral = await _check(maker, referral_id)
    assert (referral.status, referral.fail_reason) == ("failed", "payment_rejected")


@pytest.mark.asyncio
async def test_a_payment_never_approved_fails_after_the_wait(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=40)
    clock(48 + 7 * 24 + 1)
    referral = await _check(maker, referral_id)
    assert (referral.status, referral.fail_reason) == ("failed", "approval_timeout")


@pytest.mark.asyncio
async def test_a_credit_pack_is_not_pro(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    async with maker() as session:
        tx = await ManualPaymentRepository(session).create(
            user_id=referee, amount=299, currency="INR", utr_number="UTRPACK1", screenshot_key="k",
            payment_method="upi_manual", credit_pack="creator", credits=200,
        )
        await session.execute(update(PaymentTransaction).where(PaymentTransaction.id == tx.id).values(
            status=PaymentStatus.SUCCESS, verified_at=T0 + H))
        await session.commit()
    clock(49)
    assert (await _check(maker, referral_id)).fail_reason == "pro_not_bought"


@pytest.mark.asyncio
async def test_approving_the_payment_pays_the_pro_rewards_straight_away(maker, program):
    from payment.service import PaymentService
    from subscription.repository import PlanRepository

    referrer, referee, referral_id = await _pair(maker)
    tx = await _pay(maker, referee, at_hours=0)
    admin = await _admin(maker)
    async with maker() as session:
        await PaymentService(
            ManualPaymentRepository(session), PlanRepository(session), SubscriptionService.for_session(session)
        ).approve(tx, admin)
    assert set(await _rewards(maker, referral_id)) == {"referee_pro", "referrer_pro"}


# Video milestone


@pytest.mark.asyncio
async def test_pro_without_a_video_keeps_the_first_reward(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=2)
    clock(3)
    await _check(maker, referral_id)
    clock(2 + 48 + 1)
    referral = await _check(maker, referral_id)
    assert (referral.status, referral.fail_reason) == ("partial", "no_video")
    assert set(await _rewards(maker, referral_id)) == {"referee_pro", "referrer_pro"}


@pytest.mark.asyncio
async def test_which_runs_count_for_the_video(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=10, status=PaymentStatus.SUCCESS, verified_hours=10)
    await _run(maker, referee, at_hours=5)                  # before Pro
    await _run(maker, referee, at_hours=12, seconds=30)      # shorter than a minute
    await _run(maker, referee, at_hours=13, done=False, error="failed")  # failed
    clock(20)
    assert (await _check(maker, referral_id)).status == "pending_video"

    # Started inside the window, finished after it: counts.
    await _run(maker, referee, at_hours=57, done=False)
    clock(59)
    assert (await _check(maker, referral_id)).status == "pending_video"
    async with maker() as session:
        await session.execute(update(PipelineState).where(PipelineState.created_at == T0 + timedelta(hours=57)).values(
            is_completed=True))
        await session.commit()
    assert (await _check(maker, referral_id)).status == "succeeded"


@pytest.mark.asyncio
async def test_a_run_started_after_the_window_does_not_count(maker, program, clock):
    _, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=0, status=PaymentStatus.SUCCESS, verified_hours=0)
    await _run(maker, referee, at_hours=49)
    clock(50)
    assert (await _check(maker, referral_id)).fail_reason == "no_video"


# Who may use a code


@pytest.mark.asyncio
async def test_codes_people_cannot_use(maker, program):
    referrer = await _user(maker, "akhil.s@gmail.com", "Akhil Silveru", hours_old=24 * 90)
    code = await _code(maker, referrer)

    async def refusal(email: str, hours_old: float = 0, code: str = code) -> str:
        user_id = await _user(maker, email, hours_old=hours_old)
        with pytest.raises(CustomException) as refused:
            await _join(maker, user_id, code)
        return refused.value.message

    assert "own" in await refusal("akhils+clips@gmail.com")              # the referrer's Gmail alias
    assert "new accounts" in await refusal("old@example.com", hours_old=49)
    assert "doesn't exist" in await refusal("x@example.com", code="CLIP-NOPE1")

    # Their own code, on their own account.
    async with maker() as session:
        assert (await ReferralService(session).validate(referrer, code)).valid is False

    # An email referred before (the account was deleted and made again).
    async with maker() as session:
        session.add(ReferredEmail(email_hash=email_hash("Again@Example.com")))
        await session.commit()
    assert "already been referred" in await refusal("again@example.com")


@pytest.mark.asyncio
async def test_a_refused_code_saves_nothing_so_the_form_can_be_fixed(maker, program):
    user_id = await _user(maker, "fix@example.com")
    with pytest.raises(CustomException):
        await _join(maker, user_id, "CLIP-WRONG")
    async with maker() as session:
        assert not await OnboardingService(session).is_completed(user_id)
    assert (await _join(maker, user_id, None)).referral is None


@pytest.mark.asyncio
async def test_a_code_works_once_per_account(maker, program):
    referrer, referee, _ = await _pair(maker)
    async with maker() as session:
        assert (await ReferralService(session).validate(referee, await _code(maker, referrer))).valid is False


@pytest.mark.asyncio
async def test_the_monthly_cap_holds_under_simultaneous_sign_ups(maker, program):
    referrer = await _user(maker, "akhil@gmail.com", hours_old=24 * 90)
    code = await _code(maker, referrer)
    async with maker() as session:
        session.add(ReferralSettings(id=1, **{**Rules().to_dict(), "monthly_cap": 1}))
        await session.commit()
    users = [await _user(maker, f"new{i}@example.com") for i in range(3)]

    results = await asyncio.gather(*(_join(maker, u, code) for u in users), return_exceptions=True)

    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert all("limit" in r.message for r in results if isinstance(r, CustomException))


@pytest.mark.asyncio
async def test_codes_are_refused_while_the_program_is_off(maker):
    referrer = await _user(maker, "akhil@gmail.com", hours_old=24 * 90)
    async with maker() as session:
        code = await ReferralService(session).code_for(referrer)
    user_id = await _user(maker, "new@example.com")
    with pytest.raises(CustomException) as refused:
        await _join(maker, user_id, code)
    assert "paused" in refused.value.message


@pytest.mark.asyncio
async def test_settings_changed_later_do_not_change_a_running_referral(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    admin = await _admin(maker)
    async with maker() as session:
        await ReferralService(session).update_settings(
            ReferralSettingsRequest(**{**Rules().to_dict(), "referrer_pro_credits": 500, "pro_window_hours": 2}), admin
        )
    await _pay(maker, referee, at_hours=10, status=PaymentStatus.SUCCESS, verified_hours=10)
    clock(11)
    referral = await _check(maker, referral_id)
    assert referral.status == "pending_video"  # still the 48-hour window it started with
    assert (await _rewards(maker, referral_id))["referrer_pro"] == (referrer, 150)


# Abuse and reversals


@pytest.mark.asyncio
async def test_a_sign_up_from_the_referrers_ip_is_held_until_an_admin_approves(maker, program, clock):
    referrer = await _user(maker, "akhil@gmail.com", hours_old=24 * 90, ip="49.36.1.1")
    referee = await _user(maker, "second@gmail.com", ip="49.36.1.1")
    await _join(maker, referee, await _code(maker, referrer))
    async with maker() as session:
        referral = await session.scalar(select(Referral).where(Referral.referee_id == referee))
    assert referral.review_state == "held"

    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=1)
    clock(2)
    await _check(maker, referral.id)
    assert await _rewards(maker, referral.id) == {}

    async with maker() as session:
        await ReferralService(session).admin_approve(referral.id, await _admin(maker))
    assert set(await _rewards(maker, referral.id)) == {"referee_pro", "referrer_pro"}


@pytest.mark.asyncio
async def test_a_reversed_pro_payment_takes_back_what_is_left_of_the_rewards(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=1)
    clock(2)
    await _check(maker, referral_id)
    async with maker() as session:
        await SubscriptionService.for_session(session).deduct_credits(referrer, 20 + 100, "spent some")

    await referral_service.reverse_referral_pro(referee)

    async with maker() as session:
        referral = await session.get(Referral, referral_id)
    assert (referral.status, referral.fail_reason) == ("failed", "payment_reversed")
    assert await _bonus(maker, referrer) == 0
    assert await _bonus(maker, referee) == 0
    # Nothing comes back on later checks.
    await _check(maker, referral_id)
    assert await _bonus(maker, referrer) == 0


@pytest.mark.asyncio
async def test_an_admin_void_ends_it_and_takes_back_unspent_rewards(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=1)
    clock(2)
    await _check(maker, referral_id)
    async with maker() as session:
        await ReferralService(session).admin_void(referral_id, await _admin(maker), "Same person")
    await _run(maker, referee, at_hours=3)
    referral = await _check(maker, referral_id)
    assert referral.status == "void"
    assert set(await _rewards(maker, referral_id)) == {"referee_pro", "referrer_pro"}
    assert await _bonus(maker, referrer) == 0


@pytest.mark.asyncio
async def test_deleted_accounts_end_the_referral(maker, program, clock):
    _, before_pro, early = await _pair(maker, referee_email="a@example.com")
    referrer2, after_pro, late = await _pair(maker, referrer_email="r2@gmail.com", referee_email="b@example.com")
    await _pay(maker, after_pro, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=1)
    clock(2)
    await _check(maker, late)

    for user_id in (before_pro, after_pro):
        async with maker() as session:
            await session.delete(await session.get(User, user_id))
            await session.commit()

    assert (await _check(maker, early)).status == "failed"
    referral = await _check(maker, late)
    assert (referral.status, referral.fail_reason) == ("partial", "account_deleted")
    assert await _bonus(maker, referrer2) == 150


@pytest.mark.asyncio
async def test_the_referrer_only_sees_their_own_side(maker, program, clock):
    referrer, referee, referral_id = await _pair(maker)
    await _pay(maker, referee, at_hours=1, status=PaymentStatus.SUCCESS, verified_hours=1)
    clock(2)
    async with maker() as session:
        service = ReferralService(session)
        await service.refresh_open(referrer)  # what GET /referrals/me does first
        mine = await service.my_referrals(referrer)
    [item] = mine.referrals
    assert item.name == "Claude A." and item.email_masked == "cl***@gmail.com"
    assert [r.kind for r in item.rewards] == ["referrer_pro"]
    assert mine.stats.credits_earned == 150 and mine.used_this_month == 1
    assert mine.share_url.endswith(f"/?ref={mine.code}")
