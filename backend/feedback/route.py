from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_admin
from core.database import get_db
from core.responses import ApiResponse, ok
from feedback.schema import ClipQualityReport
from feedback.service import ClipQualityService

admin_quality = APIRouter(prefix="/admin/clip-quality", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def get_quality_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ClipQualityService:
    return ClipQualityService(session)


@admin_quality.get("", response_model=ApiResponse[ClipQualityReport])
async def clip_quality(
    service: Annotated[ClipQualityService, Depends(get_quality_service)],
    days: int = Query(30, ge=1, le=365),
):
    """How often users export, edit and publish clips, per director version."""
    return ok(await service.report(days))
