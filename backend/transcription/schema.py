from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, List


class TranscriptionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_path: str = Field(..., description="Absolute path to audio/video file")
    model_size: Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"] = Field("small", description="Whisper model size")
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'hi'). Auto-detect if omitted.")
    prompt: Optional[str] = Field(None, max_length=600, description="Context for spelling names and brands, e.g. the video title")
    chunk_duration: int = Field(1200, ge=300, le=1800, description="Chunk duration in seconds (5-30 min)")
    chunk_overlap: int = Field(10, ge=0, le=60, description="Overlap between chunks in seconds")
    word_timestamps: bool = Field(True, description="Enable word-level timestamps")
    diarization: bool = Field(False, description="Enable speaker diarization")
    output_format: Literal["json", "srt", "vtt", "txt", "all"] = Field("all", description="Output format(s)")
    output_dir: Optional[str] = Field(None, description="Directory for outputs")
    device: Optional[Literal["cpu", "cuda", "auto"]] = Field("auto", description="Compute device")


class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float
    speaker: Optional[str] = None
    words: Optional[List[dict]] = None


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_path: str
    language: str
    duration_seconds: float
    segments: List[TranscriptionSegment]
    processing_time_seconds: float
    model_used: str
    outputs: dict[str, str] = {}
    warnings: List[str] = []
    checkpoint_path: Optional[str] = None


class BatchTranscriptionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_paths: List[str] = Field(..., min_length=1)
    output_dir: str = Field(..., description="Directory for outputs")
    model_size: Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"] = "small"
    language: Optional[str] = None
    chunk_duration: int = 1200
    chunk_overlap: int = 10
    word_timestamps: bool = True
    diarization: bool = False
    output_format: Literal["json", "srt", "vtt", "txt", "all"] = "all"
    max_workers: int = Field(1, ge=1, le=4)
    device: Optional[Literal["cpu", "cuda", "auto"]] = "auto"


class BatchTranscriptionResult(BaseModel):
    total: int
    completed: int
    failed: int
    results: List[TranscriptionResult]
    processing_time_seconds: float = 0.0
