from __future__ import annotations

import enum
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, ForeignKey, Enum, DateTime, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"
    SKIPPED = "skipped"


class PipelineStepType(str, enum.Enum):
    DOWNLOAD = "download"
    AUDIO_EXTRACTION = "audio_extraction"
    AI_NOISE_CANCELLATION = "ai_noise_cancellation"
    TRANSCRIPTION = "transcription"
    TOPIC_RESEARCH = "topic_research"
    VISUAL_ANALYSIS = "visual_analysis"
    CONTENT_CLASSIFICATION = "content_classification"
    HIGHLIGHT_DETECTION = "highlight_detection"
    BOUNDING_BOX_DETECTION = "bounding_box_detection"
    SCORING = "scoring"
    METADATA_GENERATION = "metadata_generation"
    ASPECT_RATIO_RENDER = "aspect_ratio_render"
    CLIP_GENERATION = "clip_generation"
    SUBTITLE_STYLING = "subtitle_styling"
    BURN_IN_EXPORT = "burn_in_export"
    DEPTH_CAPTIONS = "depth_captions"

    _aliases: dict[str, PipelineStepType] = {}

    @classmethod
    def resolve(cls, value: str) -> PipelineStepType:
        alias_map = {
            "caption_styling": cls.SUBTITLE_STYLING,
            "auto_reframe": cls.ASPECT_RATIO_RENDER,
            "reframe": cls.ASPECT_RATIO_RENDER,
            "bbox_detection": cls.BOUNDING_BOX_DETECTION,
            "export": cls.BURN_IN_EXPORT,
            "depth_captions": cls.DEPTH_CAPTIONS,
        }
        if value in alias_map:
            return alias_map[value]
        return cls(value)


class PipelineState(Base):
    __tablename__ = "pipeline_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_step: Mapped[str] = mapped_column(
        Enum(PipelineStepType, values_callable=lambda obj: [e.value for e in obj], name="pipeline_step_type"),
        default=PipelineStepType.DOWNLOAD,
        nullable=False,
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PipelineStepLog(Base):
    __tablename__ = "pipeline_step_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    pipeline_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step: Mapped[str] = mapped_column(
        Enum(PipelineStepType, values_callable=lambda obj: [e.value for e in obj], name="pipeline_step_type"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(StepStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=StepStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
