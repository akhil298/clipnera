from __future__ import annotations

import asyncio

from clip.repository import ClipRepository
from clip.schema import YouTubeURLRequest, VideoMetadataResponse, YouTubeDownloadRequest
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
        prefetch = await self._youtube.fetch_metadata(data.url)
        if not prefetch:
            raise CustomException(
                message="Invalid YouTube URL or video not found",
                code="INVALID_YOUTUBE_URL",
                status_code=400,
            )

        project = await self._repo.create_project(
            user_id=user_id,
            title=prefetch.title,
            source_type="youtube",
            source_url=data.url,
        )

        # Format resolution from quality options
        resolution = "1920x1080"
        if prefetch.qualities and prefetch.qualities[0].height:
            first_video_quality = next((q for q in prefetch.qualities if q.height), None)
            if first_video_quality:
                resolution = f"?x{first_video_quality.height}"

        return VideoMetadataResponse(
            id=project.id,
            title=prefetch.title,
            thumbnail_url=prefetch.thumbnail or "",
            channel_title=prefetch.uploader or "Unknown",
            duration_formatted=self._youtube._format_duration(prefetch.duration or 0),
            resolution=resolution,
            aspect_ratio="16:9",
            file_size=0,
            presigned_url="",
            original_url=data.url,
            status="pending",
            created_at=project.created_at,
        )

    async def download_video(self, user_id: str, data: YouTubeDownloadRequest) -> dict:
        prefetch = await self._youtube.fetch_metadata(data.url)
        if not prefetch:
            raise CustomException(
                message="Invalid YouTube URL or video not found",
                code="INVALID_YOUTUBE_URL",
                status_code=400,
            )

        project = await self._repo.create_project(
            user_id=user_id,
            title=prefetch.title,
            source_type="youtube",
            source_url=data.url,
            status=ProjectStatus.PROCESSING,
        )

        asyncio.create_task(self._background_download(data.url, user_id, project.id, data.format_id))

        # Format resolution from quality options
        resolution = "Unknown"
        if prefetch.qualities and prefetch.qualities[0].height:
            first_video_quality = next((q for q in prefetch.qualities if q.height), None)
            if first_video_quality:
                resolution = f"?x{first_video_quality.height}"

        return {
            "id": project.id,
            "title": prefetch.title,
            "thumbnail_url": prefetch.thumbnail or "",
            "channel_title": prefetch.uploader or "Unknown",
            "duration_formatted": self._youtube._format_duration(prefetch.duration or 0),
            "resolution": resolution,
            "aspect_ratio": "16:9",
            "file_size": 0,
            "presigned_url": "",
            "original_url": data.url,
            "status": "processing",
            "created_at": project.created_at.isoformat(),
        }


    async def _background_download(self, url: str, user_id: str, project_id: str, format_id: str | None = None) -> None:
        try:
            result = await self._youtube.download_and_store(url, user_id, project_id, format_id)
            await self._repo.update_project_s3(
                project_id=project_id,
                s3_key=result["s3_key"],
                s3_bucket=result["s3_bucket"],
                presigned_url=result["presigned_url"],
                file_size=result["file_size"],
                duration=result["duration_seconds"],
                status=ProjectStatus.UPLOADED,
                local_path=result.get("local_path"),
            )
            await YouTubeService.set_progress(project_id, {
                "status": "done",
                "percent": 100.0,
                "total": self._youtube._format_bytes(result["file_size"]),
                "message": "Video downloaded, metadata saved, and upload complete.",
            })
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
