from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from creator_intro.platforms import Platform

IntroTheme = Literal["auto", "light", "dark"]
AvatarType = Literal["image/jpeg", "image/png", "image/webp"]


class CreatorIntroSaveRequest(BaseModel):
    platform: Platform = "youtube"
    niche: Optional[str] = Field(default=None, max_length=60)
    channel_name: str = Field(..., min_length=1, max_length=120)
    handle: Optional[str] = Field(default=None, max_length=120)
    about: str = Field(default="", max_length=2000)
    # Empty lets the AI write the line from ``about``.
    tagline: Optional[str] = Field(default=None, max_length=200)
    theme: IntroTheme = "auto"
    # A key from the avatar upload; omitted keeps the current picture.
    avatar_key: Optional[str] = Field(default=None, max_length=500)
    remove_avatar: bool = False
    enabled: bool = True


class CreatorIntroAvatarRequest(BaseModel):
    content_type: AvatarType
    size_bytes: int = Field(..., gt=0, le=10 * 1024 * 1024)


class CreatorIntroAvatarUpload(BaseModel):
    key: str
    url: str
    content_type: str


class CreatorIntroResponse(BaseModel):
    status: Literal["draft", "rendering", "ready", "failed"]
    platform: Platform
    niche: Optional[str] = None
    channel_name: str
    handle: Optional[str] = None
    about: str
    tagline: Optional[str] = None
    theme: IntroTheme
    theme_used: Optional[Literal["light", "dark"]] = None
    avatar_url: Optional[str] = None
    enabled: bool
    # One playable URL per rendition ("9x16", "16x9", "1x1"); empty until rendered.
    preview_urls: dict[str, str] = Field(default_factory=dict)
    duration_s: float
    error: Optional[str] = None
    updated_at: datetime
