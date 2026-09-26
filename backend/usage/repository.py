"""Aggregate queries over the AI usage ledger."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from usage.model import LlmUsage

_TOTALS = (
    func.count(LlmUsage.id).label("calls"),
    func.coalesce(func.sum(LlmUsage.input_tokens), 0).label("input_tokens"),
    func.coalesce(func.sum(LlmUsage.output_tokens), 0).label("output_tokens"),
    func.coalesce(func.sum(LlmUsage.cache_read_tokens), 0).label("cache_read_tokens"),
    func.coalesce(func.sum(LlmUsage.cache_write_tokens), 0).label("cache_write_tokens"),
    func.coalesce(func.sum(LlmUsage.audio_seconds), 0.0).label("audio_seconds"),
    func.coalesce(func.sum(LlmUsage.cost_usd), 0.0).label("cost_usd"),
)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def project_steps(self, project_id: str) -> list:
        result = await self._session.execute(
            select(LlmUsage.step, LlmUsage.provider, LlmUsage.model, *_TOTALS)
            .where(LlmUsage.project_id == project_id)
            .group_by(LlmUsage.step, LlmUsage.provider, LlmUsage.model)
            .order_by(func.min(LlmUsage.created_at))
        )
        return list(result.all())

    async def project_costs(self, project_ids: list[str]) -> dict[str, float]:
        if not project_ids:
            return {}
        result = await self._session.execute(
            select(LlmUsage.project_id, func.sum(LlmUsage.cost_usd))
            .where(LlmUsage.project_id.in_(project_ids))
            .group_by(LlmUsage.project_id)
        )
        return {project_id: float(cost or 0.0) for project_id, cost in result.all()}

    def _since(self, days: int) -> datetime:
        return datetime.utcnow() - timedelta(days=days)

    async def totals_since(self, days: int):
        result = await self._session.execute(
            select(*_TOTALS).where(LlmUsage.created_at >= self._since(days))
        )
        return result.one()

    async def by_day(self, days: int) -> list:
        day = cast(LlmUsage.created_at, Date)
        result = await self._session.execute(
            select(day.label("day"), func.count(LlmUsage.id), func.sum(LlmUsage.cost_usd))
            .where(LlmUsage.created_at >= self._since(days))
            .group_by(day)
            .order_by(day)
        )
        return list(result.all())

    async def by_model(self, days: int) -> list:
        result = await self._session.execute(
            select(LlmUsage.provider, LlmUsage.model, *_TOTALS)
            .where(LlmUsage.created_at >= self._since(days))
            .group_by(LlmUsage.provider, LlmUsage.model)
            .order_by(func.sum(LlmUsage.cost_usd).desc())
        )
        return list(result.all())

    async def project_costs_with_length(self, days: int) -> list:
        """(project cost, source seconds, used Claude) for every project with AI calls in the window."""
        from clip.model import VideoProject

        result = await self._session.execute(
            select(
                func.sum(LlmUsage.cost_usd),
                func.max(VideoProject.duration_seconds),
                func.bool_or(LlmUsage.provider == "anthropic"),
            )
            .join(VideoProject, VideoProject.id == LlmUsage.project_id)
            .where(LlmUsage.created_at >= self._since(days))
            .group_by(LlmUsage.project_id)
        )
        return list(result.all())

    async def top_projects(self, days: int, limit: int) -> list:
        cost = func.sum(LlmUsage.cost_usd)
        result = await self._session.execute(
            select(LlmUsage.project_id, func.max(LlmUsage.user_id), func.count(LlmUsage.id), cost)
            .where(LlmUsage.created_at >= self._since(days), LlmUsage.project_id.is_not(None))
            .group_by(LlmUsage.project_id)
            .order_by(cost.desc())
            .limit(limit)
        )
        return list(result.all())
