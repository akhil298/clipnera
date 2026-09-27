from __future__ import annotations

import asyncio
import math

from clip.repository import ClipRepository
from usage.repository import UsageRepository
from clip.schema import (
    AvailableFormatsResponse,
    YouTubeURLRequest,
    VideoMetadataResponse,
    YouTubeDownloadRequest,
    YouTubeMetadataResponse,
)
from clip.youtube_service import YouTubeService
from clip.model import ProjectStatus
from clip_generation.repository import ClipRepository as ClipGenRepository
from clients.services.s3 import S3
from core.exceptions import CustomException
from core.logging_config import get_logger
from datetime import datetime

log = get_logger(__name__)

IDLE_DOWNLOAD_PROGRESS = {"status": "idle", "percent": 0.0, "total": None, "speed": None, "eta": None}


def _video_shape(prefetch, default_resolution: str) -> tuple[str, str]:
    """(resolution, aspect ratio) of the best video quality, e.g. ("1080x1920", "9:16")."""
    best = next((q for q in prefetch.qualities if q.height), None)
    if not best:
        return default_resolution, "16:9"
    if not best.width:
        return f"{best.height}p", "16:9"
    divisor = math.gcd(best.width, best.height)
    return f"{best.width}x{best.height}", f"{best.width // divisor}:{best.height // divisor}"


class ClipService:
    def __init__(
        self,
        repository: ClipRepository,
        clip_gen_repository: ClipGenRepository | None = None,
        usage_repository: UsageRepository | None = None,
    ) -> None:
        self._repo = repository
        self._clip_gen_repo = clip_gen_repository
        self._usage_repo = usage_repository
        self._youtube = YouTubeService()

    async def _prefetch(self, url: str):
        prefetch = await self._youtube.fetch_metadata(url)
        if not prefetch:
            raise CustomException(
                message="Invalid YouTube URL or video not found",
                code="INVALID_YOUTUBE_URL",
                status_code=400,
            )
        return prefetch

    async def get_available_formats(self, url: str) -> AvailableFormatsResponse:
        return await self._youtube.get_available_formats(url)

    async def youtube_metadata(self, url: str) -> YouTubeMetadataResponse:
        """Metadata for a YouTube URL without creating a project."""
        prefetch = await self._prefetch(url)
        resolution, aspect_ratio = _video_shape(prefetch, "1920x1080")
        return YouTubeMetadataResponse(
            title=prefetch.title,
            thumbnail_url=prefetch.thumbnail or "",
            channel_title=prefetch.uploader or "Unknown",
            duration_seconds=int(prefetch.duration or 0),
            duration_formatted=YouTubeService._format_duration(prefetch.duration or 0),
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            original_url=url,
        )

    async def download_progress(self, project_id: str, user_id: str) -> dict:
        await self._owned_project(project_id, user_id)
        return await YouTubeService.get_progress(project_id) or dict(IDLE_DOWNLOAD_PROGRESS)

    async def list_projects_with_clips(self, user_id: str) -> dict:
        from clip_generation.service import ClipService as ClipGenService

        clip_gen_service = ClipGenService()
        projects = await self._repo.list_projects(user_id)
        clips_by_project = await self._clip_gen_repo.list_clips_for_projects([p.id for p in projects], user_id)
        costs = await self._usage_repo.project_costs([p.id for p in projects]) if self._usage_repo else {}

        result = []
        for p in projects:
            clips = clips_by_project.get(p.id, [])
            result.append({
                "id": p.id,
                "title": p.title,
                "source_type": p.source_type,
                "source_url": p.source_url,
                "status": p.status.value if hasattr(p.status, "value") else p.status,
                "duration_seconds": p.duration_seconds or 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                # AI spend on this video so far, in USD, from the usage ledger.
                "ai_cost_usd": round(costs.get(p.id, 0.0), 4),
                "clips": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "score": c.score,
                        "duration_seconds": c.duration_seconds,
                        "start_time": c.start_time,
                        "end_time": c.end_time,
                        "content_category": c.content_category,
                        "status": c.status,
                        "poster_url": clip_gen_service.poster_url(c),
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in clips
                ]
            })
        return {"projects": result, "total": len(result)}

    async def fetch_metadata(self, user_id: str, data: YouTubeURLRequest) -> VideoMetadataResponse:
        prefetch = await self._prefetch(data.url)

        project = await self._repo.create_project(
            user_id=user_id,
            title=prefetch.title,
            source_type="youtube",
            source_url=data.url,
        )

        resolution, aspect_ratio = _video_shape(prefetch, "1920x1080")
        return VideoMetadataResponse(
            id=project.id,
            title=prefetch.title,
            thumbnail_url=prefetch.thumbnail or "",
            channel_title=prefetch.uploader or "Unknown",
            duration_formatted=self._youtube._format_duration(prefetch.duration or 0),
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            file_size=0,
            presigned_url="",
            original_url=data.url,
            status="pending",
            created_at=project.created_at,
        )

    async def download_video(self, user_id: str, data: YouTubeDownloadRequest) -> dict:
        prefetch = await self._prefetch(data.url)

        project = await self._repo.create_project(
            user_id=user_id,
            title=prefetch.title,
            source_type="youtube",
            source_url=data.url,
            status=ProjectStatus.PROCESSING,
        )

        asyncio.create_task(self._background_download(data.url, user_id, project.id, data.format_id))

        resolution, aspect_ratio = _video_shape(prefetch, "Unknown")

        return {
            "id": project.id,
            "title": prefetch.title,
            "thumbnail_url": prefetch.thumbnail or "",
            "channel_title": prefetch.uploader or "Unknown",
            "duration_formatted": self._youtube._format_duration(prefetch.duration or 0),
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "file_size": 0,
            "presigned_url": "",
            "original_url": data.url,
            "status": "processing",
            "created_at": project.created_at.isoformat(),
        }


    async def _owned_project(self, project_id: str, user_id: str):
        project = await self._repo.get_project(project_id, user_id)
        if not project:
            raise CustomException(
                message="Project not found",
                code="NOT_FOUND",
                status_code=404,
            )
        return project

    async def delete_project(self, user_id: str, project_id: str) -> None:
        project = await self._owned_project(project_id, user_id)

        if project.s3_bucket and project.s3_key:
            try:
                s3 = S3()
                s3.delete_object(project.s3_bucket, project.s3_key)
                log.info(f"Deleted S3 object: bucket={project.s3_bucket} key={project.s3_key}")
            except Exception as e:
                log.warning(f"Failed to delete S3 object for project {project_id}: {e}")

        await self._repo.delete_project(project_id, user_id)

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
