"""A creator's channel intro: made once, played before every export.

One row per user. The creator's inputs are kept as typed; ``tagline`` and
``theme_used`` hold what the last render actually showed, and ``files`` maps
each rendition ("9x16", "16x9", "1x1") to its S3 key.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class IntroStatus(str, enum.Enum):
    DRAFT = "draft"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class CreatorIntro(Base):
    __tablename__ = "creator_intros"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True,
    )
    status: Mapped[IntroStatus] = mapped_column(
        Enum(IntroStatus, values_callable=lambda obj: [e.value for e in obj], name="creator_intro_status"),
        default=IntroStatus.DRAFT, nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(20), default="youtube", nullable=False)
    niche: Mapped[str | None] = mapped_column(String(60), nullable=True)
    channel_name: Mapped[str] = mapped_column(String(120), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    about: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Typed by the creator, or written by the AI when they left it empty.
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # "auto" lets the AI pick light or dark for the niche.
    theme: Mapped[str] = mapped_column(String(10), default="auto", nullable=False)
    theme_used: Mapped[str | None] = mapped_column(String(10), nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    files: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # Added to exports unless the creator turns it off (each export can still skip it).
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
