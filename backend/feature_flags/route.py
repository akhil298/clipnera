from __future__ import annotations

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.responses import ApiResponse, ok
from feature_flags.dependencies import FeatureFlagServiceDep
from feature_flags.registry import FLAGS
from feature_flags.schema import (
    AdminFeatureFlagListResponse,
    AdminFeatureFlagResponse,
    AdminFeatureFlagUpdateRequest,
    FeatureFlagsResponse,
)
from feature_flags.service import FeatureFlagService, resolve

features = APIRouter(prefix="/features", tags=["features"])
admin_features = APIRouter(
    prefix="/admin/features", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


@features.get("", response_model=ApiResponse[FeatureFlagsResponse])
async def get_features(_: CurrentUserDep, service: FeatureFlagServiceDep):
    return ok(FeatureFlagsResponse(flags=await service.effective()))


async def _admin_list(service: FeatureFlagService) -> AdminFeatureFlagListResponse:
    rows = await service.rows()
    effective = resolve({key: row.enabled for key, row in rows.items()})
    return AdminFeatureFlagListResponse(
        flags=[
            AdminFeatureFlagResponse(
                key=flag.key,
                label=flag.label,
                description=flag.description,
                parent=flag.parent,
                enabled=bool(rows.get(flag.key) and rows[flag.key].enabled),
                effective=effective[flag.key],
                updated_at=rows[flag.key].updated_at if flag.key in rows else None,
            )
            for flag in FLAGS.values()
        ]
    )


@admin_features.get("", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def list_flags(service: FeatureFlagServiceDep):
    return ok(await _admin_list(service))


@admin_features.patch("/{key}", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def set_flag(
    key: str, body: AdminFeatureFlagUpdateRequest, admin: CurrentAdminDep, service: FeatureFlagServiceDep
):
    await service.set(key, body.enabled, admin.id)
    return ok(await _admin_list(service), message="Feature updated")
