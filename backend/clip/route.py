from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from clip.repository import ClipRepository
from clip.schema import YouTubeURLRequest, VideoMetadataResponse, AvailableFormatsResponse, YouTubeMetadataResponse, YouTubeDownloadRequest
from clip.service import ClipService
from clip_generation.repository import ClipRepository as ClipGenRepository
from core.database import get_db

clip = APIRouter(prefix="/clips", tags=["clips"])


async def get_clip_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ClipService:
    return ClipService(ClipRepository(session), ClipGenRepository(session))


ClipServiceDep = Annotated[ClipService, Depends(get_clip_service)]


@clip.post("/formats", response_model=AvailableFormatsResponse)
async def get_formats(data: YouTubeURLRequest, user: CurrentUserDep, service: ClipServiceDep):
    return await service.get_available_formats(data.url)


@clip.post("/youtube/metadata", response_model=YouTubeMetadataResponse)
async def fetch_youtube_metadata(data: YouTubeURLRequest, user: CurrentUserDep, service: ClipServiceDep):
    return await service.youtube_metadata(data.url)


@clip.post("/youtube", response_model=VideoMetadataResponse)
async def fetch_youtube(data: YouTubeURLRequest, user: CurrentUserDep, service: ClipServiceDep):
    return await service.fetch_metadata(user["user_id"], data)


@clip.post("/download", response_model=VideoMetadataResponse)
async def download_youtube(data: YouTubeDownloadRequest, user: CurrentUserDep, service: ClipServiceDep):
    return await service.download_video(user["user_id"], data)


@clip.get("/progress/{project_id}")
async def get_download_progress(project_id: str, user: CurrentUserDep):
    """Get download progress for a specific project."""
    return await ClipService.download_progress(project_id)


@clip.get("/projects")
async def list_projects(user: CurrentUserDep, service: ClipServiceDep):
    return await service.list_projects_with_clips(user["user_id"])


@clip.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, user: CurrentUserDep, service: ClipServiceDep):
    await service.delete_project(user["user_id"], project_id)
    return None
