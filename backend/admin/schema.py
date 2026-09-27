from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class AdminUserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: Literal["user", "admin"]
    # Effective plan right now; "free" once a paid period has ended.
    plan: str
    # When paid access ends, counting queued renewals; null on Free.
    plan_expires_at: Optional[datetime] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None
    # Last UTC day with a signed-in request; tracked from the day this shipped.
    last_active_on: Optional[date] = None
    projects: int = 0
    clips: int = 0
    credits_left: int = 0
    # Sum of approved payments, in INR.
    total_paid: float = 0.0
    ai_cost_usd: float = 0.0


AdminUserSort = Literal["newest", "last_active", "projects", "ai_cost"]


class AdminUserPlanRequest(BaseModel):
    """Grant ``days`` of Pro (stacked on any current Pro), or revoke to Free."""

    plan: Literal["pro", "free"]
    days: Optional[int] = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def _days_for_pro(self) -> "AdminUserPlanRequest":
        if self.plan == "pro" and self.days is None:
            raise ValueError("days is required when granting Pro")
        return self


class AdminOverviewResponse(BaseModel):
    total_users: int
    free_users: int
    pro_users: int
    pending_payments: int
    # Approved payments verified since the start of the current UTC month.
    revenue_this_month: float
    currency: str


class AdminUserProject(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: Optional[str] = None
    status: str
    duration_seconds: Optional[int] = None
    clips: int
    # Net of refunds.
    credits_charged: int
    ai_cost_usd: float
    created_at: datetime


class AdminLoginEntry(BaseModel):
    created_at: datetime
    method: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None


class AdminUserPayment(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    # A payment buys either a plan period or a credit pack.
    plan_type: Optional[str] = None
    credit_pack: Optional[str] = None
    credits: Optional[int] = None
    created_at: datetime
    verified_at: Optional[datetime] = None


class AdminCreditEntry(BaseModel):
    created_at: datetime
    amount: int
    balance_after: int
    reason: str


class AdminUserDetailResponse(BaseModel):
    user: AdminUserResponse
    credits_total: int
    next_credit_reset_at: Optional[datetime] = None
    active_days: int
    projects: list[AdminUserProject]
    logins: list[AdminLoginEntry]
    payments: list[AdminUserPayment]
    credit_history: list[AdminCreditEntry]


class AdminDailyGrowth(BaseModel):
    day: date
    signups: int
    active_users: int
    logins: int
    projects: int
    clips: int
    # Approved payments by the day they were verified, in INR.
    revenue: float
    ai_cost_usd: float


class AdminGrowthResponse(BaseModel):
    days: int
    total_users: int
    new_users: int
    # Distinct users active at any point in the window.
    active_in_window: int
    active_today: int
    active_7d: int
    active_30d: int
    pro_users: int
    projects: int
    clips: int
    revenue: float
    currency: str
    ai_cost_usd: float
    daily: list[AdminDailyGrowth]
