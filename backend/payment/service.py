from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from functools import cache
from urllib.parse import quote, urlencode
from uuid import uuid4

import segno
from sqlalchemy.exc import IntegrityError

from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from notifications.service import notify_payment_approved
from payment.repository import ManualPaymentRepository
from payment.schema import AdminPaymentResponse, PaymentResponse, UpiCheckoutResponse
from referral.service import refresh_referrals_of
from subscription.entitlements import CREDIT_PACKS, PLAN_PRICES, PURCHASABLE_PLAN, CreditPack
from subscription.model import BillingPeriod, PaymentStatus, PaymentTransaction, Plan
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService

log = get_logger(__name__)

PAYMENT_METHOD = "upi_manual"
UTR_PATTERN = re.compile(r"^\d{12}$")
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
SCREENSHOT_PREFIX = "payment-screenshots"
SCREENSHOT_URL_TTL_SECONDS = 600
IMAGE_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@cache
def _storage() -> S3:
    return S3()


def sniff_image_type(data: bytes) -> str | None:
    """The image type from the file's magic bytes, or None if not an allowed image.

    The client's Content-Type is only a claim; this is what the bytes are.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalize_utr(raw: str) -> str:
    """Strip the spaces UPI apps put in UTRs and require the 12-digit form."""
    utr = re.sub(r"\s+", "", raw or "")
    if not UTR_PATTERN.match(utr):
        raise CustomException(
            message="UTR must be the 12-digit UPI transaction reference number",
            code="INVALID_UTR",
            status_code=400,
        )
    return utr


def validate_screenshot(data: bytes, declared_type: str | None) -> str:
    """Check size and type of an uploaded screenshot; return its real MIME type."""
    if not data:
        raise CustomException(message="Payment screenshot is required", code="INVALID_SCREENSHOT", status_code=400)
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise CustomException(message="Screenshot must be 5 MB or smaller", code="SCREENSHOT_TOO_LARGE", status_code=413)
    actual_type = sniff_image_type(data)
    if actual_type is None or declared_type not in IMAGE_EXTENSIONS:
        raise CustomException(
            message="Screenshot must be a JPG, PNG or WebP image",
            code="INVALID_SCREENSHOT",
            status_code=400,
        )
    return actual_type


def build_upi_uri(upi_id: str, payee_name: str, amount: float, note: str) -> str:
    params = {"pa": upi_id, "pn": payee_name, "am": f"{amount:.2f}", "cu": "INR", "tn": note}
    return f"upi://pay?{urlencode(params, quote_via=quote)}"


class PaymentService:
    """Manual UPI payments: the user pays a VPA and uploads proof, an admin
    checks it against the bank statement and approves or rejects it."""

    def __init__(
        self,
        tx_repo: ManualPaymentRepository,
        plan_repo: PlanRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._tx_repo = tx_repo
        self._plan_repo = plan_repo
        self._subscription_service = subscription_service
        self._settings = get_settings()

    # User side

    async def get_checkout(self, plan_slug: str, plan_type: BillingPeriod) -> UpiCheckoutResponse:
        plan = await self._get_purchasable_plan(plan_slug)
        return self._checkout(
            float(PLAN_PRICES[plan_type].amount_inr),
            f"{self._settings.APP_NAME} {plan.name} {plan_type.value}",
            plan_slug=_slug(plan),
            plan_name=plan.name,
            plan_type=plan_type.value,
        )

    async def get_credit_pack_checkout(self, pack_slug: str) -> UpiCheckoutResponse:
        pack = self._get_credit_pack(pack_slug)
        return self._checkout(
            float(pack.amount_inr),
            f"{self._settings.APP_NAME} {pack.credits} credits",
            credit_pack=pack.slug,
            credits=pack.credits,
        )

    async def submit(
        self,
        user_id: str,
        plan_slug: str,
        plan_type: BillingPeriod,
        utr_number: str,
        screenshot: bytes,
        content_type: str | None,
    ) -> PaymentResponse:
        plan = await self._get_purchasable_plan(plan_slug)
        tx = await self._record_payment(
            user_id,
            utr_number,
            screenshot,
            content_type,
            plan_id=plan.id,
            plan_type=plan_type,
            # Always the server's price for this period, never the client's.
            amount=float(PLAN_PRICES[plan_type].amount_inr),
        )
        log.info(f"UPI payment submitted: user={user_id} plan={_slug(plan)} period={plan_type.value} tx={tx.id}")
        return self._to_response(tx)

    async def submit_credit_pack(
        self, user_id: str, pack_slug: str, utr_number: str, screenshot: bytes, content_type: str | None
    ) -> PaymentResponse:
        pack = self._get_credit_pack(pack_slug)
        tx = await self._record_payment(
            user_id,
            utr_number,
            screenshot,
            content_type,
            credit_pack=pack.slug,
            credits=pack.credits,
            amount=float(pack.amount_inr),
        )
        log.info(f"UPI payment submitted: user={user_id} credit_pack={pack.slug} tx={tx.id}")
        return self._to_response(tx)

    async def _record_payment(
        self, user_id: str, utr_number: str, screenshot: bytes, content_type: str | None, **purchase
    ) -> PaymentTransaction:
        """Validate the proof, store the screenshot and create the pending
        transaction for ``purchase`` (a plan period or a credit pack)."""
        utr = normalize_utr(utr_number)
        image_type = validate_screenshot(screenshot, content_type)
        await self._enforce_rate_limit(user_id)
        if await self._tx_repo.utr_exists(utr):
            raise _duplicate_utr()

        key = f"{SCREENSHOT_PREFIX}/{user_id}/{uuid4().hex}{IMAGE_EXTENSIONS[image_type]}"
        bucket = self._settings.S3_BUCKET_NAME
        await asyncio.to_thread(_storage().put_object, bucket, key, screenshot, ContentType=image_type)

        try:
            return await self._tx_repo.create(
                user_id=user_id,
                currency="INR",
                utr_number=utr,
                screenshot_key=key,
                payment_method=PAYMENT_METHOD,
                **purchase,
            )
        except IntegrityError:
            # Lost a race with another submission of the same UTR.
            await self._tx_repo.rollback()
            await asyncio.to_thread(_storage().delete_object, bucket, key)
            raise _duplicate_utr()

    async def list_for_user(self, user_id: str) -> list[PaymentResponse]:
        return [self._to_response(tx) for tx in await self._tx_repo.get_by_user(user_id)]

    # Admin side

    async def list_for_admin(
        self, status: PaymentStatus | None, query: str | None, limit: int, offset: int
    ) -> list[AdminPaymentResponse]:
        txs = await self._tx_repo.search(status, (query or "").strip() or None, limit, offset)
        return [self._to_admin_response(tx) for tx in txs]

    async def get_for_admin(self, tx_id: str) -> AdminPaymentResponse:
        return self._to_admin_response(await self._get_tx(tx_id))

    async def approve(self, tx_id: str, admin_id: str) -> AdminPaymentResponse:
        """Mark the payment SUCCESS and give the user what it bought, in one
        transaction: the plan for the period paid (a renewal extends the current
        end date) or the credit pack's credits."""
        tx = await self._get_tx(tx_id)
        if not await self._tx_repo.resolve_pending(tx_id, PaymentStatus.SUCCESS, verified_by=admin_id):
            raise _already_resolved()

        if tx.credit_pack:
            await self._subscription_service.grant_purchased_credits(
                tx.user_id, tx.credits, f"Bought {tx.credits} credits", reference_id=tx.id, commit=False
            )
            credits_added = tx.credits
        else:
            # A plan's credits come from its cycle reset (none for a renewal or a
            # queued period), so the balance change is what the user actually got.
            balance_before = await self._subscription_service.get_user_credit_balance(tx.user_id)
            await self._subscription_service.extend_plan(
                tx.user_id, tx.plan, PLAN_PRICES[BillingPeriod(tx.plan_type)].days, commit=False
            )
            credits_added = await self._subscription_service.get_user_credit_balance(tx.user_id) - balance_before
        await self._tx_repo.commit()
        log.info(f"UPI payment approved: tx={tx_id} user={tx.user_id} by={admin_id}")
        await notify_payment_approved(tx.user_id, credits_added, tx.plan.name if tx.plan else None)
        # A Pro payment can move the buyer's referral on.
        await refresh_referrals_of(tx.user_id)
        return await self.get_for_admin(tx_id)

    async def reject(self, tx_id: str, admin_id: str, reason: str) -> AdminPaymentResponse:
        tx = await self._get_tx(tx_id)
        if not await self._tx_repo.resolve_pending(
            tx_id, PaymentStatus.REJECTED, verified_by=admin_id, rejection_reason=reason.strip()
        ):
            raise _already_resolved()
        await self._tx_repo.commit()
        log.info(f"UPI payment rejected: tx={tx_id} by={admin_id}")
        await refresh_referrals_of(tx.user_id)
        return await self.get_for_admin(tx_id)

    # Helpers

    def _checkout(self, amount: float, note: str, **item) -> UpiCheckoutResponse:
        upi_uri = build_upi_uri(self._settings.UPI_ID, self._settings.UPI_PAYEE_NAME, amount, note)
        return UpiCheckoutResponse(
            **item,
            amount=amount,
            currency="INR",
            upi_id=self._settings.UPI_ID,
            payee_name=self._settings.UPI_PAYEE_NAME,
            upi_uri=upi_uri,
            qr_image=segno.make(upi_uri, error="m").svg_data_uri(scale=8, border=2),
        )

    def _require_upi(self) -> None:
        if not self._settings.UPI_ID:
            raise CustomException(
                message="UPI payments are not available right now",
                code="PAYMENTS_UNAVAILABLE",
                status_code=503,
            )

    def _get_credit_pack(self, pack_slug: str) -> CreditPack:
        self._require_upi()
        pack = CREDIT_PACKS.get(pack_slug)
        if not pack:
            raise CustomException(message="Unknown credit pack", code="CREDIT_PACK_NOT_FOUND", status_code=400)
        return pack

    async def _get_purchasable_plan(self, plan_slug: str) -> Plan:
        self._require_upi()
        plan = await self._plan_repo.get_by_slug(plan_slug)
        if plan_slug != PURCHASABLE_PLAN or not plan or not plan.is_active:
            raise CustomException(
                message="This plan cannot be purchased with UPI",
                code="PLAN_NOT_PURCHASABLE",
                status_code=400,
            )
        return plan

    async def _enforce_rate_limit(self, user_id: str) -> None:
        since = datetime.utcnow() - timedelta(hours=1)
        if await self._tx_repo.count_created_since(user_id, since) >= self._settings.PAYMENT_SUBMISSIONS_PER_HOUR:
            raise CustomException(
                message="Too many payment submissions. Please try again in an hour.",
                code="RATE_LIMITED",
                status_code=429,
            )

    async def _get_tx(self, tx_id: str) -> PaymentTransaction:
        tx = await self._tx_repo.get_by_id(tx_id)
        if not tx:
            raise CustomException(message="Payment not found", code="NOT_FOUND", status_code=404)
        return tx

    def _screenshot_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return _storage().generate_presigned_url(
            self._settings.S3_BUCKET_NAME, key, expires_in=SCREENSHOT_URL_TTL_SECONDS
        )

    def _to_response(self, tx: PaymentTransaction) -> PaymentResponse:
        return PaymentResponse(**self._response_fields(tx))

    def _to_admin_response(self, tx: PaymentTransaction) -> AdminPaymentResponse:
        return AdminPaymentResponse(
            **self._response_fields(tx),
            user_id=tx.user_id,
            user_email=tx.user.email,
            user_name=tx.user.full_name or tx.user.username,
            verified_by=tx.verified_by,
        )

    def _response_fields(self, tx: PaymentTransaction) -> dict:
        return {
            "id": tx.id,
            "plan_slug": _slug(tx.plan) if tx.plan else None,
            "plan_name": tx.plan.name if tx.plan else None,
            "plan_type": str(getattr(tx.plan_type, "value", tx.plan_type)) if tx.plan_type else None,
            "credit_pack": tx.credit_pack,
            "credits": tx.credits,
            "amount": float(tx.amount),
            "currency": tx.currency,
            "utr_number": tx.utr_number,
            "status": str(getattr(tx.status, "value", tx.status)),
            "rejection_reason": tx.rejection_reason,
            "screenshot_url": self._screenshot_url(tx.screenshot_key),
            "verified_at": tx.verified_at,
            "created_at": tx.created_at,
        }


def _slug(plan: Plan) -> str:
    return str(getattr(plan.slug, "value", plan.slug))


def _duplicate_utr() -> CustomException:
    return CustomException(
        message="This UTR has already been submitted", code="DUPLICATE_UTR", status_code=409
    )


def _already_resolved() -> CustomException:
    return CustomException(
        message="Only pending payments can be approved or rejected",
        code="PAYMENT_ALREADY_RESOLVED",
        status_code=409,
    )
