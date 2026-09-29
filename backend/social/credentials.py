"""Getting a usable access token for an account, refreshing when due.

Shared by the publisher worker and the one API read that TikTok requires to be
live (creator info). A revoked or expired grant moves the account to
NEEDS_RECONNECT and emails the user once; transient refresh failures are
counted and give up after MAX_REFRESH_FAILURES, so nothing retries forever.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import get_logger
from social import audit, notify
from social.model import AccountStatus, AuditAction, ConnectedAccount
from social.providers.base import ErrorKind, PlatformError, PlatformProvider, TokenSet
from social.tokens import TokenStore

log = get_logger(__name__)

MAX_REFRESH_FAILURES = 5


def reconnect_required(label: str) -> PlatformError:
    return PlatformError(ErrorKind.AUTH, "needs_reconnect", f"{label} access has expired. Reconnect the account.")


async def mark_needs_reconnect(session: AsyncSession, account: ConnectedAccount, reason: str) -> None:
    """Flag the account and tell the user, once per transition. Commits."""
    if account.status != AccountStatus.ACTIVE:
        return
    account.status = AccountStatus.NEEDS_RECONNECT
    account.status_reason = reason[:500]
    audit.record(
        session,
        AuditAction.NEEDS_RECONNECT,
        "system",
        user_id=account.user_id,
        account_id=account.id,
        platform=account.platform,
        detail={"reason": reason[:200]},
    )
    await session.commit()
    await notify.account_needs_reconnect(session, account)


async def fresh_tokens(
    session: AsyncSession, account: ConnectedAccount, provider: PlatformProvider, force: bool = False
) -> TokenSet:
    """Decrypted tokens for ``account``, refreshed first when close to expiry."""
    expired = account.expires_at is not None and account.expires_at <= datetime.utcnow()
    if account.status != AccountStatus.ACTIVE or expired:
        raise reconnect_required(provider.label)
    store = TokenStore(session)
    tokens = await store.load(account.id)
    if tokens is None:
        raise reconnect_required(provider.label)
    if not force and not provider.refresh_due(tokens.expires_at, datetime.utcnow()):
        return tokens
    try:
        refreshed = await provider.refresh(tokens)
    except PlatformError as exc:
        if exc.kind == ErrorKind.AUTH:
            await store.delete(account.id)
            await mark_needs_reconnect(session, account, exc.message)
            raise
        failures = await store.record_refresh_failure(account.id)
        log.warning(f"Token refresh failed for account={account.id} ({exc.code}), failure {failures}")
        if failures >= MAX_REFRESH_FAILURES:
            await mark_needs_reconnect(session, account, "Could not renew access after several attempts.")
            raise reconnect_required(provider.label) from exc
        # The current token may still be valid for a while; use it if so.
        if tokens.expires_at and tokens.expires_at > datetime.utcnow():
            return tokens
        raise
    await store.save(account.id, refreshed)
    await session.commit()
    return refreshed
