from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from subtitle_styling.service import SubtitleStylingService
from subtitle_styling.schema import (
    SubtitleStylePresetsResponse,
    SubtitleBurnRequest,
    SubtitleBurnResponse,
    SubtitleStyleCreateRequest,
)

subtitle_styling = APIRouter(prefix="/subtitle-styles", tags=["subtitle-styles"])


@subtitle_styling.get("/presets", response_model=SubtitleStylePresetsResponse)
async def list_presets(user: CurrentUserDep):
    service = SubtitleStylingService()
    presets = await service.get_style_presets()
    return SubtitleStylePresetsResponse(presets=presets)


@subtitle_styling.post("/", response_model=dict)
async def create_style(data: SubtitleStyleCreateRequest, user: CurrentUserDep):
    from clip_generation.service import ClipService
    service = ClipService()
    return await service.create_subtitle_style(
        user_id=user["user_id"],
        name=data.name,
        style_type=data.style_type,
        config=data.config,
    )


@subtitle_styling.get("/", response_model=list[dict])
async def list_user_styles(user: CurrentUserDep):
    from clip_generation.service import ClipService
    service = ClipService()
    return await service.list_subtitle_styles(user["user_id"])


@subtitle_styling.post("/burn/{clip_id}", response_model=SubtitleBurnResponse)
async def burn_subtitles(clip_id: str, data: SubtitleBurnRequest, user: CurrentUserDep):
    from clip_generation.service import ClipService

    result = await ClipService().burn_clip_subtitles(clip_id, user["user_id"], data)
    return SubtitleBurnResponse(**result)
