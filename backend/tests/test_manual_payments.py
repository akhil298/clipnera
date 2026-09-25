from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import payment.service as svc
from auth.dependencies import get_current_admin
from auth.model import UserRole
from core.exceptions import CustomException
from payment.service import (
    PaymentService,
    build_upi_uri,
    normalize_utr,
    sniff_image_type,
    validate_screenshot,
)
from subscription.model import PaymentStatus

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32


def _plan(price_inr: float | None = 2499.0, is_active: bool = True):
    return SimpleNamespace(id="plan-pro", slug="pro", name="Pro", price_inr=price_inr, is_active=is_active)


def _tx(status: PaymentStatus = PaymentStatus.PENDING):
    return SimpleNamespace(
        id="tx-1",
        user_id="user-1",
        plan=_plan(),
        amount=2499.0,
        currency="INR",
        utr_number="123456789012",
        status=status,
        rejection_reason=None,
        screenshot_key="payment-screenshots/user-1/a.png",
        verified_at=None,
        verified_by=None,
        created_at=datetime(2026, 9, 25),
        user=SimpleNamespace(email="payer@example.com", full_name="Payer", username=None),
    )


class _TxRepo:
    def __init__(self, tx=None, pending: bool = True, utr_taken: bool = False, recent: int = 0) -> None:
        self.tx = tx
        self.pending = pending
        self.utr_taken = utr_taken
        self.recent = recent
        self.resolved: list[tuple] = []
        self.created: dict | None = None
        self.commits = 0

    async def get_by_id(self, tx_id):
        return self.tx

    async def resolve_pending(self, tx_id, status, verified_by, rejection_reason=None):
        if not self.pending:
            return False
        self.resolved.append((tx_id, status, verified_by, rejection_reason))
        self.tx.status = status
        self.tx.rejection_reason = rejection_reason
        self.pending = False
        return True

    async def utr_exists(self, utr):
        return self.utr_taken

    async def count_created_since(self, user_id, since):
        return self.recent

    async def create(self, **fields):
        self.created = fields
        return _tx()

    async def commit(self):
        self.commits += 1


class _PlanRepo:
    def __init__(self, plan=None) -> None:
        self.plan = plan

    async def get_by_slug(self, slug):
        return self.plan


class _SubscriptionService:
    def __init__(self) -> None:
        self.started: list[dict] = []

    async def start_subscription(self, user_id, plan, **kwargs):
        self.started.append({"user_id": user_id, "plan": plan, **kwargs})


class _Storage:
    def __init__(self) -> None:
        self.puts: list[tuple] = []

    def put_object(self, bucket, key, body, **kwargs):
        self.puts.append((bucket, key, kwargs))

    def generate_presigned_url(self, bucket, key, expires_in=3600):
        return f"https://signed/{key}"


