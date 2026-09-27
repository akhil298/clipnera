from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Dict, List, Literal, Optional


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
    # Set for a plan payment; credit_pack and credits for a credit-pack one.
    plan_id: Optional[str] = None
    plan: Optional[PlanResponse] = None
    credit_pack: Optional[str] = None
    credits: Optional[int] = None
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


class PlanCapabilities(BaseModel):
    """What a plan includes. Mirrors Entitlements in subscription/entitlements.py."""

    plan: str
    aspect_ratios: List[str]
    caption_styles: Optional[List[str]] = None  # null means every style
    max_clips_per_video: int
    watermark_forced: bool
    pro_ai_provider: bool
    priority_rendering: bool
    max_upload_duration_seconds: int
    credit_minutes: int
    all_hook_transitions: bool
    brand_kit_edit: bool
    depth_captions: bool
    batch_processing: bool
    team_members: bool
    # Per UTC day; null means unlimited.
    daily_limits: Dict[str, Optional[int]]
    social_max_accounts: int
    social_platforms: List[str]
    social_scheduling: bool
    social_max_schedule_days: int
    social_posts_per_day: int
    custom_aspect_ratios: bool
    # Every boolean capability by name, as checked by require_feature.
    features: Dict[str, bool]


class EntitlementsResponse(PlanCapabilities):
    """The caller's current plan with billing state and today's usage.

    The UI uses this to disable what the user cannot access and to explain why,
    instead of hardcoding its own copy of the tier rules.
    """

    credit_minutes_total: int = 0
    credit_minutes_remaining: int = 0
    # The bought part of credit_minutes_remaining; never expires.
    purchased_credits_remaining: int = 0
    current_period_end: Optional[datetime] = None
    subscription_status: str = "none"
    # When paid access ends, counting renewals queued after the current period.
    plan_expires_at: Optional[datetime] = None
    next_credit_reset_at: Optional[datetime] = None
    usage_today: Dict[str, int] = {}
    # Pricing, so the UI can show a run's cost before it starts; see
    # SubscriptionService.calculate_video_credit_cost.
    credits_per_video_minute: float = 0.0
    extra_aspect_ratio_credit_share: float = 0.0
    has_pending_payment: bool = False
    # One-time notice for accounts that predate Pro gating.
    show_plan_notice: bool = False


class PlanPriceResponse(BaseModel):
    plan_type: Literal["monthly", "yearly"]
    amount: int
    currency: str
    days: int


class PlanOfferResponse(BaseModel):
    slug: str
    name: str
    capabilities: PlanCapabilities
    # Empty for plans that are not sold (Free).
    prices: List[PlanPriceResponse]


class CreditPackResponse(BaseModel):
    """A one-off credit pack. Mirrors CreditPack in subscription/entitlements.py."""

    slug: str
    name: str
    credits: int
    amount: int
    currency: str


class PlansResponse(BaseModel):
    plans: List[PlanOfferResponse]
    credit_packs: List[CreditPackResponse] = []
