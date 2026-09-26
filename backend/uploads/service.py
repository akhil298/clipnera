"""Direct browser-to-S3 video uploads.

The API never carries the bytes: ``init`` creates the project and hands the
browser one presigned URL per part, ``complete`` stitches the parts in S3, and
a background task probes its real duration straight from S3, after which the project is ``uploaded`` and ready for the pipeline, exactly
like a finished YouTube download.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path

from clients.services.s3 import S3
from clip.model import ProjectStatus, VideoProject
from clip.repository import ClipRepository
from clip.youtube_service import YouTubeService
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from subscription.service import SubscriptionService
from uploads.schema import (
    VideoUploadAbortRequest,
    VideoUploadCompleteRequest,
    VideoUploadCompleteResponse,
    VideoUploadInitRequest,
    VideoUploadInitResponse,
)
from video_processor.ffmpeg_service import FFmpegService

log = get_logger(__name__)

SOURCE_TYPE = "upload"
MAX_PARTS = 10_000
_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}


def part_size_for(size_bytes: int, min_part_bytes: int) -> int:
    """The smallest part size (a whole MiB, at least the minimum) that fits S3's part limit."""
    needed = math.ceil(size_bytes / MAX_PARTS)
    mib = 1024 * 1024
    return max(min_part_bytes, math.ceil(needed / mib) * mib)


def _progress(status: str, message: str) -> dict:
    """Same shape as a YouTube download's progress, which the frontend already polls."""
    return {"status": status, "percent": 100.0, "total": None, "speed": None, "eta": None, "message": message}


def title_from_filename(filename: str) -> str:
    stem = Path(filename).name.rsplit(".", 1)[0]
    return (stem.strip() or "Uploaded video")[:500]


class VideoUploadService:
    def __init__(
        self, repository: ClipRepository, subscriptions: SubscriptionService, s3: S3 | None = None,
    ) -> None:
        self._repo = repository
        self._subscriptions = subscriptions
        self._s3 = s3 or S3()
        self._settings = get_settings()

    async def init(self, user_id: str, request: VideoUploadInitRequest) -> VideoUploadInitResponse:
        if request.size_bytes > self._settings.UPLOAD_MAX_BYTES:
            raise CustomException(
                message=f"Videos can be up to {self._settings.UPLOAD_MAX_BYTES // 1024 ** 3} GB.",
                code="UPLOAD_TOO_LARGE",
                status_code=413,
            )
        await self._check_duration(user_id, request.duration_seconds)

        project = await self._repo.create_project(
            user_id=user_id, title=title_from_filename(request.filename), source_type=SOURCE_TYPE,
        )
        bucket = self._settings.S3_BUCKET_NAME
        key = f"videos/{user_id}/{project.id}/source{_EXTENSIONS[request.content_type]}"
        upload_id = await asyncio.to_thread(self._s3.create_multipart_upload, bucket, key, request.content_type)
        await self._repo.update_project_s3(
            project_id=project.id, s3_key=key, s3_bucket=bucket, presigned_url="",
            file_size=request.size_bytes, duration=0, status=ProjectStatus.PENDING,
        )

        part_size = part_size_for(request.size_bytes, self._settings.UPLOAD_MIN_PART_BYTES)
        part_urls = [
            self._s3.presign_upload_part(bucket, key, upload_id, number, self._settings.UPLOAD_URL_TTL_SECONDS)
            for number in range(1, math.ceil(request.size_bytes / part_size) + 1)
        ]
        return VideoUploadInitResponse(
            project_id=project.id, upload_id=upload_id, part_size=part_size, part_urls=part_urls,
        )

    async def complete(
        self, user_id: str, project_id: str, request: VideoUploadCompleteRequest,
    ) -> VideoUploadCompleteResponse:
        project = await self._pending_upload(user_id, project_id)
        parts = [{"PartNumber": p.part_number, "ETag": p.etag} for p in request.parts]
        await asyncio.to_thread(
            self._s3.complete_multipart_upload, project.s3_bucket, project.s3_key, request.upload_id, parts,
        )
        stored = await asyncio.to_thread(self._s3.object_size, project.s3_bucket, project.s3_key)
        if stored != project.file_size:
            await asyncio.to_thread(self._s3.delete_object, project.s3_bucket, project.s3_key)
            await self._repo.update_project_status(project.id, ProjectStatus.FAILED)
            raise CustomException(
                message="The upload did not arrive complete. Please upload the video again.",
                code="UPLOAD_SIZE_MISMATCH",
                status_code=400,
            )
        await self._repo.update_project_status(project.id, ProjectStatus.PROCESSING)
        await YouTubeService.set_progress(project.id, _progress("uploading", "Preparing video..."))
        return VideoUploadCompleteResponse(project_id=project.id, status=ProjectStatus.PROCESSING.value)

    async def abort(self, user_id: str, project_id: str, request: VideoUploadAbortRequest) -> None:
        project = await self._pending_upload(user_id, project_id)
        await asyncio.to_thread(self._s3.abort_multipart_upload, project.s3_bucket, project.s3_key, request.upload_id)
        await self._repo.delete_project(project.id, user_id)

    async def _check_duration(self, user_id: str, duration_seconds: float | None) -> None:
        if duration_seconds is None:
            return
        entitlements = await self._subscriptions.get_entitlements(user_id)
        if duration_seconds > entitlements.max_upload_duration_seconds:
            raise CustomException(
                message=(
                    f"This video is {int(duration_seconds) // 60} minutes. Your {entitlements.plan} plan "
                    f"supports up to {entitlements.max_upload_duration_seconds // 60} minutes per video."
                ),
                code="DURATION_NOT_ENTITLED",
                status_code=403,
            )

    async def _pending_upload(self, user_id: str, project_id: str) -> VideoProject:
        project = await self._repo.get_project(project_id, user_id)
        if not project or project.source_type != SOURCE_TYPE:
            raise CustomException(message="Upload not found", code="NOT_FOUND", status_code=404)
        if project.status != ProjectStatus.PENDING or not project.s3_key:
            raise CustomException(message="This upload is already finished", code="UPLOAD_NOT_PENDING", status_code=409)
        return project


async def prepare_uploaded_video(project_id: str, user_id: str) -> None:
    """Probe a completed upload's real duration and mark it ready.

    Runs after ``complete`` returns; the frontend polls the same progress
    endpoint it uses for YouTube downloads.
    """
    async with AsyncSessionLocal() as session:
        repo = ClipRepository(session)
        project = await repo.get_project(project_id, user_id)
        if not project:
            return
        try:
            # Probed straight from S3: whichever machine runs the pipeline
            # fetches the file itself (clip.source_video), so none is copied here.
            source_url = await asyncio.to_thread(S3().generate_presigned_url, project.s3_bucket, project.s3_key)
            duration = await FFmpegService().probe_duration(source_url)
            if duration <= 0:
                raise ValueError("the file has no readable video duration")
            await repo.update_project_s3(
                project_id=project.id, s3_key=project.s3_key, s3_bucket=project.s3_bucket,
                presigned_url="", file_size=project.file_size or 0, duration=math.ceil(duration),
                status=ProjectStatus.UPLOADED,
            )
            await YouTubeService.set_progress(project.id, _progress("done", "Video ready."))
            log.info("Upload ready: project=%s duration=%.1fs", project.id, duration)
        except Exception as exc:
            log.error("Upload preparation failed: project=%s error=%s", project.id, exc)
            await repo.update_project_status(project.id, ProjectStatus.FAILED)
            await YouTubeService.set_progress(
                project.id, _progress("error", "We couldn't read this video. Try an MP4 or MOV file."),
            )
