from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateBrandKitRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    logo_url: Optional[str] = None
    logo_position: str = "top_right"
    logo_opacity: int = Field(default=85, ge=20, le=100)
    logo_size: int = Field(default=28, ge=18, le=48)
    primary_color: str = Field(default="#f59e0b", min_length=7, max_length=7)
    secondary_color: str = Field(default="#f43f5e", min_length=7, max_length=7)
    preferred_font: str = Field(default="Syne", max_length=100)
    default_preset: str = Field(default="hormozi")
    auto_emojis: bool = True
    outro_cta_text: str = Field(default="", max_length=500)


class BrandKitResponse(BaseModel):
    id: str
    userId: str
    brandName: str
    logoUrl: Optional[str] = None
    logoPosition: str
    logoOpacity: int
    logoSize: int
    primaryColor: str
    secondaryColor: str
    preferredFont: str
    defaultPreset: str
    autoEmojis: bool
    outroCtaText: str
    # False while the kit still holds the defaults it was auto-created with, so
    # the editor only applies a kit the user actually set up.
    isCustomized: bool
    createdAt: str
    updatedAt: str
