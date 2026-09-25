from __future__ import annotations

from datetime import datetime
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
