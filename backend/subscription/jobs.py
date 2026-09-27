"""Daily plan and data-retention maintenance. Run once a day, e.g. from cron:

    0 3 * * * cd /path/to/backend && venv/bin/python -m subscription.jobs

Nothing depends on it for correctness: every request already treats an ended
period as Free and resets credits when a new cycle has started. This keeps
stored statuses and balances current for users who have not been active, and
is safe to run more than once a day.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from auth.repository import UserRepository as AuthRepository
from core.database import AsyncSessionLocal
from core.logging_config import get_logger, setup_logging
from subscription.repository import UserSubscriptionRepository
from subscription.service import SubscriptionService
from user.repository import UserRepository

log = get_logger(__name__)

BATCH_SIZE = 500

# How long a sign-in's IP address and browser are kept (see the privacy policy).
LOGIN_CLIENT_RETENTION_DAYS = 90


async def expire_lapsed_subscriptions() -> int:
    async with AsyncSessionLocal() as session:
        return await UserSubscriptionRepository(session).expire_lapsed()


async def refresh_all_credits(batch_size: int = BATCH_SIZE) -> int:
    """Apply any due credit reset for every user. Idempotent per cycle."""
    refreshed = 0
    last_id: str | None = None
    while True:
        async with AsyncSessionLocal() as session:
            user_ids = await UserRepository(session).list_ids_after(last_id, batch_size)
            service = SubscriptionService.for_session(session)
            for user_id in user_ids:
                try:
                    refreshed += await service.refresh_credits(user_id)
                except Exception as exc:
                    await session.rollback()
                    log.error(f"Credit reset failed for user={user_id}: {exc}")
        if len(user_ids) < batch_size:
            return refreshed
        last_id = user_ids[-1]


async def forget_old_login_clients() -> int:
    cutoff = datetime.utcnow() - timedelta(days=LOGIN_CLIENT_RETENTION_DAYS)
    async with AsyncSessionLocal() as session:
        return await AuthRepository(session).forget_login_clients_before(cutoff)


async def run_daily_maintenance() -> None:
    expired = await expire_lapsed_subscriptions()
    refreshed = await refresh_all_credits()
    forgotten = await forget_old_login_clients()
    log.info(f"Daily maintenance done: expired={expired} credit_resets={refreshed} login_clients_forgotten={forgotten}")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_daily_maintenance())
