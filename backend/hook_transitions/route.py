from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from hook_transitions.catalog import get_catalog
from subscription.dependencies import SubscriptionServiceDep
from subscription.service import pro_required
from hook_transitions.schema import (
    HookTransitionApplied,
    HookTransitionCatalogResponse,
    HookTransitionConfig,
    HookTransitionResolveResponse,
)

hook_transitions = APIRouter(prefix="/hook-transitions", tags=["hook-transitions"])


@hook_transitions.get("/catalog", response_model=HookTransitionCatalogResponse)
async def list_catalog(user: CurrentUserDep):
    return HookTransitionCatalogResponse(**get_catalog())


@hook_transitions.post("/clips/{clip_id}/resolve", response_model=HookTransitionResolveResponse)
async def resolve_for_clip(
    clip_id: str, config: HookTransitionConfig, user: CurrentUserDep, subscription_service: SubscriptionServiceDep
):
    """The transition a config renders as for one clip -- what Auto would pick."""
    from clip_generation.service import ClipService

    entitlements = await subscription_service.get_entitlements(user["user_id"])
    if not entitlements.allows_hook_transition(config.mode):
        raise pro_required("all_hook_transitions")

    spec = await ClipService().resolve_hook_transition(clip_id, user["user_id"], config)
    return HookTransitionResolveResponse(
        clip_id=clip_id,
        transition=HookTransitionApplied(**spec.to_dict()) if spec else None,
    )
