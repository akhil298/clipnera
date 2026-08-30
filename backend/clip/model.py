from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, ForeignKey, Enum, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    UPLOADED = "uploaded"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, values_callable=lambda obj: [e.value for e in obj]), default=ProjectStatus.PENDING, nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    presigned_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
