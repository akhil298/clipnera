"""The asset registry in the product: rows in ``reel_assets``, files in S3."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import or_, select, update

from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from reel_engine.assets import AssetRecord, AssetStore, match
from reel_engine.model import ReelAsset

PREFIX = "reel_assets"


def _record(row: ReelAsset) -> AssetRecord:
    return AssetRecord(id=row.id, kind=row.kind, scope=row.scope, owner=row.owner_id or "", path=row.storage_key,
                       words=json.loads(row.words or "[]"), description=row.description, licence=row.licence, source=row.source,
                       made_by=json.loads(row.made_by or "{}"), meta=json.loads(row.meta or "{}"), uses=row.uses,
                       created_at=row.created_at.isoformat() if row.created_at else "")


class DbAssetStore(AssetStore):
    def __init__(self, s3: S3 | None = None) -> None:
        self.s3 = s3 or S3()
        self.bucket = get_settings().S3_BUCKET_NAME

    async def search(self, kind: str, words: set[str], owner: str) -> list[AssetRecord]:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(select(ReelAsset).where(
                ReelAsset.kind == kind, or_(ReelAsset.scope == "global", ReelAsset.owner_id == (owner or None))
            ))).scalars().all()
        return match([_record(r) for r in rows], words)

    async def add(self, record: AssetRecord, file: Path) -> AssetRecord:
        key = f"{PREFIX}/{record.scope}/{record.kind}/{record.id}{file.suffix}"
        await asyncio.to_thread(self.s3.upload_file, self.bucket, key, str(file), "audio/wav" if file.suffix == ".wav" else None)
        record.path = key
        async with AsyncSessionLocal() as session:
            session.add(ReelAsset(id=record.id, kind=record.kind, scope=record.scope, owner_id=record.owner or None, storage_key=key,
                                  words=json.dumps(record.words), description=record.description, licence=record.licence,
                                  source=record.source, made_by=json.dumps(record.made_by), meta=json.dumps(record.meta)))
            await session.commit()
        return record

    async def local(self, record: AssetRecord, work: Path) -> Path:
        target = work / "assets" / Path(record.path).name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self.s3.download_file, self.bucket, record.path, str(target))
        return target

    async def used(self, ids: list[str]) -> None:
        if not ids:
            return
        async with AsyncSessionLocal() as session:
            await session.execute(update(ReelAsset).where(ReelAsset.id.in_(ids)).values(uses=ReelAsset.uses + 1))
            await session.commit()
