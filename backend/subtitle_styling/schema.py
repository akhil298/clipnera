from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


class SubtitleStylePresetResponse(BaseModel):
    id: str
    name: str
    style_type: str
    config: Optional[str]
    is_preset: bool


class SubtitleStyleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    style_type: str = Field(..., min_length=1, max_length=50)
    config: Optional[str] = None


class SubtitleBurnRequest(BaseModel):
    style_type: str = Field("bold_captions", min_length=1, max_length=50)
    custom_config: Optional[dict] = None
    enable_watermark: bool = True


class SubtitleBurnResponse(BaseModel):
    clip_id: str
    burned_presigned_url: str
    s3_key: str


class SubtitleStylePresetsResponse(BaseModel):
    presets: list[SubtitleStylePresetResponse]
