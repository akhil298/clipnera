from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from clip_generation.model import GeneratedClip
from clip.model import VideoProject
from pipeline.model import PipelineState, PipelineStepLog
from core.logging_config import get_logger

log = get_logger(__name__)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_clip_stats(self, user_id: str) -> dict[str, Any]:
        stmt = select(
            func.count(GeneratedClip.id).label("total_clips"),
            func.avg(GeneratedClip.score).label("avg_score"),
            func.sum(GeneratedClip.duration_seconds).label("total_duration_seconds"),
        ).where(GeneratedClip.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        if not row:
            return {
                "total_clips": 0,
                "avg_score": 0.0,
                "total_duration_seconds": 0.0,
            }
        return {
            "total_clips": row["total_clips"] or 0,
            "avg_score": float(row["avg_score"] or 0.0),
            "total_duration_seconds": float(row["total_duration_seconds"] or 0.0),
        }

    async def get_best_post_window(self, user_id: str) -> str:
        stmt = (
            select(
                func.extract("hour", GeneratedClip.created_at).label("hour"),
                func.count(GeneratedClip.id).label("count"),
            )
            .where(GeneratedClip.user_id == user_id)
            .group_by(func.extract("hour", GeneratedClip.created_at))
            .order_by(func.count(GeneratedClip.id).desc())
        )
        result = await self._session.execute(stmt)
        row = result.mappings().first()
        if not row:
            return "7:00 PM"
        hour = int(row["hour"])
        return self._format_hour(hour)

    async def get_pipeline_processing_seconds(self, user_id: str) -> float:
        stmt = (
            select(func.sum(
                func.extract("epoch", PipelineStepLog.finished_at - PipelineStepLog.started_at)
            ))
            .join(PipelineState, PipelineStepLog.pipeline_id == PipelineState.id)
            .join(VideoProject, PipelineState.project_id == VideoProject.id)
            .where(
                and_(
                    VideoProject.user_id == user_id,
                    PipelineStepLog.started_at.is_not(None),
                    PipelineStepLog.finished_at.is_not(None),
                )
            )
        )
        result = await self._session.execute(stmt)
        total_seconds = result.scalar_one_or_none()
        return float(total_seconds or 0.0)

    def _format_hour(self, hour: int) -> str:
        if hour == 0:
            return "12:00 AM"
        if hour < 12:
            return f"{hour}:00 AM"
        if hour == 12:
            return "12:00 PM"
        return f"{hour - 12}:00 PM"
