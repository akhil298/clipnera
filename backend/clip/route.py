from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from clip.schema import YouTubeURLRequest, VideoMetadataResponse, AvailableFormatsResponse, YouTubeMetadataResponse
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

    service = YouTubeService()
    metadata = await service.fetch_metadata(data.url)
    if not metadata:
        from core.exceptions import CustomException
        raise CustomException(
            message="Invalid YouTube URL or video not found",
            code="INVALID_YOUTUBE_URL",
            status_code=400,
        )
    return metadata


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
async def download_youtube(data: YouTubeURLRequest, user: CurrentUserDep):
    from clip.repository import ClipRepository
    from clip.service import ClipService
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        service = ClipService(repo)
        return await service.download_video(user["user_id"], data)


@clip.get("/download/progress/{video_id}")
async def download_progress(video_id: str, user: CurrentUserDep):
    from clip.youtube_service import YouTubeService
    from fastapi.responses import StreamingResponse

    async def event_stream():
        import json
        while True:
            progress = await YouTubeService.get_progress(video_id)
            yield f"data: {json.dumps(progress)}\n\n"
            if not progress or progress.get("status") in ("done", "error", "uploading"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
