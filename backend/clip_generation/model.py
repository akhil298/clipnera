from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, ForeignKey, Enum, DateTime, Integer, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ContentCategory(str, enum.Enum):
    GAMING = "gaming"
    PODCAST_INTERVIEW = "podcast_interview"
    TUTORIAL_EDUCATIONAL = "tutorial_educational"
    VLOG = "vlog"
    COMEDY = "comedy"
    REACTION = "reaction"
    MUSIC = "music"
    NEWS_POLITICS = "news_politics"
    TECH = "tech"
    FITNESS_HEALTH = "fitness_health"
    FOOD = "food"
    SPORTS = "sports"
    UNKNOWN = "unknown"


class VideoAnalysis(Base):
    __tablename__ = "video_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_changes: Mapped[str | None] = mapped_column(Text, nullable=True)
    frame_descriptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class GeneratedClip(Base):
    __tablename__ = "generated_clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    content_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    presigned_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtitle_style_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subtitle_styles.id", ondelete="SET NULL"), nullable=True
    )
    burned_subtitle_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    burned_presigned_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
