"""Daily plan maintenance. Run once a day, e.g. from cron:

    0 3 * * * cd /path/to/backend && venv/bin/python -m subscription.jobs

Nothing depends on it for correctness: every request already treats an ended
period as Free and resets credits when a new cycle has started. This keeps
stored statuses and balances current for users who have not been active, and
is safe to run more than once a day.
"""

from __future__ import annotations

import asyncio

from core.database import AsyncSessionLocal
from core.logging_config import get_logger, setup_logging
from subscription.repository import UserSubscriptionRepository
from subscription.service import SubscriptionService
from user.repository import UserRepository

log = get_logger(__name__)

BATCH_SIZE = 500


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


async def run_daily_maintenance() -> None:
    expired = await expire_lapsed_subscriptions()
    refreshed = await refresh_all_credits()
    log.info(f"Plan maintenance done: expired={expired} credit_resets={refreshed}")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_daily_maintenance())
