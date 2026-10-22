"""Request and response models for /edits (reels from raw footage) and the music library.

Mirrored field for field by the ``Edit*`` and ``MusicTrack*`` types in
frontend/lib/types.ts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from clients.ai.roles import Effort
from subtitle_styling.templates import DEFAULT_STYLE

ScriptMode = Literal["auto", "spoken", "voiceover", "onscreen", "direction"]
TargetSeconds = Literal[0, 15, 30, 45, 60, 90]
EditSourceType = Literal[
    "video/mp4", "video/quicktime", "video/webm",
    "image/jpeg", "image/png", "image/webp",
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a", "audio/webm",
]
EditChangeOp = Literal[
    "set_script_mode", "restore_line", "remove_line", "set_hook", "set_music", "set_look",
    "set_caption_style", "set_length", "remove_pop", "skip_missing_lines",
]


class EditCreateRequest(BaseModel):
    title: str = Field("Untitled reel", min_length=1, max_length=300)
    script: str | None = Field(None, max_length=6000)
    script_mode: ScriptMode = "auto"
    intent: str | None = Field(None, max_length=300)
    # A language code ("en", "hi", "te") or a mix ("hinglish", "tenglish").
    language: str = Field("en", min_length=2, max_length=20)
    caption_style: str = Field(DEFAULT_STYLE, min_length=1, max_length=60)
    target_seconds: TargetSeconds = 0
    autopilot: bool = False
    # "premium": the reel engine edits end to end (Pro); "classic": plan, review, then render.
    engine: Literal["classic", "premium"] = "classic"
    # The OpenAI deployment (one of /edits/models) and effort for the director and chat; None for the defaults.
    ai_model: str | None = Field(None, min_length=1, max_length=80)
    ai_effort: Effort | None = None
    # A reel whose editing style to copy (pacing, captions, energy), by link.
    reference_url: str | None = Field(None, max_length=1000, pattern=r"^https?://\S+$")


class EditSourceFile(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: EditSourceType
    size_bytes: int = Field(..., gt=0, le=2 * 1024 * 1024 * 1024)
    # Read by the browser before upload so over-limit footage is refused early; checked again on analysis.
    duration_s: float | None = Field(None, ge=0)
    # A video whose editing style to copy rather than footage to edit; one per reel.
    reference: bool = False


class EditSourcesInitRequest(BaseModel):
    files: list[EditSourceFile] = Field(..., min_length=1, max_length=40)


class EditUpload(BaseModel):
    key: str
    url: str
    content_type: str


class EditSourcesInitResponse(BaseModel):
    uploads: list[EditUpload]


class EditSourcesCompleteRequest(BaseModel):
    keys: list[str] = Field(..., min_length=1, max_length=40)


class EditChange(BaseModel):
    op: EditChangeOp
    value: str | None = Field(None, max_length=300)


class EditChangesRequest(BaseModel):
    changes: list[EditChange] = Field(..., min_length=1, max_length=10)


class EditChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=300)
    # A new model pick for this and later chats and re-plans; None keeps the reel's.
    ai_model: str | None = Field(None, min_length=1, max_length=80)
    ai_effort: Effort | None = None


class EditSourceResponse(BaseModel):
    key: str
    kind: Literal["video", "image", "voice", "reference"]
    name: str
    duration_s: float
    # A playable URL for the browser preview: the small proxy for videos.
    url: str | None


class EditReferenceResponse(BaseModel):
    """What the analysis took from the reference reel."""

    duration_s: float
    shots: int
    seconds_per_shot: float
    energy: Literal["low", "medium", "high"]
    # The look in a sentence: captions, colour, on-screen text, transitions.
    style: str


class EditLine(BaseModel):
    id: str
    text: str


class EditMusicResponse(BaseModel):
    id: str
    title: str
    artist: str
    licence: str
    credit_text: str
    url: str | None


class EditPlanResponse(BaseModel):
    content_type: str
    layout: Literal["talking", "voiceover", "montage"]
    # none when no script was given.
    script_mode: Literal["none", "spoken", "voiceover", "onscreen", "direction"]
    script_lines_found: int
    script_lines_total: int
    missing_lines: list[str]
    skip_missing: bool
    removed_lines: list[EditLine]
    hook: str
    title: str
    look: str
    caption_style: str
    music: EditMusicResponse | None
    music_mood: str
    broll_count: int
    own_broll_count: int
    pop_count: int
    director_model: str
    caption: str
    hashtags: list[str]


class EditPicture(BaseModel):
    kind: Literal["video", "image", "card"]
    at: float
    # Seconds on screen.
    dur: float
    src: int | None = None
    # The span of the source file shown, for video.
    source_start: float | None = None
    source_end: float | None = None
    zoom: float | None = None
    crop_x: float | None = None
    text: str | None = None


class EditVoicePiece(BaseModel):
    src: int
    source_start: float
    source_end: float
    at: float


class EditText(BaseModel):
    kind: Literal["hook", "pop", "line"]
    text: str
    at: float
    dur: float


class EditWord(BaseModel):
    word: str
    start: float
    end: float


class EditTimelineMusic(BaseModel):
    track_id: str
    offset: float
    gain_db: float
    duck: bool


class EditTimelineResponse(BaseModel):
    duration: float
    width: int
    height: int
    look: str
    picture: list[EditPicture]
    voice: list[EditVoicePiece]
    voiceover_src: int | None
    texts: list[EditText]
    words: list[EditWord]
    music: EditTimelineMusic | None


class PremiumStage(BaseModel):
    stage: str
    note: str
    at: float


class PremiumLayer(BaseModel):
    layer: str
    score: int
    note: str


class PremiumAsset(BaseModel):
    kind: str
    source: str
    made: bool


class PremiumResponse(BaseModel):
    """What the reel engine did, for the reels board: where it is, what it decided, how the review scored it."""

    stage: str
    stages: list[PremiumStage]
    path: str | None
    recipe: str | None
    audio_kind: str | None
    audio_why: str | None
    title: str | None
    hooks: list[str]
    sections: list[str]
    shots: int
    graphics: int
    captions: int
    scores: list[PremiumLayer]
    overall: float
    fixes: list[str]
    passes: int
    assets: list[PremiumAsset]
    ai_calls: int
    music: str | None


class EditResponse(BaseModel):
    id: str
    title: str
    status: Literal["draft", "analyzing", "planned", "rendering", "done", "failed"]
    progress: str | None
    script: str | None
    script_mode: ScriptMode
    intent: str | None
    language: str
    caption_style: str
    target_seconds: int
    autopilot: bool
    ai_model: str | None
    ai_effort: str | None
    reference_url: str | None
    reference: EditReferenceResponse | None
    # Why the reference reel was skipped, when it was.
    reference_error: str | None
    engine: Literal["classic", "premium"]
    premium: PremiumResponse | None
    sources: list[EditSourceResponse]
    raw_seconds: float
    duration_s: float
    plan: EditPlanResponse | None
    timeline: EditTimelineResponse | None
    credits_estimate: int
    credits_charged: int
    renders: int
    replans_left: int
    chat_edits_left: int
    output_url: str | None
    music_credit: str | None
    error: str | None
    created_at: datetime


class EditSummary(BaseModel):
    id: str
    title: str
    status: str
    duration_s: float
    created_at: datetime


class EditLimitsResponse(BaseModel):
    max_raw_seconds: int
    max_files: int
    max_output_seconds: int
    output_height: int
    opus_director: bool


class MusicTrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    source: str
    source_url: str
    licence: str
    licence_url: str
    credit_text: str
    mood: str
    energy: float
    bpm: float | None
    duration_s: float
    status: Literal["live", "pulled"]
    used_by: int = 0
    created_at: datetime


class MusicStatusRequest(BaseModel):
    status: Literal["live", "pulled"]
