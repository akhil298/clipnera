from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.database import get_db
from core.responses import ApiResponse, ok
from referral.schema import (
    AdminReferralResponse,
    AdminReferralSettingsResponse,
    AdminReferralVoidRequest,
    InvitedByResponse,
    MyReferralsResponse,
    ReferralSettingsRequest,
    ValidateCodeResponse,
)
from referral.service import ReferralService

referrals = APIRouter(prefix="/referrals", tags=["referrals"])
admin_referrals = APIRouter(
    prefix="/admin/referrals", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


def get_referral_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ReferralService:
    return ReferralService(session)


ReferralServiceDep = Annotated[ReferralService, Depends(get_referral_service)]


@referrals.get("/me", response_model=ApiResponse[MyReferralsResponse])
async def my_referrals(user: CurrentUserDep, service: ReferralServiceDep):
    await service.refresh_open(user["user_id"])
    return ok(await service.my_referrals(user["user_id"]))


@referrals.get("/invited-by", response_model=ApiResponse[Optional[InvitedByResponse]])
async def invited_by(user: CurrentUserDep, service: ReferralServiceDep):
    await service.refresh_open(user["user_id"])
    return ok(await service.invited_by(user["user_id"]))


@referrals.get("/validate/{code}", response_model=ApiResponse[ValidateCodeResponse])
async def validate_code(code: str, user: CurrentUserDep, service: ReferralServiceDep):
    return ok(await service.validate(user["user_id"], code))


@admin_referrals.get("", response_model=ApiResponse[list[AdminReferralResponse]])
async def list_referrals(
    service: ReferralServiceDep,
    status: Optional[str] = None,
    review_state: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ok(await service.admin_list(status, review_state, q, limit, offset))


@admin_referrals.post("/{referral_id}/approve", response_model=ApiResponse[None])
async def approve_referral(referral_id: str, admin: CurrentAdminDep, service: ReferralServiceDep):
    await service.admin_approve(referral_id, admin.id)
    return ok(None, message="Referral approved")


@admin_referrals.post("/{referral_id}/void", response_model=ApiResponse[None])
async def void_referral(
    referral_id: str, body: AdminReferralVoidRequest, admin: CurrentAdminDep, service: ReferralServiceDep
):
    await service.admin_void(referral_id, admin.id, body.reason)
    return ok(None, message="Referral voided")


@admin_referrals.get("/settings", response_model=ApiResponse[AdminReferralSettingsResponse])
async def get_settings(service: ReferralServiceDep):
    return ok(await service.admin_settings())


@admin_referrals.put("/settings", response_model=ApiResponse[AdminReferralSettingsResponse])
async def update_settings(body: ReferralSettingsRequest, admin: CurrentAdminDep, service: ReferralServiceDep):
    return ok(await service.update_settings(body, admin.id), message="Referral settings saved")
