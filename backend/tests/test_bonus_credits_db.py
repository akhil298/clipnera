"""Bonus credits (referral rewards) expire grant by grant, are spent before the
credits that last longer, survive plan resets and go back where they came from."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from billing_db import balance, maker, new_user, requires_db  # noqa: F401  maker is a fixture (imports main first)
import subscription.repository
import subscription.service
from subscription.service import SubscriptionService

pytestmark = requires_db

_real_datetime = datetime


@pytest.fixture
def clock(monkeypatch):
    """Shift "now" for the credit code. ``clock["delta"] = timedelta(days=31)``."""
    state = {"delta": timedelta(0)}

    class _Shifted(_real_datetime):
        @classmethod
        def utcnow(cls):
            return _real_datetime.utcnow() + state["delta"]

    for module in (subscription.service, subscription.repository):
        monkeypatch.setattr(module, "datetime", _Shifted)
    return state


async def _grant(maker, user_id: str, amount: int, days: int):
    async with maker() as session:
        return await SubscriptionService.for_session(session).grant_bonus_credits(
            user_id, amount, days, "test", f"{amount} bonus credits"
        )


async def _summary(maker, user_id: str):
    async with maker() as session:
        return await SubscriptionService.for_session(session).get_plan_summary(user_id)


async def _spend(maker, user_id: str, amount: int, reference_id: str):
    async with maker() as session:
        return await SubscriptionService.for_session(session).deduct_credits(user_id, amount, "run", reference_id)


async def _refund(maker, user_id: str, amount: int, reference_id: str):
    async with maker() as session:
        return await SubscriptionService.for_session(session).refund_credits(user_id, amount, "failed", reference_id)


@pytest.mark.asyncio
async def test_a_grant_adds_to_the_balance_and_shows_when_it_expires(maker, clock):
    user_id = await new_user(maker, "a@example.com")
    start = await balance(maker, user_id)

    await _grant(maker, user_id, 150, 30)
    await _grant(maker, user_id, 100, 10)

    summary = await _summary(maker, user_id)
    assert summary.credit_minutes_remaining == start + 250
    assert summary.bonus_credits_remaining == 250
    assert summary.bonus_credits_expiring == 100
    assert abs(summary.bonus_credits_expiring_at - (_real_datetime.utcnow() + timedelta(days=10))) < timedelta(minutes=1)


@pytest.mark.asyncio
async def test_credits_that_expire_soonest_are_spent_first(maker, clock):
    user_id = await new_user(maker, "b@example.com")
    plan = await balance(maker, user_id)  # resets in 30 days
    soon = await _grant(maker, user_id, 10, 5)
    late = await _grant(maker, user_id, 10, 40)

    await _spend(maker, user_id, 12, "p1")  # all of "soon", then plan credits
    async with maker() as session:
        repo = subscription.repository.CreditLedgerRepository(session)
        assert (await repo.get_grant(soon.id)).remaining == 0
        assert (await repo.get_grant(late.id)).remaining == 10
        assert (await repo.get_latest_balances(user_id)).plan == plan - 2


@pytest.mark.asyncio
async def test_leftover_bonus_credits_expire_once(maker, clock):
    user_id = await new_user(maker, "c@example.com")
    start = await balance(maker, user_id)
    await _grant(maker, user_id, 100, 30)
    await _spend(maker, user_id, start + 40, "p1")  # plan credits first, then 40 bonus

    clock["delta"] = timedelta(days=30, minutes=1)
    for _ in range(2):
        async with maker() as session:
            await SubscriptionService.for_session(session).expire_bonus_credits(user_id)

    summary = await _summary(maker, user_id)
    assert summary.bonus_credits_remaining == 0
    # Only the plan's new cycle is left: the 60 unspent bonus credits are gone.
    assert summary.credit_minutes_remaining == start


@pytest.mark.asyncio
async def test_a_plan_reset_keeps_bonus_credits(maker, clock):
    user_id = await new_user(maker, "d@example.com")
    start = await balance(maker, user_id)
    await _grant(maker, user_id, 100, 45)
    await _spend(maker, user_id, start, "p1")  # the plan credits only

    clock["delta"] = timedelta(days=31)
    summary = await _summary(maker, user_id)
    assert summary.bonus_credits_remaining == 100
    assert summary.credit_minutes_remaining == start + 100


@pytest.mark.asyncio
async def test_a_refund_goes_back_to_the_grant_it_came_from(maker, clock):
    user_id = await new_user(maker, "e@example.com")
    start = await balance(maker, user_id)
    grant = await _grant(maker, user_id, 50, 2)
    await _spend(maker, user_id, 30, "p1")  # 30 of the grant, which expires before the plan resets

    await _refund(maker, user_id, 30, "p1")
    async with maker() as session:
        assert (await subscription.repository.CreditLedgerRepository(session).get_grant(grant.id)).remaining == 50
    assert await balance(maker, user_id) == start + 50


@pytest.mark.asyncio
async def test_a_refund_after_the_grant_expired_is_kept_for_a_grace_period(maker, clock):
    user_id = await new_user(maker, "f@example.com")
    grant = await _grant(maker, user_id, 50, 2)
    await _spend(maker, user_id, 30, "p1")

    clock["delta"] = timedelta(days=3)
    await _refund(maker, user_id, 30, "p1")

    summary = await _summary(maker, user_id)
    assert summary.bonus_credits_remaining == 30
    grace = _real_datetime.utcnow() + clock["delta"] + timedelta(days=3)
    assert abs(summary.bonus_credits_expiring_at - grace) < timedelta(minutes=1)
    async with maker() as session:
        assert (await subscription.repository.CreditLedgerRepository(session).get_grant(grant.id)).expired_at is None


@pytest.mark.asyncio
async def test_voiding_a_grant_takes_back_only_what_is_left(maker, clock):
    user_id = await new_user(maker, "g@example.com")
    start = await balance(maker, user_id)
    grant = await _grant(maker, user_id, 50, 2)
    await _spend(maker, user_id, 20, "p1")

    async with maker() as session:
        taken = await SubscriptionService.for_session(session).void_grant(grant.id, "Referral voided")
    async with maker() as session:
        again = await SubscriptionService.for_session(session).void_grant(grant.id, "Referral voided")

    assert (taken, again) == (30, 0)
    summary = await _summary(maker, user_id)
    assert summary.bonus_credits_remaining == 0
    assert summary.credit_minutes_remaining == start
