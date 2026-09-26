from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
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


class SocialPlatform(str, enum.Enum):
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_FEED = "instagram_feed"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    SNAPCHAT = "snapchat"


SOCIAL_PLATFORM_DEFAULTS: dict[str, dict[str, Any]] = {
    SocialPlatform.TIKTOK.value: {
        "aspect_ratio": "9:16",
        "dimensions": [1080, 1920],
        "subtitle_style": "tiktok",
        "max_duration": 60,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 4,
        "position_y": 0.78,
        "emoji_enabled": True,
        "word_pop": True,
        "animation": "karaoke",
    },
    SocialPlatform.INSTAGRAM_REELS.value: {
        "aspect_ratio": "9:16",
        "dimensions": [1080, 1920],
        "subtitle_style": "default",
        "max_duration": 90,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 4,
        "position_y": 0.80,
        "emoji_enabled": True,
        "word_pop": True,
        "animation": "karaoke",
    },
    SocialPlatform.YOUTUBE_SHORTS.value: {
        "aspect_ratio": "9:16",
        "dimensions": [1080, 1920],
        "subtitle_style": "mrbeast",
        "max_duration": 60,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 3,
        "position_y": 0.70,
        "emoji_enabled": True,
        "word_pop": True,
        "animation": "karaoke",
    },
    SocialPlatform.INSTAGRAM_FEED.value: {
        "aspect_ratio": "1:1",
        "dimensions": [1080, 1080],
        "subtitle_style": "minimal",
        "max_duration": 120,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 6,
        "position_y": 0.82,
        "emoji_enabled": False,
        "word_pop": False,
        "animation": "fade",
    },
    SocialPlatform.LINKEDIN.value: {
        "aspect_ratio": "1:1",
        "dimensions": [1080, 1080],
        "subtitle_style": "podcast",
        "max_duration": 120,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 5,
        "position_y": 0.80,
        "emoji_enabled": False,
        "word_pop": False,
        "animation": "karaoke",
    },
    SocialPlatform.TWITTER.value: {
        "aspect_ratio": "16:9",
        "dimensions": [1920, 1080],
        "subtitle_style": "minimal",
        "max_duration": 140,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 6,
        "position_y": 0.82,
        "emoji_enabled": False,
        "word_pop": False,
        "animation": "fade",
    },
    SocialPlatform.FACEBOOK.value: {
        "aspect_ratio": "16:9",
        "dimensions": [1920, 1080],
        "subtitle_style": "boxed",
        "max_duration": 120,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 4,
        "position_y": 0.80,
        "emoji_enabled": True,
        "word_pop": True,
        "animation": "karaoke",
    },
    SocialPlatform.SNAPCHAT.value: {
        "aspect_ratio": "9:16",
        "dimensions": [1080, 1920],
        "subtitle_style": "tiktok",
        "max_duration": 60,
        "caption_max_chars": 42,
        "caption_max_words_per_line": 4,
        "position_y": 0.78,
        "emoji_enabled": True,
        "word_pop": True,
        "animation": "karaoke",
    },
}


class SocialExportTemplate(Base):
    __tablename__ = "social_export_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False)
    subtitle_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


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
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # Source-video span of the teaser played before the clip; null when the
    # clip has none. duration_seconds includes it.
    hook_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    hook_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON [[start, end], ...] in source seconds: the parts of the source the
    # clip's body is stitched from, in play order, with pauses and tangents
    # left out. Null means the single span [start_time, end_time).
    edit_spans: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which director prompt and pipeline made this clip; null for clips made
    # before versioning. Lets a prompt change be judged on how users treat it.
    director_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scores: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    presigned_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtitle_style_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subtitle_styles.id", ondelete="SET NULL"), nullable=True
    )
    burned_subtitle_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    burned_presigned_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    bounding_boxes: Mapped[str | None] = mapped_column(Text, nullable=True)
    crop_tracking: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_formats: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_files: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ClipEditorSettings as JSON: what the editor last saved for this clip.
    editor_settings: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
