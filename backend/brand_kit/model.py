from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Boolean, Text, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CaptionPreset(str, enum.Enum):
    HORMOZI = "hormozi"
    MRBEAST = "mrbeast"
    NEON = "neon"
    CYBERPUNK = "cyberpunk"
    MINIMAL = "minimal"
    KARAOKE_YELLOW = "karaoke_yellow"
    SUNSET = "sunset"


class LogoPosition(str, enum.Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_position: Mapped[LogoPosition] = mapped_column(
        Enum(LogoPosition, values_callable=lambda obj: [e.value for e in obj], name="logo_position"),
        default=LogoPosition.TOP_RIGHT,
        nullable=False,
    )
    logo_opacity: Mapped[int] = mapped_column(Integer, default=85, nullable=False)
    logo_size: Mapped[int] = mapped_column(Integer, default=28, nullable=False)
    primary_color: Mapped[str] = mapped_column(String(9), default="#f59e0b", nullable=False)
    secondary_color: Mapped[str] = mapped_column(String(9), default="#f43f5e", nullable=False)
    preferred_font: Mapped[str] = mapped_column(String(100), default="Syne", nullable=False)
    default_preset: Mapped[CaptionPreset] = mapped_column(
        Enum(CaptionPreset, values_callable=lambda obj: [e.value for e in obj], name="caption_preset"),
        default=CaptionPreset.HORMOZI,
        nullable=False,
    )
    auto_emojis: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    outro_cta_text: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
