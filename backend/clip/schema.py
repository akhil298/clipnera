from pydantic import AfterValidator, BaseModel, Field
from typing import Annotated, Optional, Union
from datetime import datetime

from clip.youtube_url import canonical_youtube_url
from pipeline.schema import PipelineStartRequest

YouTubeVideoURL = Annotated[str, AfterValidator(canonical_youtube_url), Field(description="YouTube video URL")]


class YouTubeURLRequest(BaseModel):
    url: YouTubeVideoURL


class YouTubeDownloadRequest(BaseModel):
    url: YouTubeVideoURL
    format_id: Optional[str] = Field(None, description="yt-dlp format selector string")
    # Started by the server once the video is stored, so closing or reloading
    # the page during the download cannot leave the project unprocessed.
    pipeline: Optional[PipelineStartRequest] = None


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
    # Charged when the download was requested with a run; 0 otherwise.
    credits_deducted: int = 0


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
