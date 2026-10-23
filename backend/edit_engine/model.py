"""A reel edited from a creator's raw footage, and the music it can use.

An edit moves draft -> analyzing -> planned -> rendering -> done. Sources,
analysis, plan and timeline are JSON documents on the row: each is read and
written whole, together with the edit, as reels/ does.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from subtitle_styling.templates import DEFAULT_STYLE


class EditStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    PLANNED = "planned"
    RENDERING = "rendering"
    DONE = "done"
    FAILED = "failed"


class MusicStatus(str, enum.Enum):
    LIVE = "live"
    PULLED = "pulled"


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, values_callable=lambda obj: [e.value for e in obj], name=name)


class EditProject(Base):
    __tablename__ = "edit_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[EditStatus] = mapped_column(_enum(EditStatus, "edit_status"), default=EditStatus.DRAFT, nullable=False)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    # auto | spoken | voiceover | onscreen | direction (see edit_engine.script)
    script_mode: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    intent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    caption_style: Mapped[str] = mapped_column(String(60), default=DEFAULT_STYLE, nullable=False)
    # 0 lets the director choose.
    target_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    autopilot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The OpenAI deployment and reasoning effort picked for the director and chat; None is the plan's own.
    ai_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_effort: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # A reel whose editing style to copy, by link; an uploaded one is a "reference" source instead.
    reference_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # A YouTube video to edit, fetched into ``sources`` as a video when the edit starts.
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # "classic" (analyse, plan, review, render) or "premium" (the reel engine edits end to end in one job).
    engine: Mapped[str] = mapped_column(String(20), default="classic", server_default="classic", nullable=False)
    # The reel engine's Edit Plan (JSON), with its progress while it runs.
    premium: Mapped[str] = mapped_column(Text, default="{}", server_default="{}", nullable=False)
    # Every reel cut from the footage (JSON list of {key, duration, title}); the first is also ``output_key``.
    reels: Mapped[str] = mapped_column(Text, default="[]", server_default="[]", nullable=False)
    # [{key, kind: video|image|voice|reference, name, content_type, duration, width, height, has_audio, proxy_key}]
    sources: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # Perception and transcript: words, sentences, shots, photos, retakes, content type.
    analysis: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # The director's decisions by ID plus the user's changes to them.
    plan: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # The compiled multi-track timeline the preview plays and the renderer draws.
    timeline: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    raw_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    replans: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chat_edits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    renders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Whether this edit's plan was made by the Opus director, which prices it higher.
    opus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The music (and licence) the last render used, kept with the reel.
    music_credit: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class MusicTrack(Base):
    """A free-licence track and the licence record we took when downloading it."""

    __tablename__ = "music_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    artist: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    licence: Mapped[str] = mapped_column(String(40), nullable=False)
    licence_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Empty for licences that need no credit.
    credit_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    commercial_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    edit_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # S3 copy of the track page as it was on the day we downloaded the track.
    snapshot_key: Mapped[str] = mapped_column(String(500), nullable=False)
    audio_key: Mapped[str] = mapped_column(String(500), nullable=False)
    audio_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    duration_s: Mapped[float] = mapped_column(Float, nullable=False)
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mood: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # 0 (calm) .. 1 (driving)
    energy: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    status: Mapped[MusicStatus] = mapped_column(_enum(MusicStatus, "music_status"), default=MusicStatus.LIVE, nullable=False)
    added_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
