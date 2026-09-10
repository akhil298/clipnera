from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, ForeignKey, Enum, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SubtitleStyleType(str, enum.Enum):
    BOLD_CAPTIONS = "bold_captions"
    KARAOKE = "karaoke"
    MINIMAL = "minimal"
    BOXED = "boxed"
    NEON = "neon"
    TYPEWRITER = "typewriter"


class SubtitleStyle(Base):
    __tablename__ = "subtitle_styles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    style_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
