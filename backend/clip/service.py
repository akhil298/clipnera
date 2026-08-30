from __future__ import annotations

import asyncio

from clip.repository import ClipRepository
from clip.schema import YouTubeURLRequest, VideoMetadataResponse
from clip.youtube_service import YouTubeService
from clip.model import ProjectStatus
from core.exceptions import CustomException
from core.logging_config import get_logger
from datetime import datetime

log = get_logger(__name__)


class ClipService:
    def __init__(self, repository: ClipRepository) -> None:
        self._repo = repository
        self._youtube = YouTubeService()

    async def fetch_metadata(self, user_id: str, data: YouTubeURLRequest) -> VideoMetadataResponse:
        metadata = await self._youtube.fetch_metadata(data.url)
        if not metadata:
            raise CustomException(
                message="Invalid YouTube URL or video not found",
                code="INVALID_YOUTUBE_URL",
                status_code=400,
            )

        project = await self._repo.create_project(
            user_id=user_id,
            title=metadata["title"],
            source_type="youtube",
            source_url=data.url,
        )

        return VideoMetadataResponse(
            id=project.id,
            title=metadata["title"],
            thumbnail_url=metadata["thumbnail_url"],
            channel_title=metadata["channel_title"],
            duration_formatted=metadata.get("duration_formatted", "--:--"),
            resolution=metadata.get("resolution", "1920x1080"),
            aspect_ratio=metadata.get("aspect_ratio", "16:9"),
            file_size=0,
            presigned_url="",
            original_url=data.url,
            status="pending",
            created_at=project.created_at,
        )

    async def download_video(self, user_id: str, data: YouTubeURLRequest) -> dict:
        metadata = await self._youtube.fetch_metadata(data.url)
        if not metadata:
            raise CustomException(
                message="Invalid YouTube URL or video not found",
                code="INVALID_YOUTUBE_URL",
                status_code=400,
            )

        project = await self._repo.create_project(
            user_id=user_id,
            title=metadata["title"],
            source_type="youtube",
            source_url=data.url,
        )

        asyncio.create_task(self._background_download(data.url, user_id, project.id))

        return {
            "id": project.id,
            "title": metadata["title"],
            "thumbnail_url": metadata.get("thumbnail_url", ""),
            "channel_title": metadata.get("channel_title", ""),
            "duration_formatted": metadata.get("duration_formatted", "--:--"),
            "resolution": metadata.get("resolution", "Unknown"),
            "aspect_ratio": metadata.get("aspect_ratio", "16:9"),
            "file_size": 0,
            "presigned_url": "",
            "original_url": data.url,
            "status": "downloading",
            "created_at": project.created_at.isoformat(),
        }

    async def _background_download(self, url: str, user_id: str, project_id: str) -> None:
        try:
            result = await self._youtube.download_and_store(url, user_id, project_id)
            await self._repo.update_project_s3(
                project_id=project_id,
                s3_key=result["s3_key"],
                s3_bucket=result["s3_bucket"],
                presigned_url=result["presigned_url"],
                file_size=result["file_size"],
                duration=result["duration_seconds"],
                status=ProjectStatus.UPLOADED,
            )
            log.info(f"Video downloaded: project={project_id} user={user_id}")
        except ValueError as e:
            log.error(f"Download failed: project={project_id} user={user_id} error={e}")
            await self._repo.update_project_s3(
                project_id=project_id,
                s3_key="",
                s3_bucket="",
                presigned_url="",
                file_size=0,
                duration=0,
                status=ProjectStatus.FAILED,
            )
        except Exception as e:
            log.error(f"Download error: project={project_id} user={user_id} error={e}")
