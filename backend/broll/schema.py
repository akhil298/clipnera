from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BrollAssetResponse(BaseModel):
    id: str
    kind: str
    source: str
    source_id: str
    source_url: str | None
    title: str
    tags: list[str]
    duration_s: float
    width: int
    height: int
    orientation: str
    quality_score: float
    status: str
    status_reason: str | None
    license_code: str | None
    attribution_text: str | None
    thumb_url: str | None
    proxy_url: str | None
    created_at: datetime


class BrollAssetListResponse(BaseModel):
    items: list[BrollAssetResponse]
    total: int


class BrollIngestRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    per_source: int = Field(5, ge=1, le=20)
    sources: list[str] | None = None


class BrollIngestResponse(BaseModel):
    query: str
    queued: bool


class BrollStatusRequest(BaseModel):
    status: Literal["live", "blocked", "taken_down"]
    reason: str | None = Field(None, max_length=500)


class BrollPreview(BaseModel):
    """What a user may see of a library shot: a low-resolution preview, never the master."""

    id: str
    title: str
    duration_s: float
    thumb_url: str | None
    proxy_url: str | None
    attribution_text: str | None


class BrollPlacementResponse(BaseModel):
    index: int
    start: float
    end: float
    query: str
    score: float
    generating: bool
    asset: BrollPreview | None
    alternates: list[BrollPreview]


class ClipBrollResponse(BaseModel):
    clip_id: str
    placements: list[BrollPlacementResponse]


class BrollPlacementUpdate(BaseModel):
    """Swap a cutaway's shot (``asset_id``) or remove the cutaway (``remove``)."""

    asset_id: str | None = None
    remove: bool = False


class GenerateShotRequest(BaseModel):
    """Generate an AI shot for a cutaway or scene (Pro). ``shot`` overrides the planned description."""

    shot: str | None = Field(None, min_length=3, max_length=200)
