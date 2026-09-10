from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brand_kit.model import BrandKit, LogoPosition, CaptionPreset


class BrandKitRepository:
    """Data access layer for brand kits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> BrandKit | None:
        stmt = select(BrandKit).where(BrandKit.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, brand_kit_id: str, user_id: str) -> BrandKit | None:
        stmt = select(BrandKit).where(BrandKit.id == brand_kit_id, BrandKit.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: str, **kwargs) -> BrandKit:
        brand_kit = BrandKit(user_id=user_id, **kwargs)
        self._session.add(brand_kit)
        await self._session.commit()
        await self._session.refresh(brand_kit)
        return brand_kit

    async def update(self, brand_kit: BrandKit, **kwargs) -> BrandKit:
        for key, value in kwargs.items():
            if hasattr(brand_kit, key):
                setattr(brand_kit, key, value)
        await self._session.commit()
        await self._session.refresh(brand_kit)
        return brand_kit

    async def delete(self, brand_kit: BrandKit) -> None:
        await self._session.delete(brand_kit)
        await self._session.commit()

    async def list_for_user(self, user_id: str) -> list[BrandKit]:
        stmt = select(BrandKit).where(BrandKit.user_id == user_id).order_by(BrandKit.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
