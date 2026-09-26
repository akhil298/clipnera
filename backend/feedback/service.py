from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from feedback.model import ClipEventKind
from feedback.repository import ClipEventRepository
from feedback.schema import ClipQualityReport, VersionQuality

log = get_logger(__name__)


async def record_clip_event(clip_ids: list[str], user_id: str | None, kind: ClipEventKind) -> None:
    """Log what a user did with clips. Never raises: a missed label must not fail the action."""
    if not clip_ids:
        return
    try:
        async with AsyncSessionLocal() as session:
            await ClipEventRepository(session).add(clip_ids, user_id, kind)
    except Exception as exc:
        log.warning("Could not record clip event %s for %d clip(s): %s", kind.value, len(clip_ids), exc)


class ClipQualityService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ClipEventRepository(session)

    async def report(self, days: int) -> ClipQualityReport:
        rows = await self._repo.quality_by_version(days)
        return ClipQualityReport(
            days=days,
            versions=[
                VersionQuality(
                    director_version=row.version,
                    clips=row.clips,
                    exported_share=round(row.exported / row.clips, 4) if row.clips else 0.0,
                    edited_share=round(row.edited / row.clips, 4) if row.clips else 0.0,
                    published_share=round(row.published / row.clips, 4) if row.clips else 0.0,
                )
                for row in rows
            ],
        )
