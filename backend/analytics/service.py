from __future__ import annotations

from core.database import AsyncSessionLocal
from analytics.repository import AnalyticsRepository
from core.logging_config import get_logger

log = get_logger(__name__)


class AnalyticsService:
    def __init__(self) -> None:
        pass

    async def get_dashboard_stats(self, user_id: str) -> dict:
        async with AsyncSessionLocal() as session:
            repo = AnalyticsRepository(session)
            clip_stats = await repo.get_user_clip_stats(user_id)
            best_post_window = await repo.get_best_post_window(user_id)

            total_clips = clip_stats["total_clips"]
            avg_score = clip_stats["avg_score"]
            total_duration = clip_stats["total_duration_seconds"]

            manual_hours_saved = (total_duration * 8) / 3600.0

            return {
                "total_viral_shorts": total_clips,
                "manual_hours_saved": round(manual_hours_saved, 1),
                "avg_virality_score": round(avg_score, 1),
                "best_post_window": best_post_window,
            }
