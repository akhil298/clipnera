"""The publisher worker: a separate process from the API.

    cd backend && venv/bin/python -m social.worker

Each tick it claims due posts (row locks, so several workers can run side by
side), publishes them, and runs the housekeeping sweeps on their own
intervals: finishing disconnects, renewing tokens, refreshing follower counts,
re-encrypting tokens after a key rotation and purging old OAuth states.

It is the only process that decrypts platform tokens for publishing.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import time
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from core.database import AsyncSessionLocal
from core.logging_config import get_logger, setup_logging
from feature_flags.registry import SOCIAL_PUBLISHING, social_platform_flag
from feature_flags.service import FeatureFlagService
from social.credentials import fresh_tokens
from social.model import AccountStatus, ConnectedAccount
from social.oauth_state import OAuthStateStore
from social.providers import get_provider
from social.providers.base import PlatformError
from social.publisher import Publisher
from social.repository import SocialRepository
from social.service import SocialAccountService
from social.tokens import TokenStore

log = get_logger(__name__)

POLL_SECONDS = 15
BATCH_SIZE = 4
# A claim older than this without a heartbeat belongs to a run that died.
CLAIM_LEASE = timedelta(minutes=15)
# Refresh every token expiring within this window; providers decide exactly when.
REFRESH_HORIZON = timedelta(days=11)
PROFILE_MAX_AGE = timedelta(hours=24)


async def publish_due() -> int:
    async with AsyncSessionLocal() as session:
        claimed = await SocialRepository(session).claim_due(datetime.utcnow(), BATCH_SIZE, CLAIM_LEASE)
    await asyncio.gather(*(_publish_one(item.post_id) for item in claimed))
    return len(claimed)


async def _publish_one(post_id: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await Publisher(session).process(post_id)
        except Exception as exc:  # one broken post must not stop the others
            log.error(f"Publisher crashed on post={post_id}: {type(exc).__name__}", exc_info=True)


async def finish_disconnects() -> int:
    async with AsyncSessionLocal() as session:
        accounts = await SocialRepository(session).accounts_with_status(AccountStatus.DISCONNECTING, 20)
        service = SocialAccountService(session)
        for account in accounts:
            await service.finalize_disconnect(account)
    return len(accounts)


async def refresh_tokens() -> int:
    refreshed = 0
    async with AsyncSessionLocal() as session:
        account_ids = await TokenStore(session).due_for_refresh(datetime.utcnow() + REFRESH_HORIZON, 50)
        for account_id in account_ids:
            account = await session.get(ConnectedAccount, account_id)
            if account is None or account.status != AccountStatus.ACTIVE:
                continue
            async with get_provider(account.platform) as provider:
                try:
                    await fresh_tokens(session, account, provider)
                    refreshed += 1
                except PlatformError as exc:
                    log.info(f"Token refresh for account={account_id} did not succeed: {exc.code}")
    return refreshed


async def refresh_profiles() -> int:
    """Follower counts and handles, at most daily per account, never on page loads."""
    updated = 0
    async with AsyncSessionLocal() as session:
        flags = await FeatureFlagService(session).effective()
        if not flags[SOCIAL_PUBLISHING]:
            return 0
        stale = datetime.utcnow() - PROFILE_MAX_AGE
        for account in await SocialRepository(session).accounts_needing_profile_refresh(stale, 20):
            if not flags[social_platform_flag(account.platform.value)]:
                continue
            async with get_provider(account.platform) as provider:
                try:
                    tokens = await fresh_tokens(session, account, provider)
                    profile = await provider.fetch_profile(tokens)
                except PlatformError as exc:
                    log.info(f"Profile refresh for account={account.id} failed: {exc.code}")
                    # Try again tomorrow rather than on every tick.
                    account.follower_count_updated_at = datetime.utcnow()
                    await session.commit()
                    continue
            account.handle = profile.handle
            account.display_name = profile.display_name
            account.avatar_url = profile.avatar_url
            account.follower_count = profile.follower_count
            account.follower_count_updated_at = datetime.utcnow()
            await session.commit()
            updated += 1
    return updated


async def rotate_keys() -> int:
    """Re-encrypt tokens still under an old key version, a batch at a time."""
    async with AsyncSessionLocal() as session:
        store = TokenStore(session)
        account_ids = await store.stale_key_accounts(100)
        for account_id in account_ids:
            tokens = await store.load(account_id)
            if tokens:
                await store.save(account_id, tokens)
        await session.commit()
    return len(account_ids)


async def purge_states() -> int:
    async with AsyncSessionLocal() as session:
        return await OAuthStateStore(session).purge()


class Periodic:
    """Runs a job when its interval has passed; failures are logged, never raised."""

    def __init__(self, name: str, interval: timedelta, job: Callable[[], Awaitable[int]]) -> None:
        self.name = name
        self.interval = interval.total_seconds()
        self.job = job
        self._next = 0.0

    async def maybe_run(self) -> None:
        now = time.monotonic()
        if now < self._next:
            return
        self._next = now + self.interval
        try:
            count = await self.job()
            if count:
                log.info(f"Worker {self.name}: {count}")
        except Exception as exc:
            log.error(f"Worker job {self.name} failed: {type(exc).__name__}", exc_info=True)


JOBS = (
    Periodic("publish", timedelta(seconds=0), publish_due),
    Periodic("disconnects", timedelta(seconds=0), finish_disconnects),
    Periodic("token_refresh", timedelta(minutes=5), refresh_tokens),
    Periodic("profiles", timedelta(minutes=30), refresh_profiles),
    Periodic("key_rotation", timedelta(hours=1), rotate_keys),
    Periodic("oauth_states", timedelta(hours=1), purge_states),
)


async def run(once: bool = False) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("Social publisher worker started")
    while not stop.is_set():
        for job in JOBS:
            await job.maybe_run()
        if once:
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass
    log.info("Social publisher worker stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clipnera social publisher worker")
    parser.add_argument("--once", action="store_true", help="run every job once and exit")
    args = parser.parse_args()
    setup_logging()
    # Fail at startup, not on the first post, when the key ring is missing.
    from core.crypto import get_token_cipher

    get_token_cipher()
    asyncio.run(run(once=args.once))
