from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    avatar_initials: str = ""
    plan: str = "pro"
    ai_credits_minutes_remaining: int = 500
    ai_credits_total: int = 1000
    active_workspace_id: Optional[str] = None
    providers: list[str] = []
