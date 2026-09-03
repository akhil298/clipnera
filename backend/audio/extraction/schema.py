from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum


class AudioCodec(str, Enum):
    PCM = "pcm_s16le"
    MP3 = "libmp3lame"
    AAC = "aac"
    FLAC = "flac"
    OPUS = "libopus"


class AudioChannel(str, Enum):
    MONO = "mono"
    STEREO = "stereo"


class OutputFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    AAC = "aac"
    FLAC = "flac"
    OPUS = "opus"


class ExtractionRequest(BaseModel):
    input_path: str = Field(..., description="Absolute path to input video/audio file")
    output_path: Optional[str] = Field(None, description="Absolute path for output file. Auto-generated if omitted.")
    output_format: OutputFormat = Field(OutputFormat.WAV, description="Target output container format")
    codec: Optional[AudioCodec] = Field(None, description="Override output codec")
    sample_rate: int = Field(16000, ge=8000, le=192000, description="Target sample rate in Hz")
    channels: AudioChannel = Field(AudioChannel.MONO, description="Target channel layout")
    track_index: Optional[int] = Field(None, ge=0, description="Audio stream index to extract (0-based). Extracts all if omitted.")
    language: Optional[str] = Field(None, description="Preferred audio language tag (e.g., 'eng', 'hin')")
    overwrite: bool = Field(False, description="Overwrite existing output file")


class BatchExtractionRequest(BaseModel):
    input_paths: list[str] = Field(..., min_length=1, description="List of input file paths")
    output_dir: str = Field(..., description="Directory for output files")
    output_format: OutputFormat = Field(OutputFormat.WAV)
    sample_rate: int = Field(16000, ge=8000, le=192000)
    channels: AudioChannel = Field(AudioChannel.MONO)
    overwrite: bool = Field(False)
    max_workers: int = Field(1, ge=1, le=8, description="Parallel workers for batch processing")


class ExtractionProgress(BaseModel):
    percent: float = Field(0.0, ge=0.0, le=100.0)
    frame: int = 0
    fps: float = 0.0
    bitrate: str = ""
    total_size: int = 0
    out_time_us: int = 0
    speed: str = ""
    status: str = "idle"


class ExtractionResult(BaseModel):
    input_path: str
    output_path: str
    format: str
    codec: str
    sample_rate: int
    channels: int
    duration_seconds: float
    file_size_bytes: int
    status: Literal["completed", "failed", "skipped"]
    warnings: list[str] = []
    error: Optional[str] = None
    processing_time_seconds: float = 0.0


class BatchExtractionResult(BaseModel):
    total: int
    completed: int
    failed: int
    skipped: int
    results: list[ExtractionResult]
    processing_time_seconds: float = 0.0
