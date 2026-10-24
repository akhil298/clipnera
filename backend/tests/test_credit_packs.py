from __future__ import annotations

from types import SimpleNamespace

import pytest

import payment.service as payment_service
from payment.service import PaymentService
from core.exceptions import CustomException
from subscription.entitlements import CREDIT_PACKS, PLAN_PRICES, BillingPeriod
from subscription.repository import Balances
from subscription.service import CREDIT_PACK_REFERENCE, InsufficientCreditsError, SubscriptionService


class _Ledger:
    """In-memory ledger holding the total and the bought part, like the real rows."""

    def __init__(self, balance: int = 0, purchased: int = 0) -> None:
        self.balance = balance
        self.purchased = purchased
        self.entries: list[dict] = []

    async def get_latest_balance(self, user_id):
        return self.balance

    async def lock_user(self, user_id):
        pass

    async def get_latest_balances(self, user_id):
        return Balances(self.balance, self.purchased)

    async def purchased_spent(self, user_id, reference_id):
        return -sum(e["purchased_amount"] for e in self.entries if e["reference_id"] == reference_id)

    async def grants_spent(self, user_id, reference_id):
        return []

    async def open_grants(self, user_id, now):
        return []

    async def due_grants(self, user_id, now):
        return []

    async def add_entry(self, **fields):
        self.entries.append(fields)
        self.balance = fields["balances_after"].total
        self.purchased = fields["balances_after"].purchased
        after = fields["balances_after"]
        return SimpleNamespace(
            id=f"entry-{len(self.entries)}", balance_after=after.total, purchased_balance_after=after.purchased, **fields
        )


class _NoSubscription:
    async def get_active_by_user(self, user_id):
        return None

    async def get_account_created_at(self, user_id):
        return None


def _service(ledger: _Ledger, monkeypatch) -> SubscriptionService:
    service = SubscriptionService(None, _NoSubscription(), None, ledger)

    async def no_reset(user_id, commit=True):
        return False

    monkeypatch.setattr(service, "refresh_credits", no_reset)
    return service


def test_packs_cost_more_per_credit_than_pro():
    pro = PLAN_PRICES[BillingPeriod.MONTHLY].amount_usd / 600
    for pack in CREDIT_PACKS.values():
        assert pack.amount_usd / pack.credits > pro, pack.slug


@pytest.mark.asyncio
async def test_plan_credits_are_spent_before_bought_ones(monkeypatch):
    ledger = _Ledger(balance=100, purchased=60)  # 40 plan + 60 bought
    service = _service(ledger, monkeypatch)

    await service.deduct_credits("u", 30, "run", reference_id="p1")
    assert (ledger.balance, ledger.purchased) == (70, 60)

    await service.deduct_credits("u", 30, "run", reference_id="p2")
    assert (ledger.balance, ledger.purchased) == (40, 40)
    assert ledger.entries[-1]["purchased_amount"] == -20


@pytest.mark.asyncio
async def test_deduct_refuses_more_than_the_total(monkeypatch):
    service = _service(_Ledger(balance=10, purchased=5), monkeypatch)
    with pytest.raises(InsufficientCreditsError):
        await service.deduct_credits("u", 11, "run")


@pytest.mark.asyncio
async def test_refund_returns_bought_credits_to_the_bought_part(monkeypatch):
    ledger = _Ledger(balance=50, purchased=40)  # 10 plan + 40 bought
    service = _service(ledger, monkeypatch)

    await service.deduct_credits("u", 30, "run", reference_id="p1")  # 10 plan, 20 bought
    await service.refund_credits("u", 30, "failed", reference_id="p1")
    assert (ledger.balance, ledger.purchased) == (50, 40)


@pytest.mark.asyncio
async def test_other_entries_carry_the_bought_part_forward(monkeypatch):
    ledger = _Ledger(balance=30, purchased=25)
    service = _service(ledger, monkeypatch)

    await service.topup_credits("u", 10, "gift")
    assert (ledger.balance, ledger.purchased) == (40, 25)


@pytest.mark.asyncio
async def test_grant_purchased_credits(monkeypatch):
    ledger = _Ledger(balance=20, purchased=0)
    await _service(ledger, monkeypatch).grant_purchased_credits("u", 200, "Bought 200 credits", reference_id="tx-1")

    [entry] = ledger.entries
    assert entry["balances_after"] == Balances(220, 200)
    assert entry["reference_type"] == CREDIT_PACK_REFERENCE


class _Subscriptions:
    def __init__(self) -> None:
        self.granted: list[tuple] = []
        self.extended: list[tuple] = []

    async def grant_purchased_credits(self, user_id, amount, reason, reference_id, commit=True):
        self.granted.append((user_id, amount, reference_id, commit))

    async def extend_plan(self, user_id, plan, days, commit=True):
        self.extended.append((user_id, plan, days))


class _Txs:
    def __init__(self, tx) -> None:
        self.tx = tx
        self.committed = False

    async def get_by_id(self, tx_id):
        return self.tx

    async def resolve_pending(self, tx_id, status, **fields):
        return True

    async def commit(self):
        self.committed = True


def _payment_service(tx, subscriptions) -> PaymentService:
    service = PaymentService(_Txs(tx), None, subscriptions)

    async def admin_view(tx_id):
        return tx_id

    service.get_for_admin = admin_view
    return service


@pytest.fixture(autouse=True)
def _no_referral_checks(monkeypatch):
    async def skip(user_id):
        pass

    monkeypatch.setattr(payment_service, "refresh_referrals_of", skip)


@pytest.mark.asyncio
async def test_approving_a_credit_pack_grants_its_credits():
    tx = SimpleNamespace(id="tx-1", user_id="u", credit_pack="creator", credits=200, plan=None, plan_type=None)
    subscriptions = _Subscriptions()
    service = _payment_service(tx, subscriptions)

    await service.approve("tx-1", "admin")

    assert subscriptions.granted == [("u", 200, "tx-1", False)]
    assert subscriptions.extended == []
    assert service._tx_repo.committed


def test_unknown_credit_pack_is_refused(monkeypatch):
    service = _payment_service(None, _Subscriptions())
    monkeypatch.setattr(service._settings, "UPI_ID", "shop@upi")
    with pytest.raises(CustomException) as exc:
        service._get_credit_pack("mega")
    assert exc.value.code == "CREDIT_PACK_NOT_FOUND"
