from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from clip_generation.model import GeneratedClip
from subtitle_styling.model import SubtitleStyle
from core.logging_config import get_logger

log = get_logger(__name__)


class ClipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_clip(self, **kwargs) -> GeneratedClip:
        clip = GeneratedClip(**kwargs)
        self._session.add(clip)
        await self._session.commit()
        await self._session.refresh(clip)
        return clip

    async def get_clip(self, clip_id: str, user_id: str) -> GeneratedClip | None:
        stmt = select(GeneratedClip).where(
            GeneratedClip.id == clip_id,
            GeneratedClip.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_clips(self, project_id: str, user_id: str) -> list[GeneratedClip]:
        stmt = (
            select(GeneratedClip)
            .where(
                GeneratedClip.project_id == project_id,
                GeneratedClip.user_id == user_id,
            )
            .order_by(desc(GeneratedClip.score))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_clip(self, clip_id: str, user_id: str, **kwargs) -> GeneratedClip | None:
        clip = await self.get_clip(clip_id, user_id)
        if not clip:
            return None
        for key, value in kwargs.items():
            if hasattr(clip, key):
                setattr(clip, key, value)
        await self._session.commit()
        await self._session.refresh(clip)
        return clip

    async def delete_clip(self, clip_id: str, user_id: str) -> bool:
        clip = await self.get_clip(clip_id, user_id)
        if not clip:
            return False
        await self._session.delete(clip)
        await self._session.commit()
        return True

    async def list_subtitle_styles(self, user_id: str) -> list[SubtitleStyle]:
        stmt = (
            select(SubtitleStyle)
            .where(SubtitleStyle.user_id == user_id)
            .order_by(desc(SubtitleStyle.created_at))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_subtitle_style(self, style_id: str, user_id: str) -> SubtitleStyle | None:
        stmt = select(SubtitleStyle).where(
            SubtitleStyle.id == style_id,
            SubtitleStyle.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_subtitle_style(self, user_id: str, name: str, style_type: str, config: str | None = None, is_preset: bool = False) -> SubtitleStyle:
        style = SubtitleStyle(
            user_id=user_id,
            name=name,
            style_type=style_type,
            config=config,
            is_preset=is_preset,
        )
        self._session.add(style)
        await self._session.commit()
        await self._session.refresh(style)
        return style
