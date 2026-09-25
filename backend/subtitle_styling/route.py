from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from subtitle_styling.service import SubtitleStylingService
from subtitle_styling.schema import (
    SubtitleStylePresetsResponse,
    SubtitleBurnRequest,
    SubtitleBurnResponse,
    SubtitleStyleCreateRequest,
)
from core.logging_config import get_logger

log = get_logger(__name__)

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


async def prepare_burn_payload(user_id: str, data: SubtitleBurnRequest) -> dict:
    """The burn request clamped to the caller's plan, counted as one export.

    Shared by every route that burns captions, since each is reachable
    directly and the editor only hides locked options.
    """
    from core.database import AsyncSessionLocal
    from core.exceptions import CustomException
    from subscription.service import SubscriptionService, pro_required

    payload = data.model_dump()
    # The model itself, not its dump: a dump marks every unset field as sent,
    # which would override the preset's parts with blanks.
    payload["hook_transition"] = data.hook_transition

    async with AsyncSessionLocal() as session:
        subscription_service = SubscriptionService.for_session(session)
        entitlements = await subscription_service.get_entitlements(user_id)

        style = payload.get("style_type")
        if style and not entitlements.allows_caption_style(str(style)):
            raise CustomException(
                message=(
                    f"The '{style}' caption style requires a paid plan. "
                    "Upgrade to unlock the full caption library."
                ),
                code="CAPTION_STYLE_NOT_ENTITLED",
                status_code=403,
            )
        if data.hook_transition and not entitlements.allows_hook_transition(data.hook_transition.mode):
            raise pro_required("all_hook_transitions")
        await subscription_service.consume_daily_quota(user_id, "exports")

    if entitlements.watermark_forced:
        payload["enable_watermark"] = True
    return payload


@subtitle_styling.post("/burn/{clip_id}", response_model=SubtitleBurnResponse)
async def burn_subtitles(clip_id: str, data: SubtitleBurnRequest, user: CurrentUserDep):
    from clip_generation.service import ClipService

    payload = await prepare_burn_payload(user["user_id"], data)
    service = ClipService()
    result = await service.process_clip_subtitles(clip_id, user["user_id"], payload)
    return SubtitleBurnResponse(**result)
