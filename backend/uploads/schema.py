from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from pipeline.schema import PipelineStartRequest

VideoContentType = Literal["video/mp4", "video/quicktime", "video/webm", "video/x-matroska"]


class VideoUploadInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: VideoContentType
    size_bytes: int = Field(..., gt=0)
    # Read by the browser from the file's metadata, so an over-long video is
    # refused before any bytes are sent; the pipeline re-checks the real length.
    duration_seconds: float | None = Field(None, gt=0)


class VideoUploadInitResponse(BaseModel):
    project_id: str
    upload_id: str
    part_size: int
    part_urls: list[str]


class UploadedPart(BaseModel):
    part_number: int = Field(..., ge=1, le=10_000)
    etag: str = Field(..., min_length=1)


class VideoUploadCompleteRequest(BaseModel):
    upload_id: str = Field(..., min_length=1)
    parts: list[UploadedPart] = Field(..., min_length=1)
    # Started by the server once the upload is ready, as for YouTube downloads.
    pipeline: PipelineStartRequest | None = None

    @field_validator("parts")
    @classmethod
    def _parts_are_unique(cls, parts: list[UploadedPart]) -> list[UploadedPart]:
        if len({p.part_number for p in parts}) != len(parts):
            raise ValueError("part numbers must be unique")
        return sorted(parts, key=lambda p: p.part_number)


class VideoUploadAbortRequest(BaseModel):
    upload_id: str = Field(..., min_length=1)


class VideoUploadCompleteResponse(BaseModel):
    project_id: str
    status: str
