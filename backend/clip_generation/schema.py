from __future__ import annotations

import json
from typing import Optional
from pydantic import BaseModel, Field


class ContentCategoryResponse(BaseModel):
    category: str
    confidence: float
    keywords: list[str] = Field(default_factory=list)
    reasoning: Optional[str] = None


class TranscriptSummary(BaseModel):
    summary: str
    key_phrases: list[str] = Field(default_factory=list)
    sentiment: Optional[str] = None


class FrameAnalysisResult(BaseModel):
    scene_changes: list[float] = Field(default_factory=list, description="Timestamps of detected scene changes in seconds")
    descriptions: dict[str, str] = Field(default_factory=dict, description="timestamp -> description mapping")
    on_screen_text: list[dict] = Field(default_factory=list)


class HighlightCandidate(BaseModel):
    start_time: float
    end_time: float
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    content_category: str
    transcript_excerpt: str = ""


class ClipMetadata(BaseModel):
    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)
    suggested_emoji: str | None = None


class GeneratedClipResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str]
    start_time: float
    end_time: float
    duration_seconds: float
    score: float
    content_category: Optional[str]
    presigned_url: Optional[str]
    status: str
    subtitle_style_id: Optional[str]
    burned_subtitle_path: Optional[str]
    burned_presigned_url: Optional[str]


class ClipListResponse(BaseModel):
    project_id: str
    clips: list[GeneratedClipResponse]
    total: int


class StyleBurnRequest(BaseModel):
    style_id: Optional[str] = Field(None, description="SubtitleStyle ID to use for burning")
    style_type: str = Field("bold_captions", description="Subtitle style preset name")
    custom_config: Optional[dict] = Field(None, description="Custom style overrides")


class StyleBurnResponse(BaseModel):
    clip_id: str
    burned_presigned_url: str
    local_path: str


class SubtitleStyleResponse(BaseModel):
    id: str
    name: str
    style_type: str
    config: Optional[str]
    is_preset: bool


class ContentAnalysisResponse(BaseModel):
    project_id: str
    category: ContentCategoryResponse
    transcript_summary: TranscriptSummary
    frame_analysis: FrameAnalysisResult
