from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import creator_intro.jobs  # noqa: F401 -- registers the render job handler
from auth.dependencies import CurrentUserDep
from core.database import get_db
from core.responses import ApiResponse, ok
from creator_intro.schema import (
    CreatorIntroAvatarRequest,
    CreatorIntroAvatarUpload,
    CreatorIntroResponse,
    CreatorIntroSaveRequest,
)
from creator_intro.service import CreatorIntroService
from subscription.dependencies import require_feature

creator_intro_router = APIRouter(prefix="/creator-intro", tags=["creator-intro"])
_pro = [Depends(require_feature("creator_intro"))]


async def get_creator_intro_service(session: Annotated[AsyncSession, Depends(get_db)]) -> CreatorIntroService:
    return CreatorIntroService(session)


CreatorIntroServiceDep = Annotated[CreatorIntroService, Depends(get_creator_intro_service)]


# Readable on every plan, so Free sees what it would get and the upload nudge knows
# whether an intro exists; making or changing one is Pro.
@creator_intro_router.get("", response_model=ApiResponse[Optional[CreatorIntroResponse]])
async def get_intro(user: CurrentUserDep, service: CreatorIntroServiceDep):
    return ok(await service.get(user["user_id"]))


@creator_intro_router.put("", response_model=ApiResponse[CreatorIntroResponse], dependencies=_pro)
async def save_intro(data: CreatorIntroSaveRequest, user: CurrentUserDep, service: CreatorIntroServiceDep):
    return ok(await service.save(user["user_id"], data))


@creator_intro_router.post("/avatar", response_model=ApiResponse[CreatorIntroAvatarUpload], dependencies=_pro)
async def avatar_upload(data: CreatorIntroAvatarRequest, user: CurrentUserDep, service: CreatorIntroServiceDep):
    """A signed URL the browser PUTs the picture to; pass its key as ``avatar_key`` when saving."""
    return ok(await service.avatar_upload(user["user_id"], data))


@creator_intro_router.post("/render", response_model=ApiResponse[CreatorIntroResponse], dependencies=_pro)
async def render_intro(user: CurrentUserDep, service: CreatorIntroServiceDep):
    """Queue a render of the saved intro (poll until status is ready)."""
    return ok(await service.render(user["user_id"]))
