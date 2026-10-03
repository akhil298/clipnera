from __future__ import annotations

import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, Response

from auth.dependencies import CurrentUserDep
from core.config import Environment, get_settings
from core.responses import ApiResponse, ok
from feature_flags.admin_service import FlagAdminService
from feature_flags.context import FlagContext, load_context
from feature_flags.dependencies import (
    ANON_COOKIE,
    FeatureFlagServiceDep,
    SessionDep,
    admin_service_for,
    bearer_user_id,
)
from feature_flags.engine import flags
from feature_flags.model import CONFIG_EDIT, FLAGS_EDIT, FLAGS_KILL, FLAGS_VIEW, SEGMENTS_EDIT
from feature_flags.registry import FLAGS, LEGACY_KEYS
from feature_flags.schema import (
    AdminAuditPageResponse,
    AdminConfigDetailResponse,
    AdminConfigListResponse,
    AdminConfigUpdateRequest,
    AdminEvaluateRequest,
    AdminEvaluationResponse,
    AdminFeatureFlagListResponse,
    AdminFeatureFlagUpdateRequest,
    AdminFlagDetailResponse,
    AdminFlagKillRequest,
    AdminFlagListResponse,
    AdminFlagsHealthResponse,
    AdminFlagUpdateRequest,
    AdminOverrideRequest,
    AdminReasonRequest,
    AdminSegmentListResponse,
    AdminSegmentUpdateRequest,
    FeatureFlagsResponse,
    FlagsBootstrapResponse,
    SubjectType,
)

ANON_COOKIE_MAX_AGE = 365 * 24 * 3600
ReasonQuery = Annotated[str, Query(min_length=10, max_length=500)]
Viewer = Annotated[FlagAdminService, Depends(admin_service_for(FLAGS_VIEW))]
FlagEditor = Annotated[FlagAdminService, Depends(admin_service_for(FLAGS_EDIT))]
Killer = Annotated[FlagAdminService, Depends(admin_service_for(FLAGS_KILL))]
ConfigEditor = Annotated[FlagAdminService, Depends(admin_service_for(CONFIG_EDIT))]
SegmentEditor = Annotated[FlagAdminService, Depends(admin_service_for(SEGMENTS_EDIT))]
LegacyViewer = Annotated[FlagAdminService, Depends(admin_service_for(FLAGS_VIEW, legacy=True))]
LegacyEditor = Annotated[FlagAdminService, Depends(admin_service_for(FLAGS_EDIT, legacy=True))]

# -- legacy (unchanged shapes) ----------------------------------------------------------

features = APIRouter(prefix="/features", tags=["features"])
admin_features = APIRouter(prefix="/admin/features", tags=["admin"])


@features.get(
    "",
    response_model=ApiResponse[FeatureFlagsResponse],
    description="Deprecated: use GET /flags/bootstrap. Now evaluated for the caller.",
)
async def get_features(_: CurrentUserDep, service: FeatureFlagServiceDep):
    effective = await service.effective()
    return ok(FeatureFlagsResponse(
        flags={key: on for key, on in effective.items() if key in LEGACY_KEYS or FLAGS[key].client}
    ))


