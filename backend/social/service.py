"""Connecting, listing and disconnecting social accounts."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from feature_flags.registry import SOCIAL_PUBLISHING, social_platform_flag
from feature_flags.service import FeatureFlagService
from social import audit, quota
from social.credentials import fresh_tokens
from social.model import (
    AccountStatus,
    AuditAction,
    ConnectedAccount,
    DataDeletionRequest,
    ScheduledPost,
    SocialPlatform,
)
from social.oauth_state import OAuthStateStore
from social.providers import get_provider
from social.providers.base import ErrorKind, PkcePair, PlatformError, PlatformProvider, Profile, TokenSet
from social.repository import SocialRepository
from social.schema import (
    AdminAccountListResponse,
    AdminAccountResponse,
    AdminFailure,
    AdminPlatformStats,
    AdminSocialOverviewResponse,
    ConnectedAccountResponse,
    ConnectionsResponse,
    ConnectStartResponse,
    DeletionStatusResponse,
    DisconnectPreviewResponse,
    PlatformInfo,
    TikTokCreatorInfoResponse,
)
from social.tokens import TokenStore
from social.webhooks import parse_meta_signed_request, verify_tiktok_signature
from subscription.entitlements import Entitlements
from subscription.service import SubscriptionService, pro_required

log = get_logger(__name__)


def not_found(what: str = "Account") -> CustomException:
    return CustomException(message=f"{what} not found", code="NOT_FOUND", status_code=404)


def platform_error_response(exc: PlatformError) -> CustomException:
    status = 502 if exc.kind in (ErrorKind.TRANSIENT, ErrorKind.QUOTA) else 400
    return CustomException(message=exc.message, code="PLATFORM_ERROR", status_code=status, extra={"reason": exc.code})


def account_response(account: ConnectedAccount) -> ConnectedAccountResponse:
    return ConnectedAccountResponse(
        id=account.id,
        platform=account.platform.value,
        handle=account.handle,
        display_name=account.display_name,
        avatar_url=account.avatar_url,
        follower_count=account.follower_count,
        follower_count_updated_at=account.follower_count_updated_at,
        status=account.status.value,
        status_reason=account.status_reason,
        connected_at=account.connected_at,
    )


def _apply_profile(account: ConnectedAccount, profile: Profile, scopes: str | None) -> None:
    account.handle = profile.handle
    account.display_name = profile.display_name
    account.avatar_url = profile.avatar_url
    account.follower_count = profile.follower_count
    account.follower_count_updated_at = datetime.utcnow()
    account.scopes = scopes
    account.status = AccountStatus.ACTIVE
    account.status_reason = None


def clear_profile(account: ConnectedAccount, reason: str) -> None:
    """Keep the row for the audit trail, drop everything we learned from the platform."""
    account.status = AccountStatus.DISCONNECTED
    account.status_reason = reason
    account.handle = None
    account.display_name = None
    account.avatar_url = None
    account.follower_count = None
    account.scopes = None


class SocialAccountService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SocialRepository(session)
        self._flags = FeatureFlagService(session)
        self._subscriptions = SubscriptionService.for_session(session)

    # -- reads ---------------------------------------------------------------

    async def connections(self, user_id: str) -> ConnectionsResponse:
        flags = await self._flags.effective()
        ent = await self._subscriptions.get_entitlements(user_id)
        platforms = []
        for platform in SocialPlatform:
            provider = get_provider(platform)
            platforms.append(
                PlatformInfo(
                    platform=platform.value,
                    label=provider.label,
                    available=flags[social_platform_flag(platform.value)] and provider.is_configured(),
                    allowed_by_plan=platform.value in ent.social_platforms,
                    caption_max_chars=provider.caption_max_chars,
                    max_duration_seconds=provider.limits.max_duration_seconds,
                    pending_review_note=provider.pending_review_note,
                )
            )
        accounts = await self._repo.list_accounts(user_id)
        return ConnectionsResponse(
            platforms=platforms,
            accounts=[account_response(a) for a in accounts],
            max_accounts=ent.social_max_accounts,
            can_schedule=ent.social_scheduling,
            max_schedule_days=ent.social_max_schedule_days,
            posts_per_day=ent.social_posts_per_day,
        )

    async def disconnect_preview(self, user_id: str, account_id: str) -> DisconnectPreviewResponse:
        account = await self._repo.get_account(account_id, user_id)
        if not account:
            raise not_found()
        return DisconnectPreviewResponse(
            account_id=account.id, pending_posts=await self._repo.count_pending_posts(account.id)
        )

    async def tiktok_creator_info(self, user_id: str, account_id: str) -> TikTokCreatorInfoResponse:
        account = await self._repo.get_account(account_id, user_id)
        if not account or account.platform != SocialPlatform.TIKTOK:
            raise not_found()
        async with get_provider(SocialPlatform.TIKTOK) as provider:
            try:
                tokens = await fresh_tokens(self._session, account, provider)
                info = await provider.creator_info(tokens)
            except PlatformError as exc:
                raise platform_error_response(exc) from exc
        return TikTokCreatorInfoResponse(**info)

    # -- connect ---------------------------------------------------------------

    async def _require_platform(self, user_id: str, platform: SocialPlatform) -> tuple[PlatformProvider, Entitlements]:
        await self._flags.require(SOCIAL_PUBLISHING, social_platform_flag(platform.value))
        provider = get_provider(platform)
        if not provider.is_configured():
            raise CustomException(
                message=f"{provider.label} is not set up yet.", code="PLATFORM_NOT_CONFIGURED", status_code=503
            )
        ent = await self._subscriptions.get_entitlements(user_id)
        if platform.value not in ent.social_platforms:
            raise pro_required(f"social_{platform.value}")
        return provider, ent

    async def start_connect(self, user_id: str, platform: SocialPlatform) -> ConnectStartResponse:
        provider, ent = await self._require_platform(user_id, platform)
        accounts = await self._repo.list_accounts(user_id)
        reconnecting = any(a.platform == platform for a in accounts)
        if not reconnecting and len(accounts) >= ent.social_max_accounts:
            raise self._account_limit(ent)
        pkce = PkcePair.generate() if provider.uses_pkce else None
        state = await OAuthStateStore(self._session).create(user_id, platform, pkce.verifier if pkce else None)
        return ConnectStartResponse(authorize_url=provider.authorize_url(state, pkce.challenge if pkce else None))

    async def complete_connect(
        self, user_id: str, platform: SocialPlatform, code: str, state: str
    ) -> ConnectedAccountResponse:
        # The state is checked before anything else, so a forged callback learns nothing.
        consumed = await OAuthStateStore(self._session).consume(state, user_id, platform)
        provider, ent = await self._require_platform(user_id, platform)
        async with provider:
            try:
                tokens = await provider.exchange_code(code, consumed.code_verifier)
                profile = await provider.fetch_profile(tokens)
            except PlatformError as exc:
                log.warning(f"Connect {platform.value} failed for user={user_id}: {exc.code}")
                raise platform_error_response(exc) from exc
            try:
                account = await self._link(user_id, platform, profile, tokens, ent)
            except CustomException:
                await self._revoke_quietly(provider, tokens)
                raise
        return account_response(account)

    async def _link(
        self, user_id: str, platform: SocialPlatform, profile: Profile, tokens: TokenSet, ent: Entitlements
    ) -> ConnectedAccount:
        existing = await self._repo.find_live(platform, profile.platform_user_id)
        if existing and existing.user_id != user_id:
            log.warning(f"Blocked linking {platform.value} account already linked to another user (by user={user_id})")
            raise CustomException(
                message=(
                    f"This {get_provider(platform).label} account is already connected to another Clipnera user. "
                    "Disconnect it there first."
                ),
                code="ACCOUNT_LINKED_ELSEWHERE",
                status_code=409,
            )
        if existing:
            account, action = existing, AuditAction.RECONNECTED
        else:
            if await self._repo.count_live_accounts(user_id) >= ent.social_max_accounts:
                raise self._account_limit(ent)
            account = ConnectedAccount(
                id=str(uuid4()), user_id=user_id, platform=platform, platform_user_id=profile.platform_user_id
            )
            self._session.add(account)
            action = AuditAction.CONNECTED
        _apply_profile(account, profile, tokens.scopes)
        try:
            await self._session.flush()
            await TokenStore(self._session).save(account.id, tokens)
            audit.record(
                self._session, action, "user", actor_user_id=user_id, user_id=user_id,
                account_id=account.id, platform=platform,
            )
            await self._session.commit()
        except IntegrityError as exc:
            # Another user linked the same platform account at the same moment.
            await self._session.rollback()
            raise CustomException(
                message="This account was just connected to another Clipnera user.",
                code="ACCOUNT_LINKED_ELSEWHERE",
                status_code=409,
            ) from exc
        return account

    @staticmethod
    def _account_limit(ent: Entitlements) -> CustomException:
        return CustomException(
            message=f"Your plan allows {ent.social_max_accounts} connected account(s). Disconnect one or upgrade.",
            code="ACCOUNT_LIMIT_REACHED",
            status_code=403,
            extra={"limit": ent.social_max_accounts},
        )

    @staticmethod
    async def _revoke_quietly(provider: PlatformProvider, tokens: TokenSet) -> None:
        try:
            await provider.revoke(tokens)
        except PlatformError as exc:
            log.warning(f"Could not revoke rejected {provider.label} grant: {exc.code}")

    # -- disconnect -------------------------------------------------------------

    async def disconnect(
        self, account: ConnectedAccount, actor_type: str, actor_user_id: str | None
    ) -> int:
        """Stop using an account now; the worker revokes and deletes its tokens.
        Returns how many scheduled posts were cancelled. Commits."""
        if account.status == AccountStatus.DISCONNECTED:
            return 0
        reason = "Account disconnected" if actor_type == "user" else "Account disconnected by an administrator"
        cancelled = await self._repo.cancel_pending_posts(account.id, reason)
        account.status = AccountStatus.DISCONNECTING
        account.status_reason = reason
        audit.record(
            self._session,
            AuditAction.DISCONNECTED if actor_type == "user" else AuditAction.FORCE_DISCONNECTED,
            actor_type,
            actor_user_id=actor_user_id,
            user_id=account.user_id,
            account_id=account.id,
            platform=account.platform,
            detail={"cancelled_posts": len(cancelled)},
        )
        await self._session.commit()
        return len(cancelled)

    async def disconnect_for_user(self, user_id: str, account_id: str) -> int:
        account = await self._repo.get_account(account_id, user_id)
        if not account:
            raise not_found()
        return await self.disconnect(account, "user", user_id)

    async def finalize_disconnect(self, account: ConnectedAccount) -> None:
        """Revoke the grant (best effort), delete tokens, forget the profile. Commits."""
        store = TokenStore(self._session)
        try:
            tokens = await store.load(account.id)
        except Exception as exc:  # undecryptable tokens are deleted all the same
            log.warning(f"Could not read tokens to revoke account={account.id}: {type(exc).__name__}")
            tokens = None
        if tokens:
            async with get_provider(account.platform) as provider:
                await self._revoke_quietly(provider, tokens)
        await store.delete(account.id)
        clear_profile(account, account.status_reason or "Account disconnected")
        await self._session.commit()

    async def platform_removed(self, platform: SocialPlatform, platform_user_id: str, delete_data: bool) -> int:
        """A platform told us the user removed our app (or asked for deletion).
        No revoke call: the grant is already gone. Returns accounts affected. Commits."""
        account = await self._repo.find_live(platform, platform_user_id)
        if not account:
            return 0
        await TokenStore(self._session).delete(account.id)
        cancelled = await self._repo.cancel_pending_posts(account.id, "Access was removed on the platform")
        clear_profile(account, "Access was removed on the platform")
        if delete_data:
            await self._session.execute(delete(ScheduledPost).where(ScheduledPost.account_id == account.id))
            # Drop the platform's id too; nothing links this row to the person any more.
            account.platform_user_id = f"deleted:{uuid4()}"
        audit.record(
            self._session,
            AuditAction.DATA_DELETED if delete_data else AuditAction.DEAUTHORIZED,
            "webhook",
            user_id=account.user_id,
            account_id=account.id,
            platform=platform,
            detail={"cancelled_posts": len(cancelled)},
        )
        await self._session.commit()
        return 1

    async def admin_force_disconnect(self, account_id: str, admin_id: str) -> DisconnectPreviewResponse:
        account = await self._repo.get_account_by_id(account_id)
        if not account:
            raise not_found()
        cancelled = await self.disconnect(account, "admin", admin_id)
        log.info(f"Admin {admin_id} force-disconnected social account={account_id}")
        return DisconnectPreviewResponse(account_id=account_id, pending_posts=cancelled)

    # -- platform callbacks --------------------------------------------------

    @staticmethod
    def _meta_payload(signed_request: str) -> dict:
        payload = parse_meta_signed_request(signed_request)
        if not payload or not payload.get("user_id"):
            raise CustomException(message="Invalid signature", code="INVALID_SIGNATURE", status_code=400)
        return payload

    async def meta_deauthorize(self, signed_request: str) -> None:
        payload = self._meta_payload(signed_request)
        await self.platform_removed(SocialPlatform.INSTAGRAM, str(payload["user_id"]), delete_data=False)

    async def meta_data_deletion(self, signed_request: str) -> dict:
        """Delete what we hold for the Meta user and return the status URL Meta
        shows them, in Meta's response shape."""
        payload = self._meta_payload(signed_request)
        deleted = await self.platform_removed(SocialPlatform.INSTAGRAM, str(payload["user_id"]), delete_data=True)
        code = secrets.token_hex(8)
        self._session.add(
            DataDeletionRequest(
                confirmation_code=code, platform=SocialPlatform.INSTAGRAM, accounts_deleted=deleted, completed=True
            )
        )
        await self._session.commit()
        status_url = f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/data-deletion?code={code}"
        return {"url": status_url, "confirmation_code": code}

    async def tiktok_event(self, signature: str | None, body: bytes) -> None:
        if not verify_tiktok_signature(signature, body):
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
            await self.platform_removed(SocialPlatform.TIKTOK, str(event["user_openid"]), delete_data=reason == 2)

    async def deletion_status(self, code: str) -> DeletionStatusResponse:
        record = await self._session.get(DataDeletionRequest, code[:32])
        if not record:
            raise not_found("Deletion request")
        return DeletionStatusResponse(
            confirmation_code=record.confirmation_code,
            platform=record.platform.value,
            completed=record.completed,
            accounts_deleted=record.accounts_deleted,
            requested_at=record.created_at,
        )

    async def purge_user(self, user_id: str) -> None:
        """Revoke and delete every connected account of a user being deleted.
        Call before deleting the user row; the FK cascade then removes the rest."""
        for account_id in await self._repo.user_account_ids(user_id):
            account = await self._repo.get_account_by_id(account_id)
            if account:
                await self._repo.cancel_pending_posts(account.id, "Account deleted")
                await self.finalize_disconnect(account)


class SocialAdminService:
    """Platform-wide publishing health for the admin panel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SocialRepository(session)

    async def overview(self, days: int) -> AdminSocialOverviewResponse:
        accounts: dict[SocialPlatform, dict[str, int]] = {p: {} for p in SocialPlatform}
        for platform, status, count in await self._repo.account_counts():
            accounts[platform][status.value] = count
        posts: dict[SocialPlatform, dict[str, int]] = {p: {} for p in SocialPlatform}
        for platform, status, count in await self._repo.post_counts(datetime.utcnow() - timedelta(days=days)):
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
            for post, account, user in await self._repo.recent_failures(25)
        ]
        return AdminSocialOverviewResponse(
            window_days=days, platforms=stats, quota=await quota.usage(self._session), recent_failures=failures
        )

    async def accounts(self, query: str | None, limit: int, offset: int) -> AdminAccountListResponse:
        rows = await self._repo.admin_accounts((query or "").strip() or None, limit, offset)
        return AdminAccountListResponse(
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
