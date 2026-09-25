from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from clip_generation.service import ClipService
from clip_generation.schema import *
from subtitle_styling.schema import SubtitleBurnRequest
from subtitle_styling.route import prepare_burn_payload
from pipeline.route import permitted_aspect_ratios
from subscription.dependencies import SubscriptionServiceDep
from core.logging_config import get_logger

log = get_logger(__name__)

clip_generation = APIRouter(prefix="/clips", tags=["clip-generation"])


@clip_generation.post("/{project_id}/generate")
async def generate_clips(
    project_id: str, user: CurrentUserDep, subscription_service: SubscriptionServiceDep, data: dict | None = None
):
    service = ClipService()
    data = data or {}
    output_aspect_ratios = data.get("output_aspect_ratios")
    if isinstance(output_aspect_ratios, str):
        output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
    if output_aspect_ratios:
        entitlements = await subscription_service.get_entitlements(user["user_id"])
        output_aspect_ratios = permitted_aspect_ratios(entitlements, output_aspect_ratios)
    result = await service.generate_clips_for_project(
        project_id=project_id,
        user_id=user["user_id"],
        output_aspect_ratios=output_aspect_ratios,
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
    payload = await prepare_burn_payload(user["user_id"], data)
    service = ClipService()
    result = await service.process_clip_subtitles(clip_id, user["user_id"], payload)
    return result
