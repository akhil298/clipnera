from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

PaymentStatusValue = Literal["pending", "success", "failed", "rejected"]
PlanTypeValue = Literal["monthly", "yearly"]


class UpiCheckoutResponse(BaseModel):
    """What the user needs to pay through UPI for a plan period (plan_*) or a
    credit pack (credit_pack, credits)."""

    plan_slug: Optional[str] = None
    plan_name: Optional[str] = None
    plan_type: Optional[PlanTypeValue] = None
    credit_pack: Optional[str] = None
    credits: Optional[int] = None
    # What the QR charges: the dollar price in rupees at today's rate.
    amount: float
    currency: str
    amount_usd: float
    usd_inr_rate: float
    upi_id: str
    payee_name: str
    # upi://pay deep link; opens the user's UPI app directly on mobile.
    upi_uri: str
    # SVG data URI of the QR code encoding ``upi_uri``, amount pre-filled.
    qr_image: str


class PaymentResponse(BaseModel):
    id: str
    # Set for a plan payment; credit_pack and credits for a credit-pack one.
    plan_slug: Optional[str] = None
    plan_name: Optional[str] = None
    plan_type: Optional[PlanTypeValue] = None
    credit_pack: Optional[str] = None
    credits: Optional[int] = None
    amount: float
    currency: str
    utr_number: Optional[str] = None
    status: PaymentStatusValue
    rejection_reason: Optional[str] = None
    # Short-lived signed URL; never a public link.
    screenshot_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime


class AdminPaymentResponse(PaymentResponse):
    user_id: str
    user_email: str
    user_name: Optional[str] = None
    verified_by: Optional[str] = None


class PaymentRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
