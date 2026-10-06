from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from referral.schema import InvitedByResponse

# Mirrored by ONBOARDING_ROLES / ONBOARDING_SOURCES in frontend/lib/types.ts.
OnboardingRole = Literal["youtuber", "podcaster", "streamer", "agency", "marketer", "educator", "business", "other"]
OnboardingSource = Literal["youtube", "instagram", "friend", "google", "x", "linkedin", "other"]


class OnboardingStatusResponse(BaseModel):
    completed: bool
    # Whether the form may take a referral code: only a brand-new account, while
    # the program is on and there is still time to buy Pro.
    can_use_referral_code: bool


class OnboardingRequest(BaseModel):
    role: OnboardingRole
    role_other: Optional[str] = Field(None, max_length=80)
    heard_from: OnboardingSource
    heard_from_other: Optional[str] = Field(None, max_length=80)
    referral_code: Optional[str] = Field(None, max_length=32)

    @model_validator(mode="after")
    def _other_needs_text(self) -> "OnboardingRequest":
        for choice, text in ((self.role, self.role_other), (self.heard_from, self.heard_from_other)):
            if choice == "other" and not (text or "").strip():
                raise ValueError("Tell us a little more when you pick Other.")
        return self


class OnboardingResponse(BaseModel):
    completed_at: datetime
    # The referral the code started, if one was given.
    referral: Optional[InvitedByResponse] = None
