from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Integer, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from broll.model import AssetStatus, BrollAsset, BrollLicense, BrollUsage


@dataclass
class Candidate:
    asset: BrollAsset
    text_rank: float
    commercial_ok: bool


class BrollRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, source: str, source_id: str) -> bool:
        stmt = select(BrollAsset.id).where(BrollAsset.source == source, BrollAsset.source_id == source_id).limit(1)
        return (await self._session.execute(stmt)).first() is not None

    async def hash_exists(self, content_hash: str) -> bool:
        stmt = select(BrollAsset.id).where(BrollAsset.content_hash == content_hash).limit(1)
        return (await self._session.execute(stmt)).first() is not None

    async def add(self, asset: BrollAsset, license_row: BrollLicense | None = None) -> BrollAsset:
        self._session.add(asset)
        await self._session.flush()
        if license_row is not None:
            license_row.asset_id = asset.id
            self._session.add(license_row)
        await self._session.commit()
        return asset

    async def get(self, asset_id: str) -> BrollAsset | None:
        return await self._session.get(BrollAsset, asset_id)

    async def get_many(self, asset_ids: list[str]) -> list[BrollAsset]:
        if not asset_ids:
            return []
        rows = (await self._session.execute(select(BrollAsset).where(BrollAsset.id.in_(asset_ids)))).scalars().all()
        order = {asset_id: index for index, asset_id in enumerate(asset_ids)}
        return sorted(rows, key=lambda a: order[a.id])

    async def license_for(self, asset_id: str) -> BrollLicense | None:
        return await self._session.get(BrollLicense, asset_id)

    async def set_status(self, asset_id: str, status: AssetStatus, reason: str | None = None) -> bool:
        result = await self._session.execute(
            update(BrollAsset).where(BrollAsset.id == asset_id).values(status=status, status_reason=reason)
        )
        await self._session.commit()
        return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        min_duration: float = 0.0,
        user_id: str | None = None,
        commercial: bool = False,
        exclude_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[Candidate]:
        """Live shots matching ``query`` by full-text rank, filtered for the scene.

        A user's own private assets are included; nobody else's are.
        """
        vector = func.to_tsvector("english", BrollAsset.search_text)
        tsquery = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(vector, tsquery).label("rank")
        conditions = [
            BrollAsset.status == AssetStatus.LIVE,
            BrollAsset.duration_s >= min_duration,
            vector.op("@@")(tsquery),
            or_(BrollAsset.owner_user_id.is_(None), BrollAsset.owner_user_id == user_id),
        ]
        if exclude_ids:
            conditions.append(BrollAsset.id.not_in(exclude_ids))
        if commercial:
            conditions.append(or_(BrollAsset.has_logos.is_(None), BrollAsset.has_logos.is_(False)))
        stmt = (
            select(BrollAsset, rank, func.coalesce(BrollLicense.commercial_ok, True))
            .outerjoin(BrollLicense, BrollLicense.asset_id == BrollAsset.id)
            .where(and_(*conditions))
            .order_by(rank.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            Candidate(asset=row[0], text_rank=float(row[1]), commercial_ok=bool(row[2]))
            for row in rows
            if not commercial or row[2]
        ]

    async def recently_used(self, user_id: str, days: int = 30) -> set[str]:
        since = datetime.utcnow() - timedelta(days=days)
        stmt = select(BrollUsage.asset_id).where(BrollUsage.user_id == user_id, BrollUsage.created_at >= since)
        return set((await self._session.execute(stmt)).scalars().all())

    async def swap_rates(self, asset_ids: list[str]) -> dict[str, float]:
        """Share of placements users swapped away, per asset; the library's quality signal."""
        if not asset_ids:
            return {}
        swapped = func.sum(func.cast(BrollUsage.swapped, Integer))
        stmt = (
            select(BrollUsage.asset_id, func.count(), swapped)
            .where(BrollUsage.asset_id.in_(asset_ids))
            .group_by(BrollUsage.asset_id)
        )
        return {asset_id: (swaps or 0) / count for asset_id, count, swaps in (await self._session.execute(stmt)).all() if count}

    async def record_usage(self, rows: list[BrollUsage]) -> None:
        self._session.add_all(rows)
        await self._session.commit()

    async def list_assets(self, query: str | None, status: AssetStatus | None, limit: int, offset: int) -> tuple[list[BrollAsset], int]:
        conditions = []
        if status is not None:
            conditions.append(BrollAsset.status == status)
        if query:
            conditions.append(func.to_tsvector("english", BrollAsset.search_text).op("@@")(func.websearch_to_tsquery("english", query)))
        base = select(BrollAsset).where(*conditions)
        total = (await self._session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self._session.execute(base.order_by(BrollAsset.created_at.desc()).limit(limit).offset(offset))).scalars().all()
        return list(rows), int(total)

