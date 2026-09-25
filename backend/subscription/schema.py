from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


class PlanResponse(BaseModel):
    id: str
    name: str
    slug: str
    credit_minutes: int
    price_monthly: float
    currency: str
    price_inr: Optional[float] = None
    is_active: bool
    features: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserSubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan_id: str
    plan: PlanResponse
    status: str
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaymentTransactionResponse(BaseModel):
    id: str
    user_id: str
    plan_id: str
    plan: PlanResponse
    amount: float
    currency: str
    status: str
    payment_uuid: str
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CreditTopupRequest(BaseModel):
    """An admin adding credit minutes to a user's balance by hand."""

    user_email: EmailStr
    amount: int = Field(gt=0, le=100_000)
    reason: str = Field(min_length=3, max_length=255)


class AdminCreditTopupResponse(BaseModel):
    """One manual top-up, for the admin audit log."""

    id: str
    user_id: str
    user_email: str
    user_name: Optional[str] = None
    amount: int
    balance_after: int
    reason: str
    created_by: Optional[str] = None
    created_by_email: Optional[str] = None
    created_at: datetime


class CreditLedgerResponse(BaseModel):
    id: str
    user_id: str
    amount: int
    balance_after: int
    reason: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    created_at: datetime


class UserCreditsResponse(BaseModel):
    plan: str
    credit_minutes_total: int
    credit_minutes_remaining: int
    subscription_status: str
    current_period_end: Optional[datetime] = None


class EntitlementsResponse(BaseModel):
    """Capabilities granted by the caller's current plan.

    The UI uses this to disable what the user cannot access and to explain why,
    instead of hardcoding its own copy of the tier rules.
    """

    plan: str
    aspect_ratios: List[str]
    caption_styles: Optional[List[str]] = None  # null means every style
    max_clips_per_video: int
    watermark_forced: bool
    pro_ai_provider: bool
    priority_rendering: bool
    max_upload_duration_seconds: int
    # Billing context, so the UI can show a real renewal date and quota instead
    # of a hardcoded placeholder.
    credit_minutes_total: int = 0
    credit_minutes_remaining: int = 0
    current_period_end: Optional[datetime] = None
    subscription_status: str = "none"


class PlanCatalogEntry(BaseModel):
    """A plan plus the capabilities it would grant, for upgrade comparisons."""

    id: str
    name: str
    slug: str
    credit_minutes: int
    price_monthly: float
    currency: str
    features: List[str]
    entitlements: EntitlementsResponse
    is_current: bool
