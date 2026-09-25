from __future__ import annotations

from fastapi import APIRouter, Query

from auth.dependencies import CurrentAdminDep, CurrentUserDep
from subscription.dependencies import SubscriptionServiceDep
from subscription.schema import (
    PaymentTransactionResponse,
    CreditLedgerResponse,
    UserCreditsResponse,
    CreditTopupRequest,
    AdminCreditTopupResponse,
    EntitlementsResponse,
    PlansResponse,
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans", response_model=PlansResponse)
async def list_plans(service: SubscriptionServiceDep):
    """Plans on sale, their prices and what each includes, for the pricing page."""
    return await service.plan_offers()


@router.get("/me", response_model=UserCreditsResponse)
async def get_my_subscription(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    return await service.credits_summary(current_user["user_id"])


@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_my_entitlements(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """What the caller's plan allows, today's usage and billing state. The UI
    reads this instead of deciding tier rules for itself, so both sides stay
    in step."""
    return await service.entitlements_summary(current_user["user_id"])


@router.post("/activate-free", response_model=UserCreditsResponse)
async def activate_free_plan(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """Idempotent: grants this cycle's Free credits if not already granted. It
    never touches a paid subscription."""
    return await service.activate_free(current_user["user_id"])


@router.post("/topup", response_model=AdminCreditTopupResponse)
async def topup_credits(admin: CurrentAdminDep, service: SubscriptionServiceDep, body: CreditTopupRequest):
    """Add credit minutes to any user. Admin only; the entry records who did it."""
    return await service.admin_topup_by_email(body.user_email, body.amount, body.reason, admin.id)


@router.get("/topups", response_model=list[AdminCreditTopupResponse])
async def list_topups(
    _: CurrentAdminDep,
    service: SubscriptionServiceDep,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Audit log of manual top-ups, newest first. Admin only."""
    return await service.admin_topup_history(q, limit, offset)


@router.get("/transactions", response_model=list[PaymentTransactionResponse])
async def get_my_transactions(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    return await service.transaction_history(current_user["user_id"])


@router.get("/ledger", response_model=list[CreditLedgerResponse])
async def get_credit_ledger(current_user: CurrentUserDep, service: SubscriptionServiceDep, limit: int = 50):
    return await service.ledger_history(current_user["user_id"], limit)
