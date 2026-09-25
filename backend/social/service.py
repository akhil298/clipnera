"""Connecting, listing and disconnecting social accounts."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import CustomException
from core.logging_config import get_logger
from feature_flags.registry import SOCIAL_PUBLISHING, social_platform_flag
from feature_flags.service import FeatureFlagService
from social import audit
from social.credentials import fresh_tokens
from social.model import AccountStatus, AuditAction, ConnectedAccount, ScheduledPost, SocialPlatform
from social.oauth_state import OAuthStateStore
from social.providers import get_provider
from social.providers.base import ErrorKind, PkcePair, PlatformError, PlatformProvider, Profile, TokenSet
from social.repository import SocialRepository
from social.schema import (
    ConnectedAccountResponse,
    ConnectionsResponse,
    ConnectStartResponse,
    DisconnectPreviewResponse,
    PlatformInfo,
    TikTokCreatorInfoResponse,
)
from social.tokens import TokenStore
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

    async def purge_user(self, user_id: str) -> None:
        """Revoke and delete every connected account of a user being deleted.
        Call before deleting the user row; the FK cascade then removes the rest."""
        for account_id in await self._repo.user_account_ids(user_id):
            account = await self._repo.get_account_by_id(account_id)
            if account:
                await self._repo.cancel_pending_posts(account.id, "Account deleted")
                await self.finalize_disconnect(account)
