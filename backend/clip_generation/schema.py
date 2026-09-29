from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from hook_transitions.schema import HookTransitionApplied, HookTransitionConfig


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class VisualSubject(BaseModel):
    label: str
    confidence: float = 0.0
    bounding_box: BoundingBox
    pixel_bounding_box: Optional[BoundingBox] = None
    is_speaker: bool = False
    speaker: Optional[str] = None
    role: Optional[str] = None


class VisualFrameAnalysis(BaseModel):
    timestamp: float
    frame_width: int
    frame_height: int
    description: str = ""
    subjects: list[VisualSubject] = Field(default_factory=list)
    faces: list[VisualSubject] = Field(default_factory=list)
    objects: list[VisualSubject] = Field(default_factory=list)
    on_screen_text: list[Any] = Field(default_factory=list)
    scene: str = ""
    camera_shot: str = ""
    body_position: str = ""
    speaker: Optional[str] = None
    visual_quality: dict[str, Any] = Field(default_factory=dict)
    text_logos: list[Any] = Field(default_factory=list)
    main_subject_position: Optional[BoundingBox] = None
    suitable_for_vertical_crop: bool = True
    content_category: str = "unknown"


class CropTrackingPoint(BaseModel):
    timestamp: float
    bbox: BoundingBox


class ClipOutputFormat(BaseModel):
    crop: BoundingBox
    tracking: bool
    crop_tracking: list[CropTrackingPoint] = Field(default_factory=list)
    target_width: int
    target_height: int


class ContentCategoryResponse(BaseModel):
    category: str
    confidence: float
    keywords: list[str] = Field(default_factory=list)
    reasoning: Optional[str] = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


class TranscriptSummary(BaseModel):
    summary: str
    key_phrases: list[str] = Field(default_factory=list)
    sentiment: Optional[str] = None


class FrameAnalysisResult(BaseModel):
    scene_changes: list[float] = Field(default_factory=list)
    descriptions: dict[str, str] = Field(default_factory=dict)
    on_screen_text: list[dict] = Field(default_factory=list)
    frames: list[VisualFrameAnalysis] = Field(default_factory=list)


class TopicResearchResult(BaseModel):
    title: str
    summary: str
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    important_statements: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    key_moments: list[str] = Field(default_factory=list)
    context_required: list[str] = Field(default_factory=list)
    current_relevance: str = ""
    research_queries: list[str] = Field(default_factory=list)
    sources: list[Any] = Field(default_factory=list)


class VideoUnderstandingResult(BaseModel):
    topic_research: TopicResearchResult
    classification: ContentCategoryResponse
    frame_analysis: FrameAnalysisResult


class HighlightCandidate(BaseModel):
    start_time: float
    end_time: float
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    content_category: str
    transcript_excerpt: str = ""
    title: str = ""
    reason: str = ""
    scores: dict[str, float] = Field(default_factory=dict)


class ClipMetadata(BaseModel):
    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)
    suggested_emoji: str | None = None


class GeneratedClipResponse(BaseModel):
    video_id: str
    clip_id: str
    id: str
    project_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    start_time: float
    end_time: float
    duration_seconds: float
    hook_start: Optional[float] = None
    hook_end: Optional[float] = None
    timestamps: dict[str, float]
    reason: str = ""
    score: float
    scores: dict[str, float] = Field(default_factory=dict)
    content_category: Optional[str] = None
    presigned_url: Optional[str] = None
    poster_url: Optional[str] = None
    local_path: Optional[str] = None
    status: str
    subtitle_style_id: Optional[str] = None
    burned_subtitle_path: Optional[str] = None
    burned_presigned_url: Optional[str] = None
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    visual_analysis: list[VisualFrameAnalysis] = Field(default_factory=list)
    bounding_boxes: list[dict[str, Any]] = Field(default_factory=list)
    crop_tracking: dict[str, list[CropTrackingPoint]] = Field(default_factory=dict)
    output_formats: dict[str, ClipOutputFormat] = Field(default_factory=dict)
    output_files: dict[str, str] = Field(default_factory=dict)
    analysis_json: dict[str, Any] = Field(default_factory=dict)


class ClipListResponse(BaseModel):
    project_id: str
    clips: list[GeneratedClipResponse]
    total: int


