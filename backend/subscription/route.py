from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CurrentAdminDep, CurrentUserDep
from auth.repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from subscription.repository import (
    PlanRepository,
    UserSubscriptionRepository,
    PaymentTransactionRepository,
    CreditLedgerRepository,
)
from subscription.service import SubscriptionService
from subscription.schema import (
    PlanResponse,
    UserSubscriptionResponse,
    PaymentTransactionResponse,
    CreditLedgerResponse,
    UserCreditsResponse,
    CreditTopupRequest,
    AdminCreditTopupResponse,
    EntitlementsResponse,
    PlanCatalogEntry,
)
from subscription.entitlements import entitlements_for
from subscription.model import PlanSlug
from core.database import get_db
from core.exceptions import CustomException

router = APIRouter(prefix="/subscription", tags=["subscription"])


async def get_subscription_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionService:
    plan_repo = PlanRepository(session)
    sub_repo = UserSubscriptionRepository(session)
    tx_repo = PaymentTransactionRepository(session)
    ledger_repo = CreditLedgerRepository(session)
    return SubscriptionService(plan_repo, sub_repo, tx_repo, ledger_repo)


SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(service: SubscriptionServiceDep):
    plans = await service.list_plans()
    return [PlanResponse.model_validate(p) for p in plans]


@router.get("/me", response_model=UserCreditsResponse)
async def get_my_subscription(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    sub = await service.get_user_subscription(current_user["user_id"])
    balance = await service.get_user_credit_balance(current_user["user_id"])

    if not sub:
        return UserCreditsResponse(
            plan="free",
            credit_minutes_total=0,
            credit_minutes_remaining=balance,
            subscription_status="none",
            current_period_end=None,
        )

    return UserCreditsResponse(
        plan=sub.plan.slug.value,
        credit_minutes_total=sub.plan.credit_minutes,
        credit_minutes_remaining=balance,
        subscription_status=sub.status.value,
        current_period_end=sub.current_period_end,
    )


@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_my_entitlements(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """What the caller's plan allows. The UI reads this instead of deciding
    tier rules for itself, so both sides stay in step."""
    user_id = current_user["user_id"]
    ent = await service.get_entitlements(user_id)
    sub = await service.get_user_subscription(user_id)
    balance = await service.get_user_credit_balance(user_id)
    return EntitlementsResponse(
        **ent.to_dict(),
        credit_minutes_total=sub.plan.credit_minutes if sub else 0,
        credit_minutes_remaining=balance,
        current_period_end=sub.current_period_end if sub else None,
        subscription_status=sub.status.value if sub else "none",
    )


@router.get("/catalog", response_model=list[PlanCatalogEntry])
async def get_plan_catalog(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    """Every active plan with the capabilities it grants, for the upgrade view."""
    plans = await service.list_plans()
    current_slug = await service.get_user_plan_slug(current_user["user_id"])

    catalog: list[PlanCatalogEntry] = []
    for plan in plans:
        slug = str(getattr(plan.slug, "value", plan.slug))
        ent = entitlements_for(slug)
        catalog.append(
            PlanCatalogEntry(
                id=plan.id,
                name=plan.name,
                slug=slug,
                credit_minutes=plan.credit_minutes,
                price_monthly=float(plan.price_monthly),
                currency=plan.currency,
                features=[f.strip() for f in (plan.features or "").split(",") if f.strip()],
                entitlements=EntitlementsResponse(**ent.to_dict()),
                is_current=(slug == current_slug),
            )
        )
    catalog.sort(key=lambda entry: entry.price_monthly)
    return catalog


@router.post("/activate-free", response_model=UserCreditsResponse)
async def activate_free_plan(current_user: CurrentUserDep, service: SubscriptionServiceDep):
    try:
        sub = await service.activate_free_plan(current_user["user_id"])
        balance = await service.get_user_credit_balance(current_user["user_id"])
        return UserCreditsResponse(
            plan=sub.plan.slug.value,
            credit_minutes_total=sub.plan.credit_minutes,
            credit_minutes_remaining=balance,
            subscription_status=sub.status.value,
            current_period_end=sub.current_period_end,
        )
    except ValueError as exc:
        raise CustomException(message=str(exc), code="INVALID_PLAN", status_code=400)


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
