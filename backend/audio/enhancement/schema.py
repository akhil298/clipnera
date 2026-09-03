from pydantic import BaseModel, Field
from typing import Optional


class AudioEnhanceRequest(BaseModel):
    audio_url: str = Field(..., description="Presigned S3 URL or path to input audio file")
    config: dict = Field(default_factory=lambda: {
        "ai_denoise": True,
        "noise_suppression_strength": 90,
        "de_reverb": True,
        "vocal_clarity_eq": True,
        "hum_filter": True,
    })


class AudioEnhanceResponse(BaseModel):
    success: bool
    processed_url: Optional[str] = None
    processing_time_seconds: float
    sample_rate: int
    duration_seconds: float
    applied_settings: dict
    error: Optional[str] = None


class AudioPreviewRequest(BaseModel):
    frequency_hz: float = Field(default=440.0, ge=20.0, le=2000.0, description="Test tone frequency")
    duration_seconds: float = Field(default=3.0, ge=0.5, le=10.0, description="Preview duration")
    config: dict = Field(default_factory=lambda: {
        "ai_denoise": True,
        "noise_suppression_strength": 90,
        "de_reverb": True,
        "vocal_clarity_eq": True,
        "hum_filter": True,
    })
