"""What users do with generated clips: the free labels that say which clips were good.

A clip that is exported, edited or published was worth something to its owner;
comparing those rates across ``director_version`` values is how a prompt or
model change is judged on real use rather than on taste.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ClipEventKind(str, enum.Enum):
    EXPORTED = "exported"
    EDITED = "edited"
    PUBLISHED = "published"


class ClipEvent(Base):
    __tablename__ = "clip_events"
    __table_args__ = (Index("ix_clip_events_clip_kind", "clip_id", "kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_clips.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # A plain string rather than a Postgres enum, so adding a kind needs no migration.
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
