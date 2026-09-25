from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from subscription.dependencies import SubscriptionServiceDep
from hook_transitions.schema import (
    HookTransitionCatalogResponse,
    HookTransitionConfig,
    HookTransitionResolveResponse,
)
from hook_transitions.service import HookTransitionService

hook_transitions = APIRouter(prefix="/hook-transitions", tags=["hook-transitions"])


@hook_transitions.get("/catalog", response_model=HookTransitionCatalogResponse)
async def list_catalog(user: CurrentUserDep):
    return HookTransitionService.catalog()


@hook_transitions.post("/clips/{clip_id}/resolve", response_model=HookTransitionResolveResponse)
async def resolve_for_clip(
    clip_id: str, config: HookTransitionConfig, user: CurrentUserDep, subscription_service: SubscriptionServiceDep
):
    """The transition a config renders as for one clip -- what Auto would pick."""
    return await HookTransitionService(subscription_service).resolve_for_clip(clip_id, user["user_id"], config)
