"""/social: connect accounts and publish clips.

Connecting and publishing need the admin feature flags on; reading, cancelling
and disconnecting always work, so turning the feature off never traps a user's
account or posts.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentAdminDep, CurrentUserDep, get_current_admin
from core.config import get_settings
from core.database import get_db
from core.exceptions import CustomException
from core.logging_config import get_logger
from core.rate_limit import rate_limit
from core.responses import ApiResponse, ok
from social import quota
from social.model import DataDeletionRequest, PostStatus, SocialPlatform
from social.posts import SocialPostService
from social.repository import SocialRepository
from social.schema import (
    AdminAccountListResponse,
    AdminAccountResponse,
    AdminFailure,
    AdminPlatformStats,
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
from social.service import SocialAccountService, not_found
from social.webhooks import parse_meta_signed_request, verify_tiktok_signature

log = get_logger(__name__)

social = APIRouter(prefix="/social", tags=["social"])
social_webhooks = APIRouter(prefix="/social/webhooks", tags=["social-webhooks"])
# The router-level dependency returns 403 to non-admins on every route here.
admin_social = APIRouter(prefix="/admin/social", tags=["admin"], dependencies=[Depends(get_current_admin)])

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _accounts(session: SessionDep) -> SocialAccountService:
    return SocialAccountService(session)


def _posts(session: SessionDep) -> SocialPostService:
    return SocialPostService(session)


AccountServiceDep = Annotated[SocialAccountService, Depends(_accounts)]
PostServiceDep = Annotated[SocialPostService, Depends(_posts)]


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
    statuses = [PostStatus(s) for s in status] if status else None
    return ok(await service.list(current_user["user_id"], statuses, limit, offset))


@social.post("/posts/{post_id}/cancel", response_model=ApiResponse[PostResponse])
@rate_limit("60/hour")
async def cancel_post(post_id: str, current_user: CurrentUserDep, service: PostServiceDep):
    return ok(await service.cancel(current_user["user_id"], post_id), message="Post cancelled")


# -- platform callbacks ----------------------------------------------------------
# Meta expects its own response shapes here, not the API envelope.


def _meta_payload(signed_request: str) -> dict:
    payload = parse_meta_signed_request(signed_request)
    if not payload or not payload.get("user_id"):
        raise CustomException(message="Invalid signature", code="INVALID_SIGNATURE", status_code=400)
    return payload


@social_webhooks.post("/meta/deauthorize")
@rate_limit("120/minute")
async def meta_deauthorize(service: AccountServiceDep, signed_request: str = Form(..., max_length=4096)):
    payload = _meta_payload(signed_request)
    await service.platform_removed(SocialPlatform.INSTAGRAM, str(payload["user_id"]), delete_data=False)
    return {"success": True}


@social_webhooks.post("/meta/data-deletion")
@rate_limit("120/minute")
async def meta_data_deletion(
    session: SessionDep, service: AccountServiceDep, signed_request: str = Form(..., max_length=4096)
):
    payload = _meta_payload(signed_request)
    deleted = await service.platform_removed(SocialPlatform.INSTAGRAM, str(payload["user_id"]), delete_data=True)
    code = secrets.token_hex(8)
    session.add(
        DataDeletionRequest(
            confirmation_code=code, platform=SocialPlatform.INSTAGRAM, accounts_deleted=deleted, completed=True
        )
    )
    await session.commit()
    status_url = f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/data-deletion?code={code}"
    return {"url": status_url, "confirmation_code": code}


@social_webhooks.post("/tiktok")
@rate_limit("120/minute")
async def tiktok_webhook(request: Request, service: AccountServiceDep):
    body = await request.body()
    if not verify_tiktok_signature(request.headers.get("tiktok-signature"), body):
        raise CustomException(message="Invalid signature", code="INVALID_SIGNATURE", status_code=400)
    try:
        event = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CustomException(message="Invalid body", code="INVALID_BODY", status_code=400) from exc
    if event.get("client_key") != get_settings().TIKTOK_CLIENT_KEY:
        raise CustomException(message="Unknown client", code="INVALID_BODY", status_code=400)
    if event.get("event") == "authorization.removed" and event.get("user_openid"):
        try:
            reason = int(json.loads(event.get("content") or "{}").get("reason", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            reason = 0
        # reason 2: the TikTok account itself was deleted, so delete what we hold too.
        await service.platform_removed(SocialPlatform.TIKTOK, str(event["user_openid"]), delete_data=reason == 2)
    return {"success": True}


@social_webhooks.get("/data-deletion/{code}", response_model=ApiResponse[DeletionStatusResponse])
@rate_limit("30/minute")
async def data_deletion_status(code: str, session: SessionDep):
    record = await session.get(DataDeletionRequest, code[:32])
    if not record:
        raise not_found("Deletion request")
    return ok(
        DeletionStatusResponse(
            confirmation_code=record.confirmation_code,
            platform=record.platform.value,
            completed=record.completed,
            accounts_deleted=record.accounts_deleted,
            requested_at=record.created_at,
        )
    )


# -- admin -----------------------------------------------------------------------


@admin_social.get("/overview", response_model=ApiResponse[AdminSocialOverviewResponse])
async def admin_overview(session: SessionDep, days: int = Query(7, ge=1, le=90)):
    repo = SocialRepository(session)
    accounts: dict[SocialPlatform, dict[str, int]] = {p: {} for p in SocialPlatform}
    for platform, status, count in await repo.account_counts():
        accounts[platform][status.value] = count
    posts: dict[SocialPlatform, dict[str, int]] = {p: {} for p in SocialPlatform}
    for platform, status, count in await repo.post_counts(datetime.utcnow() - timedelta(days=days)):
        posts[platform][status.value] = count
    stats = []
    for platform in SocialPlatform:
        done = posts[platform].get("published", 0) + posts[platform].get("failed", 0)
        stats.append(
            AdminPlatformStats(
                platform=platform.value,
                accounts=accounts[platform],
                posts=posts[platform],
                success_rate=round(posts[platform].get("published", 0) / done, 4) if done else None,
            )
        )
    failures = [
        AdminFailure(
            post_id=post.id,
            platform=post.platform.value,
            account_handle=account.handle,
            user_email=user.email,
            error_code=post.error_code,
            error_message=post.error_message,
            attempts=post.attempts,
            failed_at=post.updated_at,
        )
        for post, account, user in await repo.recent_failures(25)
    ]
    return ok(
        AdminSocialOverviewResponse(
            window_days=days, platforms=stats, quota=await quota.usage(session), recent_failures=failures
        )
    )


@admin_social.get("/accounts", response_model=ApiResponse[AdminAccountListResponse])
async def admin_accounts(
    session: SessionDep,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = await SocialRepository(session).admin_accounts((q or "").strip() or None, limit, offset)
    return ok(
        AdminAccountListResponse(
            accounts=[
                AdminAccountResponse(
                    id=account.id,
                    platform=account.platform.value,
                    handle=account.handle,
                    display_name=account.display_name,
                    follower_count=account.follower_count,
                    status=account.status.value,
                    status_reason=account.status_reason,
                    user_id=user.id,
                    user_email=user.email,
                    connected_at=account.connected_at,
                )
                for account, user in rows
            ]
        )
    )


@admin_social.post("/accounts/{account_id}/disconnect", response_model=ApiResponse[DisconnectPreviewResponse])
async def admin_force_disconnect(
    account_id: str, admin: CurrentAdminDep, session: SessionDep, service: AccountServiceDep
):
    account = await SocialRepository(session).get_account_by_id(account_id)
    if not account:
        raise not_found()
    cancelled = await service.disconnect(account, "admin", admin.id)
    log.info(f"Admin {admin.id} force-disconnected social account={account_id}")
    return ok(DisconnectPreviewResponse(account_id=account_id, pending_posts=cancelled), message="Account disconnected")
