from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

PaymentStatusValue = Literal["pending", "success", "failed", "rejected"]


class UpiCheckoutResponse(BaseModel):
    """What the user needs to pay for a plan through UPI."""

    plan_slug: str
    plan_name: str
    amount: float
    currency: str
    upi_id: str
    payee_name: str
    # upi://pay deep link; opens the user's UPI app directly on mobile.
    upi_uri: str
    # SVG data URI of the QR code encoding ``upi_uri``, amount pre-filled.
    qr_image: str


class PaymentResponse(BaseModel):
    id: str
    plan_slug: str
    plan_name: str
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
