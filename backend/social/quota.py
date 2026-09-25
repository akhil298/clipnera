"""App-wide platform quotas the worker must respect before calling out.

YouTube gives the whole API project 100 ``videos.insert`` calls a day (reset
at midnight Pacific) until a quota extension is granted. X bills every post,
so publishing to X stops for the month once X_MONTHLY_BUDGET_USD is spent.
Per-account limits (Instagram's 100 posts a day, TikTok's daily cap) are
checked by the platforms themselves and surface as QUOTA errors.

Each reservation is one conditional upsert, so concurrent workers cannot
overshoot a limit together.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from social.model import PlatformQuotaUsage, SocialPlatform
from social.providers.base import ErrorKind, PlatformError
from social.providers.x import POST_COST_MICROS
from social.providers.youtube import until_pacific_midnight

APP_SCOPE = "app"
YOUTUBE_DAILY_UPLOADS = 100
_UTC = ZoneInfo("UTC")


def youtube_window(now: datetime) -> date:
    return now.replace(tzinfo=_UTC).astimezone(ZoneInfo("America/Los_Angeles")).date()


def month_window(now: datetime) -> date:
    return now.date().replace(day=1)


def until_next_month(now: datetime) -> timedelta:
    first = month_window(now)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return datetime.combine(next_month, datetime.min.time()) - now


async def _add(
    session: AsyncSession,
    platform: SocialPlatform,
    window: date,
    count_limit: int | None = None,
    cost_micros: int = 0,
    cost_limit_micros: int | None = None,
) -> bool:
    """Add one call (and its cost) to the window unless that passes a limit. Commits."""
    now = datetime.utcnow()
    stmt = pg_insert(PlatformQuotaUsage).values(
        id=str(uuid4()),
        platform=platform,
        scope_key=APP_SCOPE,
        window_start=window,
        count=1,
        cost_micros=cost_micros,
        updated_at=now,
    )
    new_count = PlatformQuotaUsage.count + 1
    new_cost = PlatformQuotaUsage.cost_micros + cost_micros
    conditions = []
    if count_limit is not None:
        conditions.append(new_count <= count_limit)
    if cost_limit_micros is not None:
        conditions.append(new_cost <= cost_limit_micros)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_platform_quota_usage_window",
        set_={"count": new_count, "cost_micros": new_cost, "updated_at": now},
        where=and_(*conditions) if conditions else None,
    ).returning(PlatformQuotaUsage.id)
    reserved = (await session.execute(stmt)).first() is not None
    await session.commit()
    return reserved


async def reserve(session: AsyncSession, platform: SocialPlatform, now: datetime | None = None) -> None:
    """Count one publish against the app-wide quota, or raise PlatformError(QUOTA)."""
    now = now or datetime.utcnow()
    if platform == SocialPlatform.YOUTUBE:
        if not await _add(session, platform, youtube_window(now), count_limit=YOUTUBE_DAILY_UPLOADS):
            raise PlatformError(
                ErrorKind.QUOTA,
                "app_daily_quota",
                "Clipnera's daily YouTube upload allowance is used up. The post will go out after it resets.",
                until_pacific_midnight(now),
            )
    elif platform == SocialPlatform.X:
        budget = int(get_settings().X_MONTHLY_BUDGET_USD * 1_000_000)
        if not await _add(
            session, platform, month_window(now), cost_micros=POST_COST_MICROS, cost_limit_micros=budget
        ):
            raise PlatformError(
                ErrorKind.PERMANENT,
                "app_monthly_budget",
                "Posting to X is paused for the rest of the month. Please try again next month.",
            )


async def usage(session: AsyncSession, now: datetime | None = None) -> dict[str, dict[str, float]]:
    """Current app-wide usage for the admin panel."""
    now = now or datetime.utcnow()
    result = await session.execute(
        select(PlatformQuotaUsage).where(
            PlatformQuotaUsage.scope_key == APP_SCOPE,
            PlatformQuotaUsage.window_start.in_([youtube_window(now), month_window(now)]),
        )
    )
    rows = {(row.platform, row.window_start): row for row in result.scalars().all()}
    youtube = rows.get((SocialPlatform.YOUTUBE, youtube_window(now)))
    x = rows.get((SocialPlatform.X, month_window(now)))
    return {
        "youtube": {"used": youtube.count if youtube else 0, "limit": YOUTUBE_DAILY_UPLOADS},
        "x": {
            "used": x.count if x else 0,
            "spent_usd": (x.cost_micros if x else 0) / 1_000_000,
            "budget_usd": get_settings().X_MONTHLY_BUDGET_USD,
        },
    }
