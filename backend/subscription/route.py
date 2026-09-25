from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CurrentAdminDep, CurrentUserDep
from auth.repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from subscription.dependencies import SubscriptionServiceDep
from subscription.schema import (
    PaymentTransactionResponse,
    CreditLedgerResponse,
    UserCreditsResponse,
    CreditTopupRequest,
    AdminCreditTopupResponse,
    EntitlementsResponse,
    PlanOfferResponse,
    PlanPriceResponse,
    PlansResponse,
)
from subscription.entitlements import PLAN_PRICES, PURCHASABLE_PLAN, entitlements_for
from subscription.service import PlanSummary, plan_slug
from core.database import get_db
from core.exceptions import CustomException

router = APIRouter(prefix="/subscription", tags=["subscription"])


def entitlements_response(summary: PlanSummary) -> EntitlementsResponse:
    ent = summary.entitlements
    return EntitlementsResponse(
        **ent.to_dict(),
        credit_minutes_total=ent.credit_minutes,
        credit_minutes_remaining=summary.credit_minutes_remaining,
        current_period_end=summary.current_period_end,
        subscription_status=summary.subscription_status,
        plan_expires_at=summary.plan_expires_at,
        next_credit_reset_at=summary.next_credit_reset_at,
        usage_today=summary.usage_today,
        has_pending_payment=summary.has_pending_payment,
        show_plan_notice=summary.show_plan_notice,
    )


def _credits_response(summary: PlanSummary) -> UserCreditsResponse:
    return UserCreditsResponse(
        plan=summary.entitlements.plan,
        credit_minutes_total=summary.entitlements.credit_minutes,
        credit_minutes_remaining=summary.credit_minutes_remaining,
        subscription_status=summary.subscription_status,
        current_period_end=summary.current_period_end,
    )


@router.get("/plans", response_model=PlansResponse)
async def list_plans(service: SubscriptionServiceDep):
    """Plans on sale, their prices and what each includes, for the pricing page."""
    offers = []
    for plan in await service.list_plans():
        slug = plan_slug(plan)
        prices = PLAN_PRICES if slug == PURCHASABLE_PLAN else {}
        offers.append(
            PlanOfferResponse(
                slug=slug,
                name=plan.name,
                capabilities=entitlements_for(slug).to_dict(),
                prices=[
                    PlanPriceResponse(plan_type=period.value, amount=price.amount_inr, currency="INR", days=price.days)
                    for period, price in prices.items()
                ],
            )
        )
    return PlansResponse(plans=offers)


@router.get("/me", response_model=UserCreditsResponse)
async def get_my_subscription(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    return _credits_response(await service.get_plan_summary(current_user["user_id"]))


@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_my_entitlements(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """What the caller's plan allows, today's usage and billing state. The UI
    reads this instead of deciding tier rules for itself, so both sides stay
    in step."""
    return entitlements_response(await service.get_plan_summary(current_user["user_id"]))


@router.post("/activate-free", response_model=UserCreditsResponse)
async def activate_free_plan(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """Idempotent: grants this cycle's Free credits if not already granted. It
    never touches a paid subscription."""
    await service.activate_free_plan(current_user["user_id"])
    return _credits_response(await service.get_plan_summary(current_user["user_id"]))


@router.post("/topup", response_model=AdminCreditTopupResponse)
async def topup_credits(
    admin: CurrentAdminDep,
    service: SubscriptionServiceDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: CreditTopupRequest,
):
    """Add credit minutes to any user. Admin only; the entry records who did it."""
    user = await UserRepository(session).get_user_by_email(body.user_email)
    if not user:
        raise CustomException(message="No user with that email", code="NOT_FOUND", status_code=404)
    entry = await service.admin_topup(user.id, body.amount, body.reason.strip(), admin.id)
    return _topup_response(entry)


@router.get("/topups", response_model=list[AdminCreditTopupResponse])
async def list_topups(
    _: CurrentAdminDep,
    service: SubscriptionServiceDep,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Audit log of manual top-ups, newest first. Admin only."""
    entries = await service.list_admin_topups((q or "").strip() or None, limit, offset)
    return [_topup_response(e) for e in entries]


def _topup_response(entry) -> AdminCreditTopupResponse:
    return AdminCreditTopupResponse(
        id=entry.id,
        user_id=entry.user_id,
        user_email=entry.user.email,
        user_name=entry.user.full_name or entry.user.username,
        amount=entry.amount,
        balance_after=entry.balance_after,
        reason=entry.reason,
        created_by=entry.created_by,
        created_by_email=entry.creator.email if entry.creator else None,
        created_at=entry.created_at,
    )


@router.get("/transactions", response_model=list[PaymentTransactionResponse])
async def get_my_transactions(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    txs = await service.get_user_transactions(current_user["user_id"])
    return [PaymentTransactionResponse.model_validate(t) for t in txs]


@router.get("/ledger", response_model=list[CreditLedgerResponse])
async def get_credit_ledger(current_user: CurrentUserDep, service: SubscriptionServiceDep, limit: int = 50):
    entries = await service.get_user_credit_history(current_user["user_id"], limit)
    return [CreditLedgerResponse.model_validate(e) for e in entries]
