from __future__ import annotations

from pydantic import BaseModel


class VersionQuality(BaseModel):
    director_version: str
    clips: int
    exported_share: float
    edited_share: float
    published_share: float


class ClipQualityReport(BaseModel):
    days: int
    versions: list[VersionQuality]
