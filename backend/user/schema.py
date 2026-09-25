from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    avatar_initials: str = ""
    plan: str = "free"
    ai_credits_minutes_remaining: int = 0
    ai_credits_total: int = 0
    active_workspace_id: Optional[str] = None
    providers: list[str] = []
    # Display only: admin pages are guarded server-side by the role in the database.
    role: Literal["user", "admin"] = "user"
