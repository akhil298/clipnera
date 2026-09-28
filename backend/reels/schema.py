from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from broll.schema import BrollPreview

ReelStyle = Literal["clean", "bold", "neon", "warm"]
ReelAssetType = Literal[
    "image/jpeg", "image/png", "image/webp",
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a", "audio/webm",
]
SceneKind = Literal["image", "broll", "text"]


class ReelCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    topic: str | None = Field(None, max_length=500)
    script: str | None = Field(None, max_length=4000)
    # A language code ("en", "hi", "te") or a mix ("hinglish", "tenglish").
    language: str = Field("en", min_length=2, max_length=20)
    style: ReelStyle = "clean"


class ReelAssetFile(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: ReelAssetType
    size_bytes: int = Field(..., gt=0, le=60 * 1024 * 1024)


class ReelAssetsInitRequest(BaseModel):
    files: list[ReelAssetFile] = Field(..., min_length=1, max_length=31)


class ReelAssetUpload(BaseModel):
    key: str
    url: str
    content_type: str


class ReelAssetsInitResponse(BaseModel):
    uploads: list[ReelAssetUpload]


class ReelAssetsCompleteRequest(BaseModel):
    keys: list[str] = Field(..., min_length=1, max_length=31)


class ReelSceneResponse(BaseModel):
    index: int
    start: float
    end: float
    text: str
    kind: SceneKind
    image_index: int | None
    headline: str
    query: str
    generating: bool
    image_url: str | None
    footage: BrollPreview | None
    alternates: list[BrollPreview]


class ReelResponse(BaseModel):
    id: str
    title: str
    status: str
    topic: str | None
    script: str | None
    language: str
    style: str
    image_urls: list[str]
    has_voiceover: bool
    duration_s: float
    scenes: list[ReelSceneResponse]
    credits_estimate: int
    credits_charged: int
    output_url: str | None
    error: str | None
    created_at: datetime


class ReelSummary(BaseModel):
    id: str
    title: str
    status: str
    duration_s: float
    created_at: datetime
    # The reel's first image, shown as its cover in lists; None without images.
    cover_url: str | None = None


class ReelSceneUpdate(BaseModel):
    kind: SceneKind
    image_index: int | None = Field(None, ge=0)
    asset_id: str | None = None
    headline: str | None = Field(None, max_length=60)
