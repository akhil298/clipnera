from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep, get_db
from brand_kit.repository import BrandKitRepository
from brand_kit.schema import CreateBrandKitRequest, BrandKitResponse
from brand_kit.service import BrandKitService
from subscription.dependencies import require_feature
from sqlalchemy.ext.asyncio import AsyncSession


async def get_brand_kit_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BrandKitService:
    return BrandKitService(BrandKitRepository(session))


BrandKitServiceDep = Annotated[BrandKitService, Depends(get_brand_kit_service)]

brand_kit = APIRouter(prefix="/brand-kits", tags=["brand-kits"])


@brand_kit.get("", response_model=list[BrandKitResponse])
async def list_brand_kits(current_user: CurrentUserDep, service: BrandKitServiceDep):
    return await service.list_brand_kits(current_user["user_id"])


@brand_kit.get("/me", response_model=BrandKitResponse)
async def get_my_brand_kit(current_user: CurrentUserDep, service: BrandKitServiceDep):
    return await service.get_brand_kit(current_user["user_id"])


# Existing kits stay readable and deletable on Free; only creating or editing is Pro.
@brand_kit.post(
    "", response_model=BrandKitResponse, status_code=201,
    dependencies=[Depends(require_feature("brand_kit_edit"))],
)
async def create_or_update_brand_kit(
    data: CreateBrandKitRequest, current_user: CurrentUserDep, service: BrandKitServiceDep
):
    return await service.create_or_update_brand_kit(current_user["user_id"], data)


@brand_kit.delete("/{brand_kit_id}", status_code=204)
async def delete_brand_kit(brand_kit_id: str, current_user: CurrentUserDep, service: BrandKitServiceDep):
    await service.delete_brand_kit(current_user["user_id"], brand_kit_id)
    return None
