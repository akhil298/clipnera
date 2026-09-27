from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep
from clip.repository import ClipRepository
from core.database import get_db
from core.responses import ApiResponse, ok
from feature_flags.dependencies import require_flag
from feature_flags.registry import VIDEO_UPLOAD
from subscription.service import SubscriptionService
from uploads.schema import (
    VideoUploadAbortRequest,
    VideoUploadCompleteRequest,
    VideoUploadCompleteResponse,
    VideoUploadInitRequest,
    VideoUploadInitResponse,
)
from uploads.service import VideoUploadService, prepare_uploaded_video

uploads = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[Depends(require_flag(VIDEO_UPLOAD))])


async def get_upload_service(session: Annotated[AsyncSession, Depends(get_db)]) -> VideoUploadService:
    return VideoUploadService(ClipRepository(session), SubscriptionService.for_session(session))


UploadServiceDep = Annotated[VideoUploadService, Depends(get_upload_service)]


@uploads.post("/video/init", response_model=ApiResponse[VideoUploadInitResponse])
async def init_video_upload(data: VideoUploadInitRequest, user: CurrentUserDep, service: UploadServiceDep):
    """Create the project and presigned part URLs; the browser uploads straight to S3."""
    return ok(await service.init(user["user_id"], data))


@uploads.post("/video/{project_id}/complete", response_model=ApiResponse[VideoUploadCompleteResponse])
async def complete_video_upload(
    project_id: str, data: VideoUploadCompleteRequest, user: CurrentUserDep, service: UploadServiceDep,
):
    """Stitch the parts; the video is ready once ``/clips/progress/{project_id}`` reports done."""
    result = await service.complete(user["user_id"], project_id, data)
    asyncio.create_task(prepare_uploaded_video(project_id, user["user_id"]))
    return ok(result)


@uploads.post("/video/{project_id}/abort", response_model=ApiResponse[None])
async def abort_video_upload(
    project_id: str, data: VideoUploadAbortRequest, user: CurrentUserDep, service: UploadServiceDep,
):
    await service.abort(user["user_id"], project_id, data)
    return ok(None, "Upload cancelled")
