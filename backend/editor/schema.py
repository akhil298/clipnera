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

AspectRatio = Literal["9:16", "1:1", "4:5", "16:9"]


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


class EditorOpsResponse(BaseModel):
    version: int
    timeline: Timeline
