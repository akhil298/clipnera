from __future__ import annotations

from clip_generation.service import ClipService
from hook_transitions.catalog import get_catalog
from hook_transitions.schema import (
    HookTransitionApplied,
    HookTransitionCatalogResponse,
    HookTransitionConfig,
    HookTransitionResolveResponse,
)
from subscription.service import SubscriptionService, require_hook_transition


class HookTransitionService:
    def __init__(self, subscription_service: SubscriptionService) -> None:
        self._subscription_service = subscription_service

    @staticmethod
    def catalog() -> HookTransitionCatalogResponse:
        return HookTransitionCatalogResponse(**get_catalog())

    async def resolve_for_clip(
        self, clip_id: str, user_id: str, config: HookTransitionConfig
    ) -> HookTransitionResolveResponse:
        """The transition a config renders as for one clip -- what Auto would pick."""
        entitlements = await self._subscription_service.get_entitlements(user_id)
        require_hook_transition(entitlements, config.mode)

        spec = await ClipService().resolve_hook_transition(clip_id, user_id, config)
        return HookTransitionResolveResponse(
            clip_id=clip_id,
            transition=HookTransitionApplied(**spec.to_dict()) if spec else None,
        )
