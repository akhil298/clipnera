from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from clip_generation.service import ClipService
from clip_generation.schema import *
from subtitle_styling.schema import SubtitleBurnRequest
from core.logging_config import get_logger

log = get_logger(__name__)

clip_generation = APIRouter(prefix="/clips", tags=["clip-generation"])


@clip_generation.post("/{project_id}/generate")
async def generate_clips(project_id: str, user: CurrentUserDep):
    service = ClipService()
    result = await service.generate_clips_for_project(
        project_id=project_id,
        user_id=user["user_id"],
    )
    return result


@clip_generation.get("/{project_id}")
async def list_project_clips(project_id: str, user: CurrentUserDep):
    service = ClipService()
    clips = await service.list_clips(project_id, user["user_id"])
    return {"project_id": project_id, "clips": clips, "total": len(clips)}


@clip_generation.get("/item/{clip_id}")
async def get_clip(clip_id: str, user: CurrentUserDep):
    service = ClipService()
    clip = await service.get_clip(clip_id, user["user_id"])
    if not clip:
        from core.exceptions import CustomException
        raise CustomException(message="Clip not found", code="NOT_FOUND", status_code=404)
    return clip


@clip_generation.post("/item/{clip_id}/burn")
async def burn_subtitles(clip_id: str, data: SubtitleBurnRequest, user: CurrentUserDep):
    service = ClipService()
    result = await service.process_clip_subtitles(clip_id, user["user_id"], data.model_dump())
    return result
