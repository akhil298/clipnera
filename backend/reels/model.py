"""A reel built from a creator's images, a script and B-roll.

The reel moves draft -> planning -> ready (scene board) -> rendering -> done.
Images, scenes and the voiceover's word timings are small JSON documents on
the row: they are always read and written whole, together with the reel.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ReelStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    READY = "ready"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class ReelProject(Base):
    __tablename__ = "reel_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ReelStatus] = mapped_column(
        Enum(ReelStatus, values_callable=lambda obj: [e.value for e in obj], name="reel_status"),
        default=ReelStatus.DRAFT, nullable=False,
    )
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    style: Mapped[str] = mapped_column(String(40), default="clean", nullable=False)
    # [{key, content_type, description}]
    images: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    voiceover_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # [{start, end, word}] of the voiceover, for scene timing and captions.
    words: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # [{start, end, text, kind, image_index, asset_id, query, subject, headline, alternates}]
    scenes: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    output_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
