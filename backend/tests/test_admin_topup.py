from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import subscription.route as route
from auth.dependencies import get_current_admin
from core.exceptions import CustomException
from subscription.schema import CreditTopupRequest
from subscription.service import ADMIN_TOPUP_REFERENCE, SubscriptionService


class _LedgerRepo:
    def __init__(self, balance: int = 10) -> None:
        self.balance = balance
        self.entries: list[dict] = []

    async def get_latest_balance(self, user_id):
        return self.balance

    async def add_entry(self, **fields):
        self.entries.append(fields)
        return SimpleNamespace(id="entry-1", **fields)


def _service(ledger: _LedgerRepo) -> SubscriptionService:
    return SubscriptionService(None, None, None, ledger)


def _route(path: str, method: str):
    return next(r for r in route.router.routes if r.path == path and method in r.methods)


def _dependency_calls(dependant) -> set:
    calls = set()
    for dep in dependant.dependencies:
        calls.add(dep.call)
        calls |= _dependency_calls(dep)
    return calls


@pytest.mark.parametrize(("path", "method"), [("/subscription/topup", "POST"), ("/subscription/topups", "GET")])
def test_topup_routes_require_admin(path, method):
    assert get_current_admin in _dependency_calls(_route(path, method).dependant)


@pytest.mark.asyncio
async def test_admin_topup_records_who_added_it():
    ledger = _LedgerRepo(balance=10)
    await _service(ledger).admin_topup("user-1", 50, "Refund", admin_id="admin-1")

    [entry] = ledger.entries
    assert entry["user_id"] == "user-1"
    assert entry["amount"] == 50
    assert entry["balance_after"] == 60
    assert entry["created_by"] == "admin-1"
    assert entry["reference_type"] == ADMIN_TOPUP_REFERENCE


@pytest.mark.parametrize("amount", [0, -5])
def test_topup_request_rejects_non_positive_amounts(amount):
    with pytest.raises(ValidationError):
        CreditTopupRequest(user_email="a@example.com", amount=amount, reason="Refund")


def test_topup_request_requires_a_reason():
    with pytest.raises(ValidationError):
        CreditTopupRequest(user_email="a@example.com", amount=10, reason="")


class _Users:
    def __init__(self, user=None) -> None:
        self._user = user

    async def get_user_by_email(self, email):
        return self._user


@pytest.mark.asyncio
async def test_topup_for_unknown_email_is_404():
    service = SubscriptionService(None, None, None, _LedgerRepo(), user_repo=_Users())
    with pytest.raises(CustomException) as exc:
        await service.admin_topup_by_email("ghost@example.com", 10, "Refund", "admin-1")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_topup_credits_the_named_user_not_the_admin(monkeypatch):
    target = SimpleNamespace(id="user-9", email="target@example.com", full_name="Target", username=None)

    ledger = _LedgerRepo(balance=0)
    service = SubscriptionService(None, None, None, ledger, user_repo=_Users(target))

    async def _admin_topup(user_id, amount, reason, admin_id):
        entry = await SubscriptionService.admin_topup(service, user_id, amount, reason, admin_id)
        entry.user = target
        entry.creator = SimpleNamespace(email="admin@example.com")
        entry.created_at = datetime(2026, 9, 25)
        return entry

    monkeypatch.setattr(service, "admin_topup", _admin_topup)
    result = await service.admin_topup_by_email("target@example.com", 25, "  Goodwill  ", "admin-1")

    assert result.user_id == "user-9"
    assert result.amount == 25
    assert result.reason == "Goodwill"
    assert result.created_by == "admin-1"
    assert result.created_by_email == "admin@example.com"
