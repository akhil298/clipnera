from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from auth.dependencies import CurrentUserDep
from clip_generation.schema import SocialExportRequest, SocialExportResponse
from pipeline.schema import PipelineStartRequest
from pipeline.service import PipelineRunService

pipeline = APIRouter(prefix="/pipeline", tags=["pipeline"])
_service = PipelineRunService()


@pipeline.post("/start/{project_id}")
async def start_pipeline(project_id: str, user: CurrentUserDep, body: PipelineStartRequest | None = None):
    return await _service.start(project_id, user, body.body() if body else None)


@pipeline.post("/cancel/{project_id}")
async def cancel_pipeline(project_id: str, user: CurrentUserDep):
    return await _service.cancel(project_id, user["user_id"])


@pipeline.get("/progress/{project_id}")
async def pipeline_progress(project_id: str, user: CurrentUserDep):
    await _service.require_owned_project(project_id, user["user_id"])
    return StreamingResponse(_service.progress_events(project_id), media_type="text/event-stream")


@pipeline.post("/status/batch")
async def pipeline_status_batch(body: dict[str, Any], user: CurrentUserDep):
    """Status for many projects in one round trip."""
    return await _service.status_batch(body, user["user_id"])


@pipeline.get("/status/{project_id}")
async def pipeline_status(project_id: str, user: CurrentUserDep):
    return await _service.status(project_id, user["user_id"])


@pipeline.post("/revert/{project_id}/{step}")
async def revert_step(project_id: str, step: str, user: CurrentUserDep):
    return await _service.revert_step(project_id, step, user["user_id"])


@pipeline.post("/resume/{project_id}")
async def resume_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    return await _service.resume(project_id, user, body)


@pipeline.get("/social-platforms")
async def list_social_platforms():
    return _service.social_platforms()


@pipeline.post("/export/{project_id}", response_model=SocialExportResponse)
async def export_clips_for_social(project_id: str, request: SocialExportRequest, user: CurrentUserDep):
    return await _service.export_for_social(project_id, request, user["user_id"])
