"""Background sweep for referrals and bonus credits, run inside the API.

Every few minutes it re-checks open referrals (deadlines that passed,
reminders due, rewards an event missed) and, hourly, removes expired bonus
credits. Requests already do both for the users they serve, so this only keeps
idle accounts and the referrer's view up to date. Safe with several API
processes: each referral is checked under a row lock.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from core.logging_config import get_logger
from referral.service import sweep_open_referrals
from subscription.jobs import expire_all_bonus_credits

log = get_logger(__name__)

REFERRAL_SWEEP_SECONDS = 5 * 60
BONUS_EXPIRY_SECONDS = 60 * 60


async def run(stop: asyncio.Event) -> None:
    next_expiry = 0.0
    while not stop.is_set():
        try:
            checked = await sweep_open_referrals()
            if checked:
                log.info(f"Referral sweep: checked={checked}")
            if time.monotonic() >= next_expiry:
                next_expiry = time.monotonic() + BONUS_EXPIRY_SECONDS
                expired = await expire_all_bonus_credits()
                if expired:
                    log.info(f"Bonus credits expired: {expired}")
        except Exception as exc:
            log.error(f"Referral sweep failed: {type(exc).__name__}", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=REFERRAL_SWEEP_SECONDS)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def running_in_background() -> AsyncIterator[None]:
    stop = asyncio.Event()
    task = asyncio.create_task(run(stop))
    try:
        yield
    finally:
        stop.set()
        await task
