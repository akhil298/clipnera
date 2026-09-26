from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clip_generation.model import GeneratedClip
from feedback.model import ClipEvent, ClipEventKind


class ClipEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, clip_ids: list[str], user_id: str | None, kind: ClipEventKind) -> None:
        self._session.add_all(ClipEvent(clip_id=clip_id, user_id=user_id, kind=kind.value) for clip_id in clip_ids)
        await self._session.commit()

    async def quality_by_version(self, days: int) -> list:
        """Per director version: clips made, and how many were exported, edited, published."""
        since = datetime.utcnow() - timedelta(days=days)

        def clips_with(kind: ClipEventKind):
            return func.count(distinct(case((ClipEvent.kind == kind.value, ClipEvent.clip_id))))

        version = func.coalesce(GeneratedClip.director_version, "legacy")
        result = await self._session.execute(
            select(
                version.label("version"),
                func.count(distinct(GeneratedClip.id)).label("clips"),
                clips_with(ClipEventKind.EXPORTED).label("exported"),
                clips_with(ClipEventKind.EDITED).label("edited"),
                clips_with(ClipEventKind.PUBLISHED).label("published"),
            )
            .select_from(GeneratedClip)
            .outerjoin(ClipEvent, ClipEvent.clip_id == GeneratedClip.id)
            .where(GeneratedClip.created_at >= since)
            .group_by(version)
            .order_by(version)
        )
        return list(result.all())