@pytest.fixture
def storage(monkeypatch):
    fake = _Storage()
    monkeypatch.setattr(svc, "_storage", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    fake = SimpleNamespace(
        UPI_ID="clipnera@upi",
        UPI_PAYEE_NAME="Clipnera",
        APP_NAME="Clipnera",
        PAYMENT_SUBMISSIONS_PER_HOUR=5,
        S3_BUCKET_NAME="bucket",
    )
    monkeypatch.setattr(svc, "get_settings", lambda: fake)
    return fake


def _service(tx_repo=None, plan=_plan(), subs=None) -> PaymentService:
    return PaymentService(tx_repo or _TxRepo(), _PlanRepo(plan), subs or _SubscriptionService())


def _code(exc_info) -> str:
    return exc_info.value.code


# Validation


@pytest.mark.parametrize("raw", ["123456789012", " 1234 5678 9012 "])
def test_normalize_utr_accepts_12_digits(raw):
    assert normalize_utr(raw) == "123456789012"


@pytest.mark.parametrize("raw", ["", "12345678901", "1234567890123", "12345678901A"])
def test_normalize_utr_rejects_other_shapes(raw):
    with pytest.raises(CustomException) as exc:
        normalize_utr(raw)
    assert _code(exc) == "INVALID_UTR"


@pytest.mark.parametrize("data,expected", [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")])
def test_sniff_image_type(data, expected):
    assert sniff_image_type(data) == expected


def test_screenshot_type_comes_from_bytes_not_the_claim():
    # A PNG body declared as JPEG is stored as what it really is.
    assert validate_screenshot(PNG, "image/jpeg") == "image/png"


@pytest.mark.parametrize(
    "data,declared,code",
    [
        (b"", "image/png", "INVALID_SCREENSHOT"),
        (b"%PDF-1.7 not an image", "image/png", "INVALID_SCREENSHOT"),
        (PNG, "application/pdf", "INVALID_SCREENSHOT"),
        (PNG + b"\x00" * (5 * 1024 * 1024), "image/png", "SCREENSHOT_TOO_LARGE"),
    ],
)
def test_screenshot_validation_rejects(data, declared, code):
    with pytest.raises(CustomException) as exc:
        validate_screenshot(data, declared)
    assert _code(exc) == code


def test_upi_uri_prefills_amount_in_inr():
    uri = build_upi_uri("clipnera@upi", "Clipnera Media", 2499, "Clipnera Pro")
    assert uri == "upi://pay?pa=clipnera%40upi&pn=Clipnera%20Media&am=2499.00&cu=INR&tn=Clipnera%20Pro"


# Checkout


@pytest.mark.asyncio
async def test_checkout_returns_qr_for_plan_price():
    checkout = await _service().get_checkout("pro")
    assert checkout.amount == 2499.0
    assert checkout.currency == "INR"
    assert checkout.upi_id == "clipnera@upi"
    assert "am=2499.00" in checkout.upi_uri
    assert checkout.qr_image.startswith("data:image/svg+xml")


@pytest.mark.parametrize("plan", [None, _plan(price_inr=None), _plan(price_inr=0), _plan(is_active=False)])
@pytest.mark.asyncio
async def test_checkout_refuses_plans_without_an_inr_price(plan):
    with pytest.raises(CustomException) as exc:
        await _service(plan=plan).get_checkout("pro")
    assert _code(exc) == "PLAN_NOT_PURCHASABLE"


@pytest.mark.asyncio
async def test_checkout_unavailable_without_upi_id(settings):
    settings.UPI_ID = ""
    with pytest.raises(CustomException) as exc:
        await _service().get_checkout("pro")
    assert _code(exc) == "PAYMENTS_UNAVAILABLE"


# Submission


@pytest.mark.asyncio
async def test_submit_stores_private_screenshot_and_pending_record(storage):
    repo = _TxRepo()
    result = await _service(repo).submit("user-1", "pro", "1234 5678 9012", PNG, "image/png")

    assert result.status == "pending"
    (bucket, key, kwargs) = storage.puts[0]
    assert key.startswith("payment-screenshots/user-1/") and key.endswith(".png")
    assert "ACL" not in kwargs  # never public-read
    # Amount and currency come from the plan, not from the client.
    assert repo.created["amount"] == 2499.0
    assert repo.created["currency"] == "INR"
    assert repo.created["utr_number"] == "123456789012"
    assert repo.created["screenshot_key"] == key


@pytest.mark.asyncio
async def test_submit_blocks_duplicate_utr_before_upload(storage):
    with pytest.raises(CustomException) as exc:
        await _service(_TxRepo(utr_taken=True)).submit("user-1", "pro", "123456789012", PNG, "image/png")
    assert _code(exc) == "DUPLICATE_UTR"
    assert storage.puts == []


@pytest.mark.asyncio
async def test_submit_rate_limited(storage):
    with pytest.raises(CustomException) as exc:
        await _service(_TxRepo(recent=5)).submit("user-1", "pro", "123456789012", PNG, "image/png")
    assert _code(exc) == "RATE_LIMITED"
    assert storage.puts == []


# Review


@pytest.mark.asyncio
async def test_approve_activates_plan_in_the_same_transaction(storage):
    repo, subs = _TxRepo(_tx()), _SubscriptionService()
    result = await _service(repo, subs=subs).approve("tx-1", "admin-1")

    assert repo.resolved == [("tx-1", PaymentStatus.SUCCESS, "admin-1", None)]
    assert subs.started[0]["user_id"] == "user-1"
    assert subs.started[0]["commit"] is False
    assert subs.started[0]["reference_id"] == "tx-1"
    assert repo.commits == 1
    assert result.status == "success"


@pytest.mark.asyncio
async def test_approve_twice_is_refused_and_grants_nothing(storage):
    repo, subs = _TxRepo(_tx(PaymentStatus.SUCCESS), pending=False), _SubscriptionService()
    with pytest.raises(CustomException) as exc:
        await _service(repo, subs=subs).approve("tx-1", "admin-1")
    assert _code(exc) == "PAYMENT_ALREADY_RESOLVED"
    assert subs.started == []
    assert repo.commits == 0


@pytest.mark.asyncio
async def test_reject_records_reason(storage):
    repo = _TxRepo(_tx())
    result = await _service(repo).reject("tx-1", "admin-1", "  UTR not found ")
    assert repo.resolved == [("tx-1", PaymentStatus.REJECTED, "admin-1", "UTR not found")]
    assert result.status == "rejected"
    assert result.rejection_reason == "UTR not found"


@pytest.mark.asyncio
async def test_review_of_missing_payment_is_404(storage):
    with pytest.raises(CustomException) as exc:
        await _service(_TxRepo(None)).approve("nope", "admin-1")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_response_uses_signed_screenshot_url(storage):
    result = await _service(_TxRepo(_tx())).get_for_admin("tx-1")
    assert result.screenshot_url == "https://signed/payment-screenshots/user-1/a.png"
    assert result.user_email == "payer@example.com"


# Admin guard


class _UserRepo:
    def __init__(self, user) -> None:
        self.user = user

    async def get_user_by_id(self, user_id):
        return self.user


@pytest.mark.parametrize(
    "user",
    [
        None,
        SimpleNamespace(role=UserRole.USER, is_active=True),
        SimpleNamespace(role=UserRole.ADMIN, is_active=False),
    ],
)
@pytest.mark.asyncio
async def test_admin_guard_forbids_non_admins(monkeypatch, user):
    import auth.dependencies as deps

    monkeypatch.setattr(deps, "UserRepository", lambda session: _UserRepo(user))
    with pytest.raises(CustomException) as exc:
        await get_current_admin({"user_id": "u"}, session=None)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_guard_allows_admin(monkeypatch):
    import auth.dependencies as deps

    admin = SimpleNamespace(role=UserRole.ADMIN, is_active=True)
    monkeypatch.setattr(deps, "UserRepository", lambda session: _UserRepo(admin))
    assert await get_current_admin({"user_id": "u"}, session=None) is admin
