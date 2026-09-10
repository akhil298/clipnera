from fastapi import APIRouter

from auth.dependencies import CurrentUserDep
from analytics.service import AnalyticsService
from analytics.schema import DashboardStatsResponse
from core.logging_config import get_logger

log = get_logger(__name__)

analytics = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics.get("/dashboard")
async def get_dashboard_stats(user: CurrentUserDep):
    service = AnalyticsService()
    stats = await service.get_dashboard_stats(user["user_id"])
    return stats
