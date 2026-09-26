from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUserDep, get_current_admin
from core.database import get_db
from core.responses import ApiResponse, ok
from usage.schema import AdminUsageSummary, ProjectUsage
from usage.service import UsageService

usage = APIRouter(prefix="/usage", tags=["usage"])
admin_usage = APIRouter(prefix="/admin/usage", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def get_usage_service(session: Annotated[AsyncSession, Depends(get_db)]) -> UsageService:
    return UsageService(session)


UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]


@usage.get("/projects/{project_id}", response_model=ApiResponse[ProjectUsage])
async def project_usage(project_id: str, user: CurrentUserDep, service: UsageServiceDep):
    """AI tokens and dollars spent on one of the caller's videos, per step and model."""
    return ok(await service.project_usage(project_id, user["user_id"]))


@admin_usage.get("", response_model=ApiResponse[AdminUsageSummary])
async def admin_usage_summary(service: UsageServiceDep, days: int = Query(30, ge=1, le=365)):
    """Platform-wide AI spend over the last ``days`` days."""
    return ok(await service.admin_summary(days))
