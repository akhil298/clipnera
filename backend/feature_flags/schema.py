from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


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


class AdminFeatureFlagListResponse(BaseModel):
    flags: List[AdminFeatureFlagResponse]


class AdminFeatureFlagUpdateRequest(BaseModel):
    enabled: bool
