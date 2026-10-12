from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FeatureFlagsResponse(BaseModel):
    """Effective on/off state of every flag, for deciding what the UI shows."""

    flags: Dict[str, bool]


class AdminFeatureFlagResponse(BaseModel):
    key: str
    label: str
    description: str
    parent: Optional[str] = None
    # The switch as set; ``effective`` is false while the parent is off.
    enabled: bool
    effective: bool
    updated_at: Optional[datetime] = None
    # Emails the flag is on for even while it's off (a staged rollout).
    test_users: List[str] = []


class AdminFeatureFlagListResponse(BaseModel):
    flags: List[AdminFeatureFlagResponse]


class AdminFeatureFlagUpdateRequest(BaseModel):
    enabled: bool


class AdminFeatureFlagUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    allowed: bool
