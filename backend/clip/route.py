from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from clip.schema import YouTubeURLRequest, VideoMetadataResponse, AvailableFormatsResponse, YouTubeMetadataResponse, YouTubeDownloadRequest
from core.logging_config import get_logger

import asyncio

log = get_logger(__name__)

clip = APIRouter(prefix="/clips", tags=["clips"])


@clip.post("/formats", response_model=AvailableFormatsResponse)
async def get_formats(data: YouTubeURLRequest, user: CurrentUserDep):
    from clip.youtube_service import YouTubeService

    service = YouTubeService()
    return await service.get_available_formats(data.url)


@clip.post("/youtube/metadata", response_model=YouTubeMetadataResponse)
async def fetch_youtube_metadata(data: YouTubeURLRequest, user: CurrentUserDep):
    from clip.youtube_service import YouTubeService
    from core.exceptions import CustomException

    service = YouTubeService()
    prefetch = await service.fetch_metadata(data.url)
    if not prefetch:
        raise CustomException(
            message="Invalid YouTube URL or video not found",
            code="INVALID_YOUTUBE_URL",
            status_code=400,
        )
    
    # Format resolution from quality options
    resolution = "1920x1080"
    if prefetch.qualities and prefetch.qualities[0].height:
        first_video_quality = next((q for q in prefetch.qualities if q.height), None)
        if first_video_quality:
            resolution = f"?x{first_video_quality.height}"
    
    return YouTubeMetadataResponse(
        title=prefetch.title,
        thumbnail_url=prefetch.thumbnail or "",
        channel_title=prefetch.uploader or "Unknown",
        duration_seconds=int(prefetch.duration or 0),
        duration_formatted=YouTubeService._format_duration(prefetch.duration or 0),
        resolution=resolution,
        aspect_ratio="16:9",
        original_url=data.url,
    )


@clip.post("/youtube", response_model=VideoMetadataResponse)
async def fetch_youtube(data: YouTubeURLRequest, user: CurrentUserDep):
    from clip.repository import ClipRepository
    from clip.service import ClipService
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        service = ClipService(repo)
        return await service.fetch_metadata(user["user_id"], data)


@clip.post("/download", response_model=VideoMetadataResponse)
async def download_youtube(data: YouTubeDownloadRequest, user: CurrentUserDep):
    from clip.repository import ClipRepository
    from clip.service import ClipService
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        service = ClipService(repo)
        return await service.download_video(user["user_id"], data)


@clip.get("/progress/{project_id}")
async def get_download_progress(project_id: str, user: CurrentUserDep):
    """Get download progress for a specific project."""
    from clip.youtube_service import YouTubeService

    progress = await YouTubeService.get_progress(project_id)
    return progress or {"status": "idle", "percent": 0.0, "total": None, "speed": None, "eta": None}
