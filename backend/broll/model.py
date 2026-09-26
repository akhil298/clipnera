"""The B-roll library: stock shots, motion-graphic renders and generated clips.

Every asset is one usable shot with a permanent id and a unique
``(source, source_id, shot_index)`` key, so it can be found, re-fetched or taken
down by reference. The library is internal: users only ever receive assets
composited into their own renders, never as downloadable files, because the
stock licences allow use in edited works but not redistribution.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    ARRAY, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AssetKind(str, enum.Enum):
    STOCK = "stock"
    TEMPLATE = "template"
    GENERATED = "generated"
    USER = "user"


class AssetStatus(str, enum.Enum):
    INGESTING = "ingesting"
    LIVE = "live"
    BLOCKED = "blocked"
    TAKEN_DOWN = "taken_down"
    FAILED = "failed"


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, values_callable=lambda obj: [e.value for e in obj], name=name)


class BrollAsset(Base):
    __tablename__ = "broll_assets"
    __table_args__ = (
        UniqueConstraint("source", "source_id", "shot_index", name="uq_broll_assets_source_shot"),
        Index("ix_broll_assets_search", text("to_tsvector('english', search_text)"), postgresql_using="gin"),
        Index("ix_broll_assets_status_orientation", "status", "orientation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    kind: Mapped[AssetKind] = mapped_column(_enum(AssetKind, "broll_asset_kind"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    shot_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    caption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list, nullable=False)
    # title + caption + tags, the text full-text search runs over.
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orientation: Mapped[str] = mapped_column(String(10), default="landscape", nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    has_people: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_logos: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[AssetStatus] = mapped_column(
        _enum(AssetStatus, "broll_asset_status"), default=AssetStatus.INGESTING, nullable=False,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null for the shared library; set for a user's private generated or uploaded clip.
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vertical_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    proxy_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumb_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BrollLicense(Base):
    """Proof of the licence an asset was taken under, as it stood when fetched."""

    __tablename__ = "broll_licenses"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), primary_key=True,
    )
    license_code: Mapped[str] = mapped_column(String(40), nullable=False)
    license_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    author_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    commercial_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # The source API's record for the asset, stored as fetched.
    source_record_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollUsage(Base):
    """Every placement of an asset in a render; swaps are the quality signal."""

    __tablename__ = "broll_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("video_projects.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    scene_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    picked_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    swapped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
