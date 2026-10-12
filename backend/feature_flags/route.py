from __future__ import annotations

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.responses import ApiResponse, ok
from feature_flags.dependencies import FeatureFlagServiceDep
from feature_flags.schema import (
    AdminFeatureFlagListResponse,
    AdminFeatureFlagUpdateRequest,
    AdminFeatureFlagUserRequest,
    FeatureFlagsResponse,
)

features = APIRouter(prefix="/features", tags=["features"])
admin_features = APIRouter(
    prefix="/admin/features", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


@features.get("", response_model=ApiResponse[FeatureFlagsResponse])
async def get_features(user: CurrentUserDep, service: FeatureFlagServiceDep):
    return ok(FeatureFlagsResponse(flags=await service.effective(user["user_id"])))


@admin_features.get("", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def list_flags(service: FeatureFlagServiceDep):
    return ok(await service.admin_list())


@admin_features.patch("/{key}", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def set_flag(
    key: str, body: AdminFeatureFlagUpdateRequest, admin: CurrentAdminDep, service: FeatureFlagServiceDep
):
    await service.set(key, body.enabled, admin.id)
    return ok(await service.admin_list(), message="Feature updated")


@admin_features.put("/{key}/users", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def set_test_user(
    key: str, body: AdminFeatureFlagUserRequest, admin: CurrentAdminDep, service: FeatureFlagServiceDep
):
    """Turn a flag on (or back off) for one user by email while it stays off for everyone else."""
    await service.set_test_user(key, body.email, body.allowed, admin.id)
    return ok(await service.admin_list(), message="Test users updated")