@admin_features.get("", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def list_legacy_flags(service: LegacyViewer):
    return ok(await service.legacy_list())


@admin_features.patch("/{key}", response_model=ApiResponse[AdminFeatureFlagListResponse])
async def set_legacy_flag(key: str, body: AdminFeatureFlagUpdateRequest, service: LegacyEditor):
    await service.legacy_switch(key, body.enabled)
    return ok(await service.legacy_list(), message="Feature updated")


# -- public ----------------------------------------------------------------------------

flags_router = APIRouter(prefix="/flags", tags=["flags"])


@flags_router.get("/bootstrap", response_model=ApiResponse[FlagsBootstrapResponse])
async def bootstrap(request: Request, response: Response, session: SessionDep):
    """Every client flag and value for the caller. Signed out: public ones only, bucketed by ``cn_anon``."""
    response.headers["Cache-Control"] = "private, no-store"
    snapshot = await flags.snapshot_for(session)
    user_id = bearer_user_id(request)
    if user_id is not None:
        ctx = await load_context(session, FlagContext(user_id=user_id), snapshot)
        return ok(flags.bootstrap(ctx, "user", snapshot))
    anon_id = request.cookies.get(ANON_COOKIE)
    if not anon_id:
        anon_id = secrets.token_hex(16)
        response.set_cookie(
            ANON_COOKIE, anon_id, max_age=ANON_COOKIE_MAX_AGE, httponly=True, samesite="lax",
            secure=get_settings().ENVIRONMENT == Environment.PRODUCTION,
        )
    return ok(flags.bootstrap(FlagContext(anon_id=anon_id), "anonymous", snapshot))


# -- admin: flags ----------------------------------------------------------------------

admin_flags = APIRouter(prefix="/admin/flags", tags=["admin"])


@admin_flags.get("", response_model=ApiResponse[AdminFlagListResponse])
async def list_flags(service: Viewer):
    return ok(await service.list_flags())


@admin_flags.get("/health", response_model=ApiResponse[AdminFlagsHealthResponse])
async def flags_health(_: Viewer):
    return ok(AdminFlagsHealthResponse(
        snapshot_version=flags.snapshot.version,
        snapshot_age_seconds=round(flags.snapshot_age_seconds, 1),
        listening=flags.listening,
    ))


@admin_flags.get("/audit", response_model=ApiResponse[AdminAuditPageResponse])
async def audit_log(service: Viewer, cursor: Optional[str] = None, target_key: Optional[str] = None):
    return ok(await service.audit_page(target_key, cursor))


@admin_flags.get("/{key}", response_model=ApiResponse[AdminFlagDetailResponse])
async def get_flag(key: str, service: Viewer):
    return ok(await service.get_flag(key))


@admin_flags.patch("/{key}", response_model=ApiResponse[AdminFlagDetailResponse])
async def update_flag(key: str, body: AdminFlagUpdateRequest, service: FlagEditor):
    return ok(await service.update_flag(key, body), message="Saved")


@admin_flags.post("/{key}/kill", response_model=ApiResponse[AdminFlagDetailResponse])
async def kill_flag(key: str, body: AdminFlagKillRequest, service: Killer):
    return ok(await service.kill(key, body), message="Feature killed")


@admin_flags.post("/{key}/unkill", response_model=ApiResponse[AdminFlagDetailResponse])
async def restore_flag(key: str, body: AdminReasonRequest, service: Killer):
    return ok(await service.unkill(key, body.reason), message="Feature restored")


@admin_flags.put("/{key}/overrides", response_model=ApiResponse[AdminFlagDetailResponse])
async def set_flag_override(key: str, body: AdminOverrideRequest, service: FlagEditor):
    await service.set_override("flag", key, body)
    return ok(await service.get_flag(key), message="Override saved")


@admin_flags.delete(
    "/{key}/overrides/{subject_type}/{subject_id}", response_model=ApiResponse[AdminFlagDetailResponse]
)
async def delete_flag_override(
    key: str, subject_type: SubjectType, subject_id: str, reason: ReasonQuery, service: FlagEditor
):
    await service.delete_override("flag", key, subject_type, subject_id, reason)
    return ok(await service.get_flag(key), message="Override removed")


@admin_flags.post("/{key}/evaluate", response_model=ApiResponse[AdminEvaluationResponse])
async def evaluate_flag(key: str, body: AdminEvaluateRequest, service: Viewer):
    return ok(await service.evaluate(key, body))


@admin_flags.get("/{key}/history", response_model=ApiResponse[AdminAuditPageResponse])
async def flag_history(key: str, service: Viewer, cursor: Optional[str] = None):
    return ok(await service.audit_page(key, cursor))


# -- admin: remote config --------------------------------------------------------------

admin_config = APIRouter(prefix="/admin/config", tags=["admin"])


@admin_config.get("", response_model=ApiResponse[AdminConfigListResponse])
async def list_configs(service: Viewer):
    return ok(await service.list_configs())


@admin_config.get("/{key}", response_model=ApiResponse[AdminConfigDetailResponse])
async def get_config(key: str, service: Viewer):
    return ok(await service.get_config(key))


@admin_config.patch("/{key}", response_model=ApiResponse[AdminConfigDetailResponse])
async def update_config(key: str, body: AdminConfigUpdateRequest, service: ConfigEditor):
    return ok(await service.update_config(key, body), message="Saved")


@admin_config.put("/{key}/overrides", response_model=ApiResponse[AdminConfigDetailResponse])
async def set_config_override(key: str, body: AdminOverrideRequest, service: ConfigEditor):
    await service.set_override("config", key, body)
    return ok(await service.get_config(key), message="Override saved")


@admin_config.delete(
    "/{key}/overrides/{subject_type}/{subject_id}", response_model=ApiResponse[AdminConfigDetailResponse]
)
async def delete_config_override(
    key: str, subject_type: SubjectType, subject_id: str, reason: ReasonQuery, service: ConfigEditor
):
    await service.delete_override("config", key, subject_type, subject_id, reason)
    return ok(await service.get_config(key), message="Override removed")


# -- admin: segments -------------------------------------------------------------------

admin_segments = APIRouter(prefix="/admin/segments", tags=["admin"])


@admin_segments.get("", response_model=ApiResponse[AdminSegmentListResponse])
async def list_segments(service: Viewer):
    return ok(await service.list_segments())


@admin_segments.patch("/{key}", response_model=ApiResponse[AdminSegmentListResponse])
async def update_segment(key: str, body: AdminSegmentUpdateRequest, service: SegmentEditor):
    return ok(await service.update_segment(key, body), message="Saved")
