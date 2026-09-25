from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from clip_generation.service import ClipService
from subtitle_styling.schema import SubtitleBurnRequest
from subscription.dependencies import SubscriptionServiceDep

clip_generation = APIRouter(prefix="/clips", tags=["clip-generation"])


@clip_generation.post("/{project_id}/generate")
async def generate_clips(
    project_id: str, user: CurrentUserDep, subscription_service: SubscriptionServiceDep, data: dict | None = None
):
    return await ClipService().generate_clips_for_user(
        project_id=project_id,
        user_id=user["user_id"],
        subscription_service=subscription_service,
        output_aspect_ratios=(data or {}).get("output_aspect_ratios"),
    )


@clip_generation.get("/{project_id}")
async def list_project_clips(project_id: str, user: CurrentUserDep):
    return await ClipService().list_project_clips(project_id, user["user_id"])


@clip_generation.get("/item/{clip_id}")
async def get_clip(clip_id: str, user: CurrentUserDep):
    return await ClipService().get_clip(clip_id, user["user_id"])


@clip_generation.post("/item/{clip_id}/burn")
async def burn_subtitles(clip_id: str, data: SubtitleBurnRequest, user: CurrentUserDep):
    return await ClipService().burn_clip_subtitles(clip_id, user["user_id"], data)
