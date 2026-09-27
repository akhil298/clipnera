"""Marks each user active for the UTC day of their signed-in requests.

Written at most once per user per day per process: the first request of the day
inserts the row and later ones are answered from memory.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert

from auth.model import UserActivityDay
from core.database import AsyncSessionLocal
from core.logging_config import get_logger

log = get_logger(__name__)

_recorded_day: date | None = None
_recorded_users: set[str] = set()


async def record_activity(user_id: str) -> None:
    """Mark ``user_id`` active today. Never raises: analytics must not fail a request."""
    global _recorded_day
    today = datetime.utcnow().date()
    if today != _recorded_day:
        _recorded_day = today
        _recorded_users.clear()
    if user_id in _recorded_users:
        return
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                insert(UserActivityDay).values(user_id=user_id, day=today).on_conflict_do_nothing()
            )
            await session.commit()
        _recorded_users.add(user_id)
    except Exception as exc:
        log.warning(f"Could not record activity for user={user_id}: {type(exc).__name__}: {exc}")
