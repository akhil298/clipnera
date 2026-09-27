from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import reels.jobs  # noqa: F401 -- registers the plan and render job handlers
from auth.dependencies import CurrentUserDep
from core.database import get_db
from core.responses import ApiResponse, ok
from feature_flags.dependencies import require_flag
from feature_flags.registry import BROLL_REELS
from broll.schema import GenerateShotRequest
from reels.schema import (
    ReelAssetsCompleteRequest,
    ReelAssetsInitRequest,
    ReelAssetsInitResponse,
    ReelCreateRequest,
    ReelResponse,
    ReelSceneUpdate,
    ReelSummary,
)
from reels.service import ReelService

reels_router = APIRouter(prefix="/reels", tags=["reels"], dependencies=[Depends(require_flag(BROLL_REELS))])


async def get_reel_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ReelService:
    return ReelService(session)


ReelServiceDep = Annotated[ReelService, Depends(get_reel_service)]


@reels_router.post("", response_model=ApiResponse[ReelResponse])
async def create_reel(data: ReelCreateRequest, user: CurrentUserDep, service: ReelServiceDep):
    return ok(await service.create(user["user_id"], data))


@reels_router.get("", response_model=ApiResponse[list[ReelSummary]])
async def list_reels(user: CurrentUserDep, service: ReelServiceDep):
    return ok(await service.list(user["user_id"]))


@reels_router.get("/{reel_id}", response_model=ApiResponse[ReelResponse])
async def get_reel(reel_id: str, user: CurrentUserDep, service: ReelServiceDep):
    return ok(await service.get(user["user_id"], reel_id))


@reels_router.post("/{reel_id}/assets/init", response_model=ApiResponse[ReelAssetsInitResponse])
async def init_assets(reel_id: str, data: ReelAssetsInitRequest, user: CurrentUserDep, service: ReelServiceDep):
    """Signed upload URLs for images and an optional voiceover; the browser PUTs straight to S3."""
    return ok(await service.init_assets(user["user_id"], reel_id, data))


@reels_router.post("/{reel_id}/assets/complete", response_model=ApiResponse[ReelResponse])
async def complete_assets(reel_id: str, data: ReelAssetsCompleteRequest, user: CurrentUserDep, service: ReelServiceDep):
    return ok(await service.complete_assets(user["user_id"], reel_id, data))


@reels_router.post("/{reel_id}/plan", response_model=ApiResponse[ReelResponse])
async def plan_reel(reel_id: str, user: CurrentUserDep, service: ReelServiceDep):
    """Write or use the script, voice it, and lay out the scene board (poll until status is ready)."""
    return ok(await service.plan(user["user_id"], reel_id))


@reels_router.post("/{reel_id}/scenes/{index}", response_model=ApiResponse[ReelResponse])
async def update_scene(reel_id: str, index: int, data: ReelSceneUpdate, user: CurrentUserDep, service: ReelServiceDep):
    return ok(await service.update_scene(user["user_id"], reel_id, index, data))


@reels_router.post("/{reel_id}/scenes/{index}/generate", response_model=ApiResponse[ReelResponse])
async def generate_scene(reel_id: str, index: int, data: GenerateShotRequest, user: CurrentUserDep, service: ReelServiceDep):
    """Pro: generate an AI shot for this scene (charged when queued, refunded if it fails)."""
    return ok(await service.generate_scene(user["user_id"], reel_id, index, data.shot))


@reels_router.post("/{reel_id}/render", response_model=ApiResponse[ReelResponse])
async def render_reel(reel_id: str, user: CurrentUserDep, service: ReelServiceDep):
    """Charge the render and queue it (poll until status is done)."""
    return ok(await service.render(user["user_id"], reel_id))
