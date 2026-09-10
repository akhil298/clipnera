from __future__ import annotations

from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_viral_shorts: int
    manual_hours_saved: float
    avg_virality_score: float
    best_post_window: str
