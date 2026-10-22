"""Queue, track and read the MUDs of an editor project's assets."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from editor.timeline import Asset
from jobs.queue import Job, get_queue
from understanding.model import AnalysisStatus, MediaAnalysis
from core.logging_config import get_logger
from understanding import reading
from understanding.mud import MUD, check_mud

ANALYZE_JOB = "understanding.analyze"
log = get_logger(__name__)
_CACHE_SIZE = 64
# (key, when it was written) -> MUD, so a rebuilt document is read afresh.
_cache: OrderedDict[tuple[str, str], MUD] = OrderedDict()


@dataclass(frozen=True)
class ProjectMedia:
    """What the agent may know about a project's media: its fps (for frame refs), asset names,
    the ready MUDs and every asset's analysis status."""

    fps: int
    names: dict[str, str]
    muds: dict[str, MUD]
    statuses: dict[str, str]

    def mud(self, asset_id: str) -> MUD:
        if asset_id not in self.names:
            raise CustomException(message=f"There is no asset {asset_id}.", code="UNKNOWN_ASSET", status_code=422)
        if asset_id not in self.muds:
            status = self.statuses.get(asset_id, "pending")
            raise CustomException(message=f"{asset_id} isn't analysed yet ({status}).", code="NOT_READY", status_code=409)
        return self.muds[asset_id]


def mud_key(asset_key: str) -> str:
    """The MUD sits next to the asset it describes."""
    return f"{Path(asset_key).with_suffix('')}.mud.json"


class UnderstandingService:
    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3_client = s3

    @property
    def _s3(self) -> S3:
        if self._s3_client is None:
            self._s3_client = S3()
        return self._s3_client

    async def queue(self, user_id: str, project_id: str, assets: Iterable[Asset]) -> None:
        """Start understanding assets the project has no analysis for yet. Commits."""
        known = set(await self._session.scalars(
            select(MediaAnalysis.asset_id).where(MediaAnalysis.project_id == project_id)
        ))
        new = [a for a in assets if a.id not in known]
        for asset in new:
            self._session.add(MediaAnalysis(project_id=project_id, user_id=user_id, asset_id=asset.id,
                                            asset_key=asset.key, kind=asset.kind, status=AnalysisStatus.PENDING))
        if not new:
            return
        await self._session.commit()
        for asset in new:
            await get_queue().enqueue(Job(ANALYZE_JOB, {"project_id": project_id, "asset_id": asset.id}))

    async def retry(self, project_id: str, asset_id: str) -> MediaAnalysis:
        row = await self._row(project_id, asset_id)
        if row.status != AnalysisStatus.FAILED:
            raise CustomException(message="Only a failed analysis can be run again.", code="NOT_FAILED", status_code=409)
        row.status, row.error = AnalysisStatus.PENDING, None
        await self._session.commit()
        # updated_at is set by the database, so read it back.
        await self._session.refresh(row)
        await get_queue().enqueue(Job(ANALYZE_JOB, {"project_id": project_id, "asset_id": asset_id}))
        return row

    async def statuses(self, project_id: str) -> list[MediaAnalysis]:
        return list(await self._session.scalars(
            select(MediaAnalysis).where(MediaAnalysis.project_id == project_id).order_by(MediaAnalysis.created_at)
        ))

    async def muds(self, project_id: str) -> dict[str, MUD]:
        """The ready MUDs of a project, by asset id."""
        ready = [row for row in await self.statuses(project_id) if row.status == AnalysisStatus.READY and row.mud_key]
        loaded = await asyncio.gather(*(self._load(row) for row in ready))
        return {row.asset_id: mud for row, mud in zip(ready, loaded)}

    async def ensure_moments(self, project_id: str) -> dict[str, MUD]:
        """The ready MUDs with their strongest moments picked: for the edits that need them (a reel, a hook,
        highlights). Picked once per asset and saved into its MUD; never when the file arrives."""
        ready = [row for row in await self.statuses(project_id) if row.status == AnalysisStatus.READY and row.mud_key]
        muds = await asyncio.gather(*(self._load(row) for row in ready))
        todo = [(row, mud) for row, mud in zip(ready, muds) if mud.utterances and mud.analyzers.get("moments") != "ok"]

        async def pick(row: MediaAnalysis, mud: MUD) -> None:
            from understanding.build import moments_of  # The analysis stack (shot detection, audio) only when picking.

            try:
                picked = await reading.pick_moments(mud.utterances)
            except Exception:
                log.exception("Picking moments failed: asset=%s", row.asset_id)
                picked = None
            mud.moments = moments_of(mud, picked)
            mud.analyzers["moments"] = "ok" if picked else "failed"
            check_mud(mud)
            # The cached copy is this object, so later reads see the moments without loading again.
            await asyncio.to_thread(self._s3.put_object, get_settings().S3_BUCKET_NAME, row.mud_key,
                                    mud.model_dump_json(exclude_defaults=True), ContentType="application/json")

        await asyncio.gather(*(pick(row, mud) for row, mud in todo))
        return {row.asset_id: mud for row, mud in zip(ready, muds)}

    async def _load(self, row: MediaAnalysis) -> MUD:
        key = (row.mud_key or "", row.updated_at.isoformat())
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        body = await asyncio.to_thread(self._s3.get_object, get_settings().S3_BUCKET_NAME, key[0])
        mud = MUD.model_validate_json(body)
        _cache[key] = mud
        if len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
        return mud

    async def _row(self, project_id: str, asset_id: str) -> MediaAnalysis:
        row = await self._session.scalar(select(MediaAnalysis).where(
            MediaAnalysis.project_id == project_id, MediaAnalysis.asset_id == asset_id))
        if row is None:
            raise CustomException(message="That asset has no analysis.", code="NOT_FOUND", status_code=404)
        return row
