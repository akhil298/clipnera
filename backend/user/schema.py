from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    avatar_initials: str = ""
    # The effective plan: "free" as soon as a paid period ends.
    plan: str = "free"
    # When paid access ends, counting queued renewals; null on Free.
    plan_expires_at: Optional[datetime] = None
    ai_credits_minutes_remaining: int = 0
    ai_credits_total: int = 0
    # Capability name -> allowed, as enforced by the API.
    features: dict[str, bool] = {}
    # Per UTC day; null means unlimited.
    daily_limits: dict[str, Optional[int]] = {}
    usage_today: dict[str, int] = {}
    active_workspace_id: Optional[str] = None
    providers: list[str] = []
    # Display only: admin pages are guarded server-side by the role in the database.
    role: Literal["user", "admin"] = "user"
