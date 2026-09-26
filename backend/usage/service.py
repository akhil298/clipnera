from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from clip.repository import ClipRepository
from core.exceptions import CustomException
from usage.repository import UsageRepository
from usage.schema import (
    AdminUsageSummary,
    DailyUsage,
    ModelUsage,
    ProjectUsage,
    StepUsage,
    TopProjectUsage,
)


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UsageRepository(session)
        self._clips = ClipRepository(session)

    async def project_usage(self, project_id: str, user_id: str) -> ProjectUsage:
        if await self._clips.get_project(project_id, user_id) is None:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)
        steps = [
            StepUsage(
                step=row.step, provider=row.provider, model=row.model, calls=row.calls,
                input_tokens=row.input_tokens, output_tokens=row.output_tokens,
                cache_read_tokens=row.cache_read_tokens, cache_write_tokens=row.cache_write_tokens,
                audio_seconds=round(float(row.audio_seconds), 1), cost_usd=round(float(row.cost_usd), 6),
            )
            for row in await self._repo.project_steps(project_id)
        ]
        return ProjectUsage(
            project_id=project_id,
            calls=sum(s.calls for s in steps),
            input_tokens=sum(s.input_tokens for s in steps),
            output_tokens=sum(s.output_tokens for s in steps),
            cache_read_tokens=sum(s.cache_read_tokens for s in steps),
            cache_write_tokens=sum(s.cache_write_tokens for s in steps),
            audio_seconds=round(sum(s.audio_seconds for s in steps), 1),
            cost_usd=round(sum(s.cost_usd for s in steps), 6),
            by_step=steps,
        )

    async def admin_summary(self, days: int, top: int = 20) -> AdminUsageSummary:
        totals = await self._repo.totals_since(days)
        return AdminUsageSummary(
            days=days,
            calls=totals.calls,
            cost_usd=round(float(totals.cost_usd), 4),
            by_day=[
                DailyUsage(day=day.isoformat(), calls=calls, cost_usd=round(float(cost or 0), 4))
                for day, calls, cost in await self._repo.by_day(days)
            ],
            by_model=[
                ModelUsage(
                    provider=row.provider, model=row.model, calls=row.calls,
                    input_tokens=row.input_tokens, output_tokens=row.output_tokens,
                    cost_usd=round(float(row.cost_usd), 4),
                )
                for row in await self._repo.by_model(days)
            ],
            top_projects=[
                TopProjectUsage(project_id=project_id, user_id=user_id, calls=calls, cost_usd=round(float(cost or 0), 4))
                for project_id, user_id, calls, cost in await self._repo.top_projects(days, top)
            ],
        )
