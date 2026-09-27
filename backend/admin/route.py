from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from admin.repository import AdminRepository
from admin.schema import (
    AdminGrowthResponse,
    AdminOverviewResponse,
    AdminUserDetailResponse,
    AdminUserPlanRequest,
    AdminUserResponse,
    AdminUserSort,
)
from admin.service import AdminService
from auth.dependencies import CurrentAdminDep, get_current_admin
from core.database import get_db
from core.responses import ApiResponse, ok
from subscription.repository import PlanRepository
from subscription.service import SubscriptionService

# The router-level dependency returns 403 to non-admins on every route here,
# including ones added later.
admin = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def get_admin_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AdminService:
    return AdminService(AdminRepository(session), PlanRepository(session), SubscriptionService.for_session(session))


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


@admin.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    service: AdminServiceDep,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: AdminUserSort = Query("newest"),
) -> list[AdminUserResponse]:
    return await service.list_users(q, limit, offset, sort)


@admin.get("/users/{user_id}/detail", response_model=ApiResponse[AdminUserDetailResponse])
async def get_user_detail(user_id: str, service: AdminServiceDep):
    """One user's full history: projects and their sources, logins, payments and credits."""
    return ok(await service.user_detail(user_id))


@admin.patch("/users/{user_id}/plan", response_model=AdminUserResponse)
async def set_user_plan(
    user_id: str, body: AdminUserPlanRequest, admin_user: CurrentAdminDep, service: AdminServiceDep
) -> AdminUserResponse:
    """Grant Pro for a number of days (stacked on any current Pro) or revoke it,
    for refunds, gifts or testing."""
    return await service.set_plan(user_id, body, admin_user.id)


@admin.get("/overview", response_model=AdminOverviewResponse)
async def get_overview(service: AdminServiceDep) -> AdminOverviewResponse:
    return await service.overview()


@admin.get("/growth", response_model=ApiResponse[AdminGrowthResponse])
async def get_growth(service: AdminServiceDep, days: int = Query(30, ge=1, le=365)):
    """Platform growth per UTC day: sign-ups, active users, logins, output, revenue and AI spend."""
    return ok(await service.growth(days))
