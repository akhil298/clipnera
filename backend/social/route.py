"""/social: connect accounts and publish clips.

Connecting and publishing need the admin feature flags on; reading, cancelling
and disconnecting always work, so turning the feature off never traps a user's
account or posts.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.database import get_db
from core.rate_limit import rate_limit
from core.responses import ApiResponse, ok
from social.model import SocialPlatform
from social.posts import SocialPostService
from social.schema import (
    AdminAccountListResponse,
    AdminSocialOverviewResponse,
    ConnectCallbackRequest,
    ConnectedAccountResponse,
    ConnectionsResponse,
    ConnectStartResponse,
    CreatePostsRequest,
    DeletionStatusResponse,
    DisconnectPreviewResponse,
    PostListResponse,
    PostResponse,
    PostStatusName,
    TikTokCreatorInfoResponse,
)
from social.service import SocialAccountService, SocialAdminService

social = APIRouter(prefix="/social", tags=["social"])
social_webhooks = APIRouter(prefix="/social/webhooks", tags=["social-webhooks"])
# The router-level dependency returns 403 to non-admins on every route here.
admin_social = APIRouter(prefix="/admin/social", tags=["admin"], dependencies=[Depends(get_current_admin)])

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _accounts(session: SessionDep) -> SocialAccountService:
    return SocialAccountService(session)


def _posts(session: SessionDep) -> SocialPostService:
    return SocialPostService(session)


def _admin(session: SessionDep) -> SocialAdminService:
    return SocialAdminService(session)


AccountServiceDep = Annotated[SocialAccountService, Depends(_accounts)]
PostServiceDep = Annotated[SocialPostService, Depends(_posts)]
AdminServiceDep = Annotated[SocialAdminService, Depends(_admin)]


# -- accounts ------------------------------------------------------------------


@social.get("/connections", response_model=ApiResponse[ConnectionsResponse])
async def get_connections(current_user: CurrentUserDep, service: AccountServiceDep):
    return ok(await service.connections(current_user["user_id"]))


@social.post("/oauth/{platform}/start", response_model=ApiResponse[ConnectStartResponse])
@rate_limit("10/hour")
async def start_connect(platform: SocialPlatform, current_user: CurrentUserDep, service: AccountServiceDep):
    return ok(await service.start_connect(current_user["user_id"], platform))


@social.post("/oauth/{platform}/callback", response_model=ApiResponse[ConnectedAccountResponse])
@rate_limit("20/hour")
async def complete_connect(
    platform: SocialPlatform, body: ConnectCallbackRequest, current_user: CurrentUserDep, service: AccountServiceDep
):
    account = await service.complete_connect(current_user["user_id"], platform, body.code, body.state)
    return ok(account, message="Account connected")


@social.get("/accounts/{account_id}/disconnect-preview", response_model=ApiResponse[DisconnectPreviewResponse])
async def disconnect_preview(account_id: str, current_user: CurrentUserDep, service: AccountServiceDep):
    return ok(await service.disconnect_preview(current_user["user_id"], account_id))


@social.delete("/accounts/{account_id}", response_model=ApiResponse[DisconnectPreviewResponse])
@rate_limit("20/hour")
async def disconnect(account_id: str, current_user: CurrentUserDep, service: AccountServiceDep):
    cancelled = await service.disconnect_for_user(current_user["user_id"], account_id)
    return ok(DisconnectPreviewResponse(account_id=account_id, pending_posts=cancelled), message="Account disconnected")


@social.get("/accounts/{account_id}/tiktok-creator-info", response_model=ApiResponse[TikTokCreatorInfoResponse])
@rate_limit("12/minute")
async def tiktok_creator_info(account_id: str, current_user: CurrentUserDep, service: AccountServiceDep):
    return ok(await service.tiktok_creator_info(current_user["user_id"], account_id))


# -- posts ---------------------------------------------------------------------


@social.post("/posts", response_model=ApiResponse[PostListResponse], status_code=201)
@rate_limit("30/hour")
async def create_posts(body: CreatePostsRequest, current_user: CurrentUserDep, service: PostServiceDep):
    return ok(await service.create(current_user["user_id"], body))


@social.get("/posts", response_model=ApiResponse[PostListResponse])
async def list_posts(
    current_user: CurrentUserDep,
    service: PostServiceDep,
    status: list[PostStatusName] | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return ok(await service.list(current_user["user_id"], status, limit, offset))


@social.post("/posts/{post_id}/cancel", response_model=ApiResponse[PostResponse])
@rate_limit("60/hour")
async def cancel_post(post_id: str, current_user: CurrentUserDep, service: PostServiceDep):
    return ok(await service.cancel(current_user["user_id"], post_id), message="Post cancelled")


# -- platform callbacks ----------------------------------------------------------
# Meta expects its own response shapes here, not the API envelope.


@social_webhooks.post("/meta/deauthorize")
@rate_limit("120/minute")
async def meta_deauthorize(service: AccountServiceDep, signed_request: str = Form(..., max_length=4096)):
    await service.meta_deauthorize(signed_request)
    return {"success": True}


@social_webhooks.post("/meta/data-deletion")
@rate_limit("120/minute")
async def meta_data_deletion(service: AccountServiceDep, signed_request: str = Form(..., max_length=4096)):
    return await service.meta_data_deletion(signed_request)


@social_webhooks.post("/tiktok")
@rate_limit("120/minute")
async def tiktok_webhook(request: Request, service: AccountServiceDep):
    await service.tiktok_event(request.headers.get("tiktok-signature"), await request.body())
    return {"success": True}


@social_webhooks.get("/data-deletion/{code}", response_model=ApiResponse[DeletionStatusResponse])
@rate_limit("30/minute")
async def data_deletion_status(code: str, service: AccountServiceDep):
    return ok(await service.deletion_status(code))


# -- admin -----------------------------------------------------------------------


@admin_social.get("/overview", response_model=ApiResponse[AdminSocialOverviewResponse])
async def admin_overview(service: AdminServiceDep, days: int = Query(7, ge=1, le=90)):
    return ok(await service.overview(days))


@admin_social.get("/accounts", response_model=ApiResponse[AdminAccountListResponse])
async def admin_accounts(
    service: AdminServiceDep,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return ok(await service.accounts(q, limit, offset))


@admin_social.post("/accounts/{account_id}/disconnect", response_model=ApiResponse[DisconnectPreviewResponse])
async def admin_force_disconnect(account_id: str, admin: CurrentAdminDep, service: AccountServiceDep):
    return ok(await service.admin_force_disconnect(account_id, admin.id), message="Account disconnected")
