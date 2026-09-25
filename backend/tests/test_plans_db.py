"""Free vs Pro lifecycle against a real Postgres database.

Skipped unless TEST_DATABASE_URL points at a disposable database, e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/clipnera_plans_test pytest tests/test_plans_db.py

Every table in that database is dropped and recreated.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main  # noqa: F401  registers every model on Base.metadata
import admin.repository
import admin.service
import subscription.jobs as jobs
import subscription.repository
import subscription.service
from admin.repository import AdminRepository
from admin.schema import AdminUserPlanRequest
from admin.service import AdminService
from auth.model import User
from core.database import Base
from core.exceptions import CustomException
from payment.repository import ManualPaymentRepository
from payment.service import PaymentService
from subscription.model import (
    BillingPeriod,
    CreditLedger,
    PaymentStatus,
    Plan,
    PlanSlug,
    SubscriptionStatus,
    UserSubscription,
)
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")

_real_datetime = datetime


@pytest.fixture
def clock(monkeypatch):
    """Shift "now" for the plan code. ``clock["delta"] = timedelta(days=31)``."""
    state = {"delta": timedelta(0)}

    class _Shifted(_real_datetime):
        @classmethod
        def utcnow(cls):
            return _real_datetime.utcnow() + state["delta"]

    for module in (subscription.service, subscription.repository, admin.repository, admin.service):
        monkeypatch.setattr(module, "datetime", _Shifted)
    return state


@pytest_asyncio.fixture
async def db(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all(
            [
                Plan(id="plan-free", name="Free", slug=PlanSlug.FREE, credit_minutes=60, price_monthly=0),
                Plan(id="plan-pro", name="Pro", slug=PlanSlug.PRO, credit_minutes=600, price_monthly=0, price_inr=499),
                Plan(
                    id="plan-pp", name="Pro Plus", slug=PlanSlug.PRO_PLUS, credit_minutes=1200,
                    price_monthly=0, is_active=False,
                ),
            ]
        )
        await session.commit()
    # Keep the daily job off the real database.
    monkeypatch.setattr(jobs, "AsyncSessionLocal", maker)
    yield maker
    await engine.dispose()


async def _user(maker, email: str, age_days: int = 0) -> str:
    async with maker() as session:
        user = User(email=email, created_at=_real_datetime.utcnow() - timedelta(days=age_days))
        session.add(user)
        await session.commit()
        return user.id


async def _plan(maker, plan_id: str) -> Plan:
    async with maker() as session:
        return await PlanRepository(session).get_by_id(plan_id)


async def _state(maker, user_id: str) -> tuple[str, int, datetime | None]:
    """Effective plan, credit balance and paid expiry, read fresh."""
    async with maker() as session:
        summary = await SubscriptionService.for_session(session).get_plan_summary(user_id)
        return summary.entitlements.plan, summary.credit_minutes_remaining, summary.plan_expires_at


async def _pay(maker, user_id: str, period: BillingPeriod, utr: str) -> str:
    async with maker() as session:
        pro = await PlanRepository(session).get_by_slug(PlanSlug.PRO)
        tx = await ManualPaymentRepository(session).create(
            user_id=user_id, plan_id=pro.id, amount=499, currency="INR", utr_number=utr,
            screenshot_key=None, payment_method="upi_manual", plan_type=period,
        )
        return tx.id


def _payments(session) -> PaymentService:
    repo = ManualPaymentRepository(session)
    return PaymentService(repo, PlanRepository(session), SubscriptionService.for_session(session))


def _close(actual: datetime, expected: datetime) -> bool:
    return abs(actual - expected) < timedelta(minutes=1)


# New users


@pytest.mark.asyncio
async def test_new_user_starts_free_and_free_credits_cannot_be_farmed(db):
    user_id = await _user(db, "new@example.com")
    for _ in range(3):
        async with db() as session:
            await SubscriptionService.for_session(session).activate_free_plan(user_id)

    plan, balance, expires = await _state(db, user_id)
    assert (plan, balance, expires) == ("free", 60, None)


# Payments


@pytest.mark.asyncio
async def test_approval_upgrades_with_the_bought_period_and_renewals_stack(db):
    user_id = await _user(db, "payer@example.com")
    admin_id = await _user(db, "admin@example.com")

    tx_id = await _pay(db, user_id, BillingPeriod.MONTHLY, "111111111111")
    async with db() as session:
        await _payments(session).approve(tx_id, admin_id)

    plan, balance, expires = await _state(db, user_id)
    assert plan == "pro"
    assert balance == 600
    assert _close(expires, _real_datetime.utcnow() + timedelta(days=30))

    # Renewing early adds a year on top of the current end, not from today,
    # and does not reset the credits mid-cycle.
    tx_id = await _pay(db, user_id, BillingPeriod.YEARLY, "222222222222")
    async with db() as session:
        await _payments(session).approve(tx_id, admin_id)

    plan, balance, renewed = await _state(db, user_id)
    assert plan == "pro"
    assert balance == 600
    assert renewed - expires == timedelta(days=365)
    async with db() as session:
        rows = (await session.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_rejected_payment_keeps_the_user_free(db):
    user_id = await _user(db, "rejected@example.com")
    admin_id = await _user(db, "admin@example.com")
    tx_id = await _pay(db, user_id, BillingPeriod.MONTHLY, "333333333333")

    async with db() as session:
        result = await _payments(session).reject(tx_id, admin_id, "UTR not found")

    assert result.status == "rejected"
    assert result.rejection_reason == "UTR not found"
    plan, _, expires = await _state(db, user_id)
    assert (plan, expires) == ("free", None)


@pytest.mark.asyncio
async def test_pending_payment_is_reported(db):
    user_id = await _user(db, "pending@example.com")
    await _pay(db, user_id, BillingPeriod.MONTHLY, "444444444444")
    async with db() as session:
        summary = await SubscriptionService.for_session(session).get_plan_summary(user_id)
    assert summary.has_pending_payment is True
    assert summary.entitlements.plan == "free"


# Expiry


@pytest.mark.asyncio
async def test_expired_pro_is_treated_as_free_on_the_next_request(db, clock):
    user_id = await _user(db, "lapsing@example.com")
    async with db() as session:
        await SubscriptionService.for_session(session).extend_plan(user_id, await _plan(db, "plan-pro"), 30)
    assert (await _state(db, user_id))[0] == "pro"

    clock["delta"] = timedelta(days=30, minutes=1)
    plan, _, expires = await _state(db, user_id)
    assert (plan, expires) == ("free", None)
    async with db() as session:
        with pytest.raises(CustomException) as exc:
            await SubscriptionService.for_session(session).require_feature(user_id, "depth_captions")
    assert exc.value.code == "PRO_REQUIRED"

    # The daily job then records it, without being needed for the rule above.
    assert await jobs.expire_lapsed_subscriptions() == 1
    async with db() as session:
        sub = (await session.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))).scalar_one()
    assert sub.status == SubscriptionStatus.EXPIRED


# Usage limits


@pytest.mark.asyncio
async def test_free_daily_limit_applies_and_resets_next_day(db, clock):
    user_id = await _user(db, "limited@example.com")

    async def export():
        async with db() as session:
            return await SubscriptionService.for_session(session).consume_daily_quota(user_id, "exports")

    assert [await export() for _ in range(10)] == list(range(1, 11))
    with pytest.raises(CustomException) as exc:
        await export()
    assert (exc.value.code, exc.value.status_code) == ("LIMIT_REACHED", 429)

    clock["delta"] = timedelta(days=1)
    assert await export() == 1


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_overshoot_the_limit(db):
    user_id = await _user(db, "burst@example.com")

    async def export():
        async with db() as session:
            try:
                await SubscriptionService.for_session(session).consume_daily_quota(user_id, "exports")
                return True
            except CustomException:
                return False

    results = await asyncio.gather(*(export() for _ in range(15)))
    assert results.count(True) == 10


@pytest.mark.asyncio
async def test_pro_has_no_daily_limit(db):
    user_id = await _user(db, "unlimited@example.com")
    async with db() as session:
        service = SubscriptionService.for_session(session)
        await service.extend_plan(user_id, await _plan(db, "plan-pro"), 30)
        counts = [await service.consume_daily_quota(user_id, "exports", 5) for _ in range(5)]
    assert counts[-1] == 25


# Credit cycles


@pytest.mark.asyncio
async def test_credit_reset_is_idempotent_and_does_not_roll_over(db, clock):
    user_id = await _user(db, "cycles@example.com")
    async with db() as session:
        service = SubscriptionService.for_session(session)
        await service.extend_plan(user_id, await _plan(db, "plan-pro"), 365)
        await service.deduct_credits(user_id, 100, "render")
    assert (await _state(db, user_id))[1] == 500

    # Same cycle: requests and repeated job runs change nothing.
    await jobs.refresh_all_credits()
    await jobs.refresh_all_credits()
    assert (await _state(db, user_id))[1] == 500

    # Next cycle, counted from the subscription start: back to 600, not 1100.
    clock["delta"] = timedelta(days=30, minutes=1)
    await jobs.refresh_all_credits()
    await jobs.refresh_all_credits()
    assert (await _state(db, user_id))[1] == 600
    async with db() as session:
        resets = (
            await session.execute(
                select(CreditLedger).where(CreditLedger.user_id == user_id, CreditLedger.reference_type == "credit_refill")
            )
        ).scalars().all()
    assert len(resets) == 2  # activation + one cycle


@pytest.mark.asyncio
async def test_free_credits_reset_every_30_days_from_signup(db, clock):
    user_id = await _user(db, "free-cycle@example.com")
    async with db() as session:
        service = SubscriptionService.for_session(session)
        await service.activate_free_plan(user_id)
        await service.deduct_credits(user_id, 50, "render")
    assert (await _state(db, user_id))[1] == 10

    clock["delta"] = timedelta(days=29)
    assert (await _state(db, user_id))[1] == 10
    clock["delta"] = timedelta(days=30, minutes=1)
    assert (await _state(db, user_id))[1] == 60


# Pro Plus


@pytest.mark.asyncio
async def test_pro_plus_subscriber_buying_pro_is_queued_after_their_period(db, clock):
    user_id = await _user(db, "legacy@example.com")
    now = _real_datetime.utcnow()
    async with db() as session:
        session.add(
            UserSubscription(
                id="sub-pp", user_id=user_id, plan_id="plan-pp", status=SubscriptionStatus.ACTIVE,
                current_period_start=now - timedelta(days=5), current_period_end=now + timedelta(days=25),
            )
        )
        await session.commit()
        await SubscriptionService.for_session(session).extend_plan(user_id, await _plan(db, "plan-pro"), 30)

    plan, _, expires = await _state(db, user_id)
    assert plan == "pro_plus"
    assert _close(expires, now + timedelta(days=55))
    async with db() as session:
        pp = await session.get(UserSubscription, "sub-pp")
    assert (pp.status, pp.current_period_end) == (SubscriptionStatus.ACTIVE, now + timedelta(days=25))

    clock["delta"] = timedelta(days=25, minutes=1)
    plan, balance, _ = await _state(db, user_id)
    assert (plan, balance) == ("pro", 600)


# Admin


@pytest.mark.asyncio
async def test_admin_can_grant_extend_and_revoke_pro(db):
    user_id = await _user(db, "gift@example.com")

    async def set_plan(plan: str, days: int | None = None):
        async with db() as session:
            service = AdminService(AdminRepository(session), PlanRepository(session), SubscriptionService.for_session(session))
            return await service.set_plan(user_id, AdminUserPlanRequest(plan=plan, days=days), "admin-1")

    granted = await set_plan("pro", 10)
    assert granted.plan == "pro"
    assert _close(granted.plan_expires_at, _real_datetime.utcnow() + timedelta(days=10))

    extended = await set_plan("pro", 5)
    assert extended.plan_expires_at - granted.plan_expires_at == timedelta(days=5)

    async with db() as session:
        listed = await AdminService(
            AdminRepository(session), PlanRepository(session), SubscriptionService.for_session(session)
        ).list_users("gift@", 10, 0)
    assert [(u.email, u.plan) for u in listed] == [("gift@example.com", "pro")]

    revoked = await set_plan("free")
    assert (revoked.plan, revoked.plan_expires_at) == ("free", None)
    assert (await _state(db, user_id))[1] == 60


@pytest.mark.asyncio
async def test_admin_overview_counts_plans_and_revenue(db):
    free_id = await _user(db, "f@example.com")
    pro_id = await _user(db, "p@example.com")
    tx_id = await _pay(db, pro_id, BillingPeriod.YEARLY, "555555555555")
    await _pay(db, free_id, BillingPeriod.MONTHLY, "666666666666")
    async with db() as session:
        await _payments(session).approve(tx_id, free_id)

    async with db() as session:
        overview = await AdminService(
            AdminRepository(session), PlanRepository(session), SubscriptionService.for_session(session)
        ).overview()
    assert (overview.total_users, overview.free_users, overview.pro_users) == (2, 1, 1)
    assert overview.pending_payments == 1
    assert overview.revenue_this_month == 499.0
