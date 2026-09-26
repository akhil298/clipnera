from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep, get_current_admin
from broll.repository import BrollRepository
import broll.generation_job  # noqa: F401 -- registers the AI shot job
from broll.schema import (
    BrollAssetListResponse,
    GenerateShotRequest,
    BrollPlacementUpdate,
    BrollPreview,
    ClipBrollResponse,
    BrollAssetResponse,
    BrollIngestRequest,
    BrollIngestResponse,
    BrollStatusRequest,
)
from broll.service import BrollService, ClipBrollService
from core.database import get_db
from core.responses import ApiResponse, ok

broll = APIRouter(prefix="/broll", tags=["broll"])
admin_broll = APIRouter(prefix="/admin/broll", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def get_broll_service(session: Annotated[AsyncSession, Depends(get_db)]) -> BrollService:
    return BrollService(BrollRepository(session))


BrollServiceDep = Annotated[BrollService, Depends(get_broll_service)]


@admin_broll.get("/assets", response_model=ApiResponse[BrollAssetListResponse])
async def list_assets(
    service: BrollServiceDep,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, pattern="^(ingesting|live|blocked|taken_down|failed)$"),
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ok(await service.list_assets(q, status, limit, offset))


@admin_broll.post("/assets/{asset_id}/status", response_model=ApiResponse[BrollAssetResponse])
async def set_asset_status(asset_id: str, data: BrollStatusRequest, service: BrollServiceDep):
    """Block or take down an asset (e.g. a licence complaint); it leaves search at once."""
    return ok(await service.set_status(asset_id, data))


@admin_broll.post("/ingest", response_model=ApiResponse[BrollIngestResponse])
async def ingest(data: BrollIngestRequest, service: BrollServiceDep):
    """Queue a stock search-and-ingest for one topic."""
    return ok(await service.queue_ingest(data), "Ingest queued")


async def get_clip_broll_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ClipBrollService:
    return ClipBrollService(session)


ClipBrollServiceDep = Annotated[ClipBrollService, Depends(get_clip_broll_service)]


@broll.get("/clips/{clip_id}", response_model=ApiResponse[ClipBrollResponse])
async def clip_broll(clip_id: str, user: CurrentUserDep, service: ClipBrollServiceDep):
    """A clip's cutaways with the chosen shot and alternates for each."""
    return ok(await service.get(clip_id, user["user_id"]))


@broll.post("/clips/{clip_id}/placements/{index}", response_model=ApiResponse[ClipBrollResponse])
async def update_placement(
    clip_id: str, index: int, data: BrollPlacementUpdate, user: CurrentUserDep, service: ClipBrollServiceDep,
):
    """Swap or remove one cutaway; the next export uses the change."""
    return ok(await service.update(clip_id, user["user_id"], index, data))


@broll.post("/clips/{clip_id}/placements/{index}/generate", response_model=ApiResponse[ClipBrollResponse])
async def generate_placement(
    clip_id: str, index: int, data: GenerateShotRequest, user: CurrentUserDep, service: ClipBrollServiceDep,
):
    """Pro: generate an AI shot for one cutaway (charged when queued, refunded if it fails)."""
    return ok(await service.generate(clip_id, user["user_id"], index, data.shot))


@broll.get("/search", response_model=ApiResponse[list[BrollPreview]])
async def search_library(
    user: CurrentUserDep, service: ClipBrollServiceDep,
    q: str = Query(..., min_length=2, max_length=120), min_duration: float = Query(0.0, ge=0, le=30),
):
    """Library shots for a phrase, as previews, for picking a cutaway by hand."""
    return ok(await service.search(q, min_duration))
