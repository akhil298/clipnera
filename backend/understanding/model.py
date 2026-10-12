"""One row per editor project asset: whether its MUD is built, and where it is."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AnalysisStatus:
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class MediaAnalysis(Base):
    __tablename__ = "media_analyses"
    __table_args__ = (UniqueConstraint("project_id", "asset_id", name="uq_media_analyses_project_asset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The Timeline asset it describes, and that asset's S3 key when the analysis was queued.
    asset_id: Mapped[str] = mapped_column(String(40), nullable=False)
    asset_key: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=AnalysisStatus.PENDING)
    # The analyzer at work while running (understanding.build.STAGES).
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # What was found (understanding.findings.AnalysisFindings), once ready.
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # The MUD JSON in S3, once ready.
    mud_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
