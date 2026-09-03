from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import datetime


class YouTubeURLRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")


class YouTubeDownloadRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")
    format_id: Optional[str] = Field(None, description="yt-dlp format selector string")


class YouTubeMetadataResponse(BaseModel):
    title: str
    thumbnail_url: str
    channel_title: str
    duration_seconds: int = 0
    duration_formatted: str = "--:--"
    resolution: str = "1920x1080"
    aspect_ratio: Union[str, float] = "16:9"
    original_url: str


class VideoMetadataResponse(BaseModel):
    id: str
    title: str
    thumbnail_url: str
    channel_title: str
    duration_formatted: str
    resolution: str
    aspect_ratio: Union[str, float]
    file_size: int
    presigned_url: str
    original_url: str
    status: str
    created_at: datetime


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: str
    width: int
    height: int
    filesize: int
    vcodec: str
    acodec: str
    abr: int
    type: str


class AvailableFormatsResponse(BaseModel):
    title: str
    duration: int
    thumbnail: str
    channel: str
    video: list[FormatInfo]
    audio: list[FormatInfo]
