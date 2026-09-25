from __future__ import annotations

from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class DepthMode(str, Enum):
    BEHIND = "behind"
    FRONT = "front"
    AUTO = "auto"
    GIANT_EDITORIAL = "giant_editorial"


class AnimationType(str, Enum):
    NONE = "none"
    FADE = "fade"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    POP = "pop"


class TextDepth(str, Enum):
    BEHIND = "behind"
    FRONT = "front"


class StylePreset(str, Enum):
    GIANT_EDITORIAL = "giant_editorial"
    GIANT_CENTER = "giant_center"
    KINETIC_BOLD = "kinetic_bold"
    MINIMAL = "minimal"
    CINEMATIC = "cinematic"
    NEWS = "news"
    PUNCH = "punch"
    DOCUMENTARY = "documentary"
    CREATOR = "creator"
    NEON = "neon"


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class PersonTrackPoint(BaseModel):
    frame: int
    bbox: BoundingBox
    confidence: float = Field(ge=0, le=1)


class PersonTrack(BaseModel):
    track_id: str
    frames: list[PersonTrackPoint]


class VideoMetadata(BaseModel):
    width: int
    height: int
    fps: float
    duration: float
    aspect_ratio: str


class SafeZones(BaseModel):
    top: float = Field(default=0.15, ge=0, le=1)
    bottom: float = Field(default=0.15, ge=0, le=1)
    left: float = Field(default=0.05, ge=0, le=1)
    right: float = Field(default=0.05, ge=0, le=1)


class StyleConfig(BaseModel):
    font_family: str = "Inter"
    font_weight: int = Field(default=800, ge=100, le=900)
    uppercase: bool = True
    tracking: float = -2
    line_height: float = 0.9
    default_scale: float = Field(default=1.2, ge=0.5, le=2.0)
    animation_in: AnimationType = AnimationType.SCALE_UP
    animation_out: AnimationType = AnimationType.FADE
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = Field(default=3, ge=0, le=10)
    shadow: bool = True
    glow: bool = False


STYLE_PRESETS: dict[StylePreset, StyleConfig] = {
    StylePreset.GIANT_EDITORIAL: StyleConfig(
        font_family="Inter",
        font_weight=900,
        uppercase=True,
        tracking=-5,
        line_height=0.85,
        default_scale=1.8,
        animation_in=AnimationType.SCALE_UP,
        animation_out=AnimationType.FADE,
        font_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=4,
        shadow=True,
        glow=False,
    ),
    StylePreset.GIANT_CENTER: StyleConfig(
        font_family="Inter",
        font_weight=800,
        uppercase=True,
        tracking=-3,
        line_height=0.9,
        default_scale=1.5,
        animation_in=AnimationType.POP,
        animation_out=AnimationType.FADE,
        font_color="#FFFF00",
        stroke_color="#FF0000",
        stroke_width=5,
        shadow=True,
        glow=True,
    ),
    StylePreset.KINETIC_BOLD: StyleConfig(
        font_family="Arial",
        font_weight=800,
        uppercase=True,
        tracking=-2,
        line_height=0.95,
        default_scale=1.3,
        animation_in=AnimationType.SLIDE_LEFT,
        animation_out=AnimationType.SLIDE_RIGHT,
        font_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=3,
        shadow=True,
        glow=False,
    ),
    StylePreset.MINIMAL: StyleConfig(
        font_family="Inter",
        font_weight=400,
        uppercase=False,
        tracking=0,
        line_height=1.2,
        default_scale=1.0,
        animation_in=AnimationType.FADE,
        animation_out=AnimationType.FADE,
        font_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=1,
        shadow=False,
        glow=False,
    ),
    StylePreset.CINEMATIC: StyleConfig(
        font_family="Georgia",
        font_weight=700,
        uppercase=True,
        tracking=2,
        line_height=1.1,
        default_scale=1.1,
        animation_in=AnimationType.FADE,
        animation_out=AnimationType.FADE,
        font_color="#FFFFFF",
        stroke_color="#1A1A1A",
        stroke_width=2,
        shadow=True,
        glow=False,
    ),
    StylePreset.NEWS: StyleConfig(
        font_family="Arial",
        font_weight=700,
        uppercase=True,
        tracking=0,
        line_height=1.0,
        default_scale=1.0,
        animation_in=AnimationType.NONE,
        animation_out=AnimationType.NONE,
        font_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=2,
        shadow=True,
        glow=False,
    ),
    StylePreset.PUNCH: StyleConfig(
        font_family="Impact",
        font_weight=900,
        uppercase=True,
        tracking=-4,
        line_height=0.9,
        default_scale=1.4,
        animation_in=AnimationType.POP,
        animation_out=AnimationType.SCALE_DOWN,
        font_color="#FFE000",
        stroke_color="#000000",
        stroke_width=4,
        shadow=True,
        glow=True,
    ),
    StylePreset.DOCUMENTARY: StyleConfig(
        font_family="Georgia",
        font_weight=500,
        uppercase=False,
        tracking=1,
        line_height=1.3,
        default_scale=0.9,
        animation_in=AnimationType.FADE,
        animation_out=AnimationType.FADE,
        font_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=1,
        shadow=False,
        glow=False,
    ),
    StylePreset.CREATOR: StyleConfig(
        font_family="Arial",
        font_weight=800,
        uppercase=True,
        tracking=-2,
        line_height=0.95,
        default_scale=1.2,
        animation_in=AnimationType.SCALE_UP,
        animation_out=AnimationType.FADE,
        font_color="#00FFFF",
        stroke_color="#000000",
        stroke_width=3,
        shadow=True,
        glow=True,
    ),
    StylePreset.NEON: StyleConfig(
        font_family="Arial",
        font_weight=700,
        uppercase=True,
        tracking=-1,
        line_height=1.0,
        default_scale=1.1,
        animation_in=AnimationType.POP,
        animation_out=AnimationType.FADE,
        font_color="#FF00FF",
        stroke_color="#002A6B",
        stroke_width=2,
        shadow=False,
        glow=True,
    ),
}


class CaptionSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    depth: TextDepth = TextDepth.BEHIND
    position: BoundingBox
    scale: float = Field(default=1.0, ge=0.5, le=2.0)
    rotation: float = Field(default=0.0, ge=-8.0, le=8.0)
    opacity: float = Field(default=0.95, ge=0, le=1)
    animation_in: AnimationType = AnimationType.SCALE_UP
    animation_out: AnimationType = AnimationType.FADE
    subject_id: Optional[str] = None

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end must be greater than start")
        return v


class CanvasConfig(BaseModel):
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)


class EditPlan(BaseModel):
    version: str = "1.0"
    canvas: CanvasConfig
    style: StyleConfig
    segments: list[CaptionSegment]
    depth_mode: DepthMode = DepthMode.AUTO
    safe_zones: SafeZones = Field(default_factory=SafeZones)
    subject_tracks: dict[str, PersonTrack] = Field(default_factory=dict)


class DepthCaptionRequest(BaseModel):
    project_id: str
    clip_id: str
    style: StylePreset = StylePreset.GIANT_EDITORIAL
    depth_mode: DepthMode = DepthMode.AUTO
    language: str = "en"
    custom_style: Optional[StyleConfig] = None


class DepthCaptionJobStatus(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    ANALYZING = "analyzing"
    TRACKING = "tracking"
    SEGMENTING = "segmenting"
    MATTING = "matting"
    PLANNING = "planning"
    COMPOSITING = "compositing"
    ENCODING = "encoding"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class DepthCaptionJobResponse(BaseModel):
    job_id: str
    status: DepthCaptionJobStatus
    progress: int = 0
    stage: str = ""
    preview_url: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None
    retryable: bool = False


class DepthCaptionsRenderRequest(BaseModel):
    project_id: str
    clip_id: str
    style: StylePreset = StylePreset.GIANT_EDITORIAL
    depth_mode: DepthMode = DepthMode.AUTO
    language: str = "en"


class DepthCaptionsJobStatusResponse(BaseModel):
    job_id: str
    status: DepthCaptionJobStatus
    progress: int
    stage: str
    preview_url: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None


class MaskQualityMetrics(BaseModel):
    temporal_stability: float = Field(ge=0, le=1)
    boundary_quality: float = Field(ge=0, le=1)
    subject_confidence: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1)


class PipelineStage(str, Enum):
    PREPARATION = "preparation"
    ANALYSIS = "analysis"
    TRACKING = "tracking"
    SEGMENTATION = "segmentation"
    MATTING = "matting"
    QUALITY_CHECK = "quality_check"
    PLANNING = "planning"
    COMPOSITION = "composition"
    PREVIEW = "preview"
    RENDER = "render"
    ENCODING = "encoding"
    UPLOAD = "upload"


class JobCheckpoint(BaseModel):
    stage: PipelineStage
    completed: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class ModelVersionInfo(BaseModel):
    segmentation_model: str = "sam3.1"
    matting_model: str = "vitmatte"
    pipeline_version: str = "1.0.0"


class VideoNormalizationConfig(BaseModel):
    target_fps: int = 30
    target_width: int = 1280
    target_height: int = 720
    pixel_format: str = "yuv420p"


class TranscriptWord(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    words: list[TranscriptWord] = Field(default_factory=list)


class SubjectGeometry(BaseModel):
    track_id: str
    bbox_normalized: BoundingBox
    center_x: float
    center_y: float
    top: float
    bottom: float
    left: float
    right: float


class GeometryRegions(BaseModel):
    top_region: BoundingBox
    person_zone: BoundingBox
    bottom_region: BoundingBox


def calculate_regions(canvas_width: int, canvas_height: int, person_bbox: BoundingBox) -> GeometryRegions:
    person_left = person_bbox.x * canvas_width
    person_right = (person_bbox.x + person_bbox.width) * canvas_width
    person_top = person_bbox.y * canvas_height
    person_bottom = (person_bbox.y + person_bbox.height) * canvas_height
    person_center_x = (person_left + person_right) / 2

    top_region = BoundingBox(
        x=0,
        y=0,
        width=1,
        height=person_bbox.y
    )
    person_zone = BoundingBox(
        x=person_bbox.x,
        y=person_bbox.y,
        width=person_bbox.width,
        height=person_bbox.height
    )
    bottom_region = BoundingBox(
        x=0,
        y=person_bbox.y + person_bbox.height,
        width=1,
        height=1 - (person_bbox.y + person_bbox.height)
    )

    return GeometryRegions(
        top_region=top_region,
        person_zone=person_zone,
        bottom_region=bottom_region
    )