"""Referral API types. Mirrored in frontend/lib/types.ts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReferralRulesResponse(BaseModel):
    referee_pro_credits: int
    referrer_pro_credits: int
    referrer_video_credits: int
    bonus_expiry_days: int
    pro_window_hours: int
    video_window_hours: int
    monthly_cap: int
    min_video_seconds: int
    approval_wait_days: int


class ReferralRewardResponse(BaseModel):
    kind: str
    credits: int
    granted_at: datetime
    expires_at: datetime


class ReferralItemResponse(BaseModel):
    """One person the caller referred, as the caller may see them."""

    id: str
    name: str
    email_masked: str
    status: str
    fail_reason: Optional[str] = None
    signed_up_at: datetime
    pro_deadline_at: datetime
    pro_activated_at: Optional[datetime] = None
    video_deadline_at: Optional[datetime] = None
    video_completed_at: Optional[datetime] = None
    # Rewards wait for an admin's review while this is true.
    on_hold: bool
    rewards: list[ReferralRewardResponse]
    # The rules this referral runs under (fixed when it began).
    rules: ReferralRulesResponse


class ReferralStatsResponse(BaseModel):
    invited: int
    in_progress: int
    succeeded: int
    partial: int
    failed: int
    credits_earned: int


class MyReferralsResponse(BaseModel):
    enabled: bool
    code: Optional[str] = None
    share_url: Optional[str] = None
    rules: ReferralRulesResponse
    used_this_month: int
    stats: ReferralStatsResponse
    referrals: list[ReferralItemResponse]


class InvitedByResponse(BaseModel):
    """The referral the caller joined through, from their side."""

    referrer_name: str
    status: str
    fail_reason: Optional[str] = None
    signed_up_at: datetime
    pro_deadline_at: datetime
    pro_activated_at: Optional[datetime] = None
    video_deadline_at: Optional[datetime] = None
    # What buying Pro in time earns the caller, and what it did earn.
    bonus_credits: int
    reward: Optional[ReferralRewardResponse] = None


class ValidateCodeResponse(BaseModel):
    valid: bool
    referrer_name: Optional[str] = None
    # Why the code cannot be used, when it cannot.
    reason: Optional[str] = None
    # What joining with a valid code earns, under the current rules.
    bonus_credits: Optional[int] = None
    pro_window_hours: Optional[int] = None
    bonus_expiry_days: Optional[int] = None


class AdminReferralResponse(BaseModel):
    id: str
    referrer_id: Optional[str] = None
    referrer_email: Optional[str] = None
    referee_id: Optional[str] = None
    referee_email: Optional[str] = None
    referee_name: str
    code: str
    status: str
    fail_reason: Optional[str] = None
    review_state: str
    flagged_reason: Optional[str] = None
    signed_up_at: datetime
    pro_deadline_at: datetime
    pro_activated_at: Optional[datetime] = None
    video_deadline_at: Optional[datetime] = None
    video_completed_at: Optional[datetime] = None
    rewards: list[ReferralRewardResponse]
    created_at: datetime


class AdminReferralVoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class ReferralSettingsRequest(BaseModel):
    referee_pro_credits: int = Field(ge=0, le=5000)
    referrer_pro_credits: int = Field(ge=0, le=5000)
    referrer_video_credits: int = Field(ge=0, le=5000)
    bonus_expiry_days: int = Field(ge=1, le=365)
    pro_window_hours: int = Field(ge=1, le=720)
    video_window_hours: int = Field(ge=1, le=720)
    # 0 stops new referrals without switching the program off.
    monthly_cap: int = Field(ge=0, le=1000)
    min_video_seconds: int = Field(ge=0, le=3600)
    approval_wait_days: int = Field(ge=0, le=60)


class ReferralSettingsChangeResponse(BaseModel):
    admin_email: Optional[str] = None
    changes: dict
    created_at: datetime


class AdminReferralSettingsResponse(BaseModel):
    rules: ReferralRulesResponse
    updated_at: Optional[datetime] = None
    history: list[ReferralSettingsChangeResponse]
