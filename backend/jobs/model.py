from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class BackgroundJob(Base):
    """One queued job for ``JOB_QUEUE_BACKEND=postgres`` (see ``jobs.postgres``)."""

    __tablename__ = "background_jobs"
    __table_args__ = (Index("ix_background_jobs_claim", "status", "run_after"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    # queued -> running -> done | failed; a crashed run goes back to queued.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    run_after: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
