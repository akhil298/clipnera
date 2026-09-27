from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.database import get_db
from payment.repository import ManualPaymentRepository
from payment.schema import (
    AdminPaymentResponse,
    PaymentRejectRequest,
    PaymentResponse,
    UpiCheckoutResponse,
)
from payment.service import MAX_SCREENSHOT_BYTES, PaymentService
from subscription.model import BillingPeriod, PaymentStatus
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService

payments = APIRouter(prefix="/payments", tags=["payments"])
# The router-level dependency returns 403 to non-admins on every route here,
# including ones added later.
admin_payments = APIRouter(
    prefix="/admin/payments", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


async def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentService:
    tx_repo = ManualPaymentRepository(session)
    return PaymentService(tx_repo, PlanRepository(session), SubscriptionService.for_session(session))


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


@payments.get("/qr", response_model=UpiCheckoutResponse)
async def get_upi_checkout(
    _: CurrentUserDep,
    service: PaymentServiceDep,
    plan_slug: str = Query(...),
    plan_type: BillingPeriod = Query(...),
) -> UpiCheckoutResponse:
    return await service.get_checkout(plan_slug, plan_type)


@payments.post("", response_model=PaymentResponse, status_code=201)
async def submit_payment(
    current_user: CurrentUserDep,
    service: PaymentServiceDep,
    plan_slug: str = Form(...),
    plan_type: BillingPeriod = Form(...),
    utr_number: str = Form(...),
    screenshot: UploadFile = File(...),
) -> PaymentResponse:
    # Read one byte past the limit so an oversized file is detected without
    # buffering all of it.
    data = await screenshot.read(MAX_SCREENSHOT_BYTES + 1)
    return await service.submit(
        user_id=current_user["user_id"],
        plan_slug=plan_slug,
        plan_type=plan_type,
        utr_number=utr_number,
        screenshot=data,
        content_type=screenshot.content_type,
    )


@payments.get("/credit-packs/{pack_slug}/qr", response_model=UpiCheckoutResponse)
async def get_credit_pack_checkout(
    pack_slug: str, _: CurrentUserDep, service: PaymentServiceDep
) -> UpiCheckoutResponse:
    return await service.get_credit_pack_checkout(pack_slug)


@payments.post("/credit-packs", response_model=PaymentResponse, status_code=201)
async def submit_credit_pack_payment(
    current_user: CurrentUserDep,
    service: PaymentServiceDep,
    credit_pack: str = Form(...),
    utr_number: str = Form(...),
    screenshot: UploadFile = File(...),
) -> PaymentResponse:
    data = await screenshot.read(MAX_SCREENSHOT_BYTES + 1)
    return await service.submit_credit_pack(
        user_id=current_user["user_id"],
        pack_slug=credit_pack,
        utr_number=utr_number,
        screenshot=data,
        content_type=screenshot.content_type,
    )


@payments.get("/my", response_model=list[PaymentResponse])
async def list_my_payments(current_user: CurrentUserDep, service: PaymentServiceDep) -> list[PaymentResponse]:
    return await service.list_for_user(current_user["user_id"])


@admin_payments.get("", response_model=list[AdminPaymentResponse])
async def list_payments(
    _: CurrentAdminDep,
    service: PaymentServiceDep,
    status: PaymentStatus | None = Query(None),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AdminPaymentResponse]:
    return await service.list_for_admin(status, q, limit, offset)


@admin_payments.get("/{payment_id}", response_model=AdminPaymentResponse)
async def get_payment(payment_id: str, _: CurrentAdminDep, service: PaymentServiceDep) -> AdminPaymentResponse:
    return await service.get_for_admin(payment_id)


@admin_payments.patch("/{payment_id}/approve", response_model=AdminPaymentResponse)
async def approve_payment(
    payment_id: str, admin: CurrentAdminDep, service: PaymentServiceDep
) -> AdminPaymentResponse:
    return await service.approve(payment_id, admin.id)


@admin_payments.patch("/{payment_id}/reject", response_model=AdminPaymentResponse)
async def reject_payment(
    payment_id: str,
    body: PaymentRejectRequest,
    admin: CurrentAdminDep,
    service: PaymentServiceDep,
) -> AdminPaymentResponse:
    return await service.reject(payment_id, admin.id, body.reason)
