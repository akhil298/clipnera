from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    # Account emails (failed posts, reconnect reminders); off after unsubscribing.
    email_notifications: bool = True


class EmailPreferencesRequest(BaseModel):
    email_notifications: bool


class UnsubscribeRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class DeleteAccountRequest(BaseModel):
    # The account's email, typed by the user to confirm a deletion that cannot be undone.
    confirm_email: str = Field(min_length=3, max_length=255)