class ClipGenerationResponse(BaseModel):
    project_id: str
    clips_generated: int
    clips: list[GeneratedClipResponse]
    analysis: dict[str, Any] = Field(default_factory=dict)


class StyleBurnRequest(BaseModel):
    style_id: Optional[str] = Field(None, description="SubtitleStyle ID to use for burning")
    style_type: str = Field("bold_captions", description="Subtitle style preset name")
    custom_config: Optional[dict] = Field(None, description="Custom style overrides")


class StyleBurnResponse(BaseModel):
    clip_id: str
    burned_presigned_url: str
    s3_key: str


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


class SocialExportTemplateResponse(BaseModel):
    platform: str
    aspect_ratio: str
    dimensions: list[int]
    subtitle_style: str
    config: dict[str, Any] = Field(default_factory=dict)
    is_preset: bool = True


class SocialExportRequest(BaseModel):
    platforms: list[str] = Field(
        default_factory=lambda: ["tiktok", "instagram_reels"],
        description="List of social platform names to export for (tiktok, instagram_reels, youtube_shorts, instagram_feed, linkedin, twitter, facebook, snapchat)",
    )
    style_type: Optional[str] = Field(
        default=None,
        description="Override subtitle style (falls back to platform default)",
    )
    custom_config: Optional[dict] = Field(default=None, description="Custom style overrides")
    clip_ids: Optional[list[str]] = Field(
        default=None,
        description="Export exactly these clips; when omitted the top-scored max_clips are exported",
    )
    aspect_ratio: Optional[str] = Field(
        default=None,
        description="Output size (9:16, 1:1, 4:5, 16:9); overrides each platform's default ratio",
    )
    max_clips: Optional[int] = Field(default=10, description="Maximum number of clips to export")
    max_duration: Optional[int] = Field(default=None, description="Trim exported clips to at most this many seconds")
    enable_emoji: Optional[bool] = Field(default=True, description="Auto-insert emojis based on transcript keywords")
    watermark_enabled: bool = Field(
        default=True,
        description="Overlay the Clipnera watermark; only paid plans may turn it off",
    )
    burn_subtitles: bool = True
    show_title: bool = Field(
        default=True,
        description="Overlay the clip title; applies only when burn_subtitles is on",
    )
    animation_speed: Optional[float] = Field(
        default=None,
        description="Caption animation speed; custom_config.animation_speed wins when both are set",
    )
    hook_transition: Optional[HookTransitionConfig] = Field(
        default=None,
        description="Bridge between each clip's hook and the clip; omitted means Auto",
    )
    bundle: bool = Field(
        default=False,
        description="Also pack every render into one ZIP, returned as bundle_presigned_url",
    )


class SocialExportClipResponse(BaseModel):
    clip_id: str
    platform: str
    aspect_ratio: str
    burned_presigned_url: Optional[str] = None
    local_path: Optional[str] = None
    s3_key: Optional[str] = None
    hook_transition: Optional[HookTransitionApplied] = None


class SocialExportResponse(BaseModel):
    project_id: str
    exported_clips: list[SocialExportClipResponse]
    platforms: list[str]
    total_exported: int
    # The watermark actually applied: a free plan gets it whatever was requested.
    watermark_enabled: bool
    # Set only when the request asked for a bundle.
    bundle_presigned_url: Optional[str] = None


class TranscriptEdits(BaseModel):
    """Transcript-tab edits, keyed by each word's source start time (``source_start``
    on the clip's captions), which is stable while caption order is not."""

    removed: list[float] = Field(default_factory=list, description="Words cut from the captions")
    highlighted: list[float] = Field(
        default_factory=list, description="The full set of emphasised words; replaces the automatic picks"
    )


class ClipEditorSettings(BaseModel):
    """What the editor last saved for a clip; each field is omitted until set."""

    aspect_ratio: Optional[str] = None
    # The editor's CaptionConfig, stored as sent so it round-trips exactly.
    caption_config: Optional[dict[str, Any]] = None
    hook_transition: Optional[HookTransitionConfig] = None
    watermark_enabled: Optional[bool] = None
    captions_enabled: Optional[bool] = None
    title_enabled: Optional[bool] = None
    transcript_edits: Optional[TranscriptEdits] = None
