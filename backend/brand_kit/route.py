from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentUserDep, get_db
from brand_kit.repository import BrandKitRepository
from brand_kit.schema import CreateBrandKitRequest, BrandKitResponse
from brand_kit.service import BrandKitService
from sqlalchemy.ext.asyncio import AsyncSession


async def get_brand_kit_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BrandKitRepository:
    return BrandKitRepository(session)


BrandKitRepoDep = Annotated[BrandKitRepository, Depends(get_brand_kit_repo)]

brand_kit = APIRouter(prefix="/brand-kits", tags=["brand-kits"])


@brand_kit.get("", response_model=list[BrandKitResponse])
async def list_brand_kits(
    current_user: CurrentUserDep,
    repo: BrandKitRepoDep,
):
    service = BrandKitService(repo)
    return await service.list_brand_kits(current_user["user_id"])


@brand_kit.get("/me", response_model=BrandKitResponse)
async def get_my_brand_kit(
    current_user: CurrentUserDep,
    repo: BrandKitRepoDep,
):
    service = BrandKitService(repo)
    return await service.get_brand_kit(current_user["user_id"])


@brand_kit.post("", response_model=BrandKitResponse, status_code=201)
async def create_or_update_brand_kit(
    data: CreateBrandKitRequest,
    current_user: CurrentUserDep,
    repo: BrandKitRepoDep,
):
    service = BrandKitService(repo)
    return await service.create_or_update_brand_kit(current_user["user_id"], data)


@brand_kit.delete("/{brand_kit_id}", status_code=204)
async def delete_brand_kit(
    brand_kit_id: str,
    current_user: CurrentUserDep,
    repo: BrandKitRepoDep,
):
    service = BrandKitService(repo)
    await service.delete_brand_kit(current_user["user_id"], brand_kit_id)
    return None
