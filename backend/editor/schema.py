"""Request and response models for /editor.

Mirrored field for field by the ``Editor*`` types in frontend/lib/api.ts; the
Timeline and its operations are mirrored by frontend/lib/editor/timeline.ts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from editor.ops import Op
from editor.timeline import Timeline
from understanding.findings import AnalysisFindings

AspectRatio = Literal["9:16", "1:1", "4:5", "16:9"]
EditorAssetType = Literal[
    "video/mp4", "video/quicktime", "video/webm",
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a", "audio/webm", "audio/ogg",
]
# One presigned PUT carries the file, and S3 takes at most 5 GB that way.
MAX_ASSET_BYTES = 2 * 1024 * 1024 * 1024


class EditorProjectCreate(BaseModel):
    title: str = Field("Untitled project", min_length=1, max_length=300)
    aspect: AspectRatio = "9:16"


class EditorOpsRequest(BaseModel):
    # The project version the client's operations were made against.
    base_version: int = Field(..., ge=0)
    ops: list[Op] = Field(..., min_length=1, max_length=200)


class EditorProjectSummary(BaseModel):
    id: str
    title: str
    version: int
    # Seconds, for the project list.
    duration_s: float
    created_at: datetime
    updated_at: datetime


class EditorProjectResponse(EditorProjectSummary):
    timeline: Timeline
    # Asset id -> a signed URL the studio plays and decodes it from; valid for an hour.
    asset_urls: dict[str, str]


class EditorAssetInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: EditorAssetType
    size_bytes: int = Field(..., gt=0, le=MAX_ASSET_BYTES)


class EditorAssetUpload(BaseModel):
    """Where the browser PUTs the file (sending ``content_type``), and the key to add it under with ``add_asset``."""

    key: str
    url: str
    content_type: str


class EditorOpsResponse(BaseModel):
    version: int
    timeline: Timeline


class MediaAnalysisResponse(BaseModel):
    """How far the AI has got understanding one asset of the project."""

    asset_id: str
    status: Literal["pending", "running", "ready", "failed"]
    # While running: "shots", "transcript", "music" or "reading".
    stage: str | None
    findings: AnalysisFindings | None
    error: str | None
    updated_at: datetime
