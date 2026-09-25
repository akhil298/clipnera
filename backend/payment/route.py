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
from subscription.model import PaymentStatus
from subscription.repository import (
    CreditLedgerRepository,
    PlanRepository,
    UserSubscriptionRepository,
)
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
    plan_repo = PlanRepository(session)
    subscription_service = SubscriptionService(
        plan_repo,
        UserSubscriptionRepository(session),
        tx_repo,
        CreditLedgerRepository(session),
    )
    return PaymentService(tx_repo, plan_repo, subscription_service)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


@payments.get("/qr", response_model=UpiCheckoutResponse)
async def get_upi_checkout(
    _: CurrentUserDep,
    service: PaymentServiceDep,
    plan_slug: str = Query(...),
) -> UpiCheckoutResponse:
    return await service.get_checkout(plan_slug)


@payments.post("", response_model=PaymentResponse, status_code=201)
async def submit_payment(
    current_user: CurrentUserDep,
    service: PaymentServiceDep,
    plan_slug: str = Form(...),
    utr_number: str = Form(...),
    screenshot: UploadFile = File(...),
) -> PaymentResponse:
    # Read one byte past the limit so an oversized file is detected without
    # buffering all of it.
    data = await screenshot.read(MAX_SCREENSHOT_BYTES + 1)
    return await service.submit(
        user_id=current_user["user_id"],
        plan_slug=plan_slug,
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
