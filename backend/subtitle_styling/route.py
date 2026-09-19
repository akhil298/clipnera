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


@subtitle_styling.post("/burn/{clip_id}", response_model=SubtitleBurnResponse)
async def burn_subtitles(clip_id: str, data: SubtitleBurnRequest, user: CurrentUserDep):
    from clip_generation.service import ClipService
    from core.database import AsyncSessionLocal
    from core.exceptions import CustomException
    from subscription.service import SubscriptionService
    from subscription.repository import (
        PlanRepository,
        UserSubscriptionRepository,
        PaymentTransactionRepository,
        CreditLedgerRepository,
    )

    payload = data.model_dump()

    # A paid caption style has to be checked here too: the editor hides the
    # locked ones, but this endpoint is reachable directly.
    async with AsyncSessionLocal() as session:
        subscription_service = SubscriptionService(
            PlanRepository(session),
            UserSubscriptionRepository(session),
            PaymentTransactionRepository(session),
            CreditLedgerRepository(session),
        )
        entitlements = await subscription_service.get_entitlements(user["user_id"])

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
    if entitlements.watermark_forced:
        payload["enable_watermark"] = True

    service = ClipService()
    result = await service.process_clip_subtitles(clip_id, user["user_id"], payload)
    return SubtitleBurnResponse(**result)
