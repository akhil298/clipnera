"""The ``understanding.analyze`` job: build one editor asset's MUD and store it in S3.

Safe to run again: it rebuilds the document from the asset and overwrites it.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from jobs.queue import Job, handler
from sqlalchemy import select
from subscription.service import SubscriptionService
from understanding.build import build_mud
from understanding.model import AnalysisStatus, MediaAnalysis
from understanding.service import ANALYZE_JOB, mud_key
from usage.context import llm_scope

log = get_logger(__name__)


@handler(ANALYZE_JOB)
async def analyze_asset(job: Job) -> None:
    project_id, asset_id = job.payload["project_id"], job.payload["asset_id"]
    row = await _set(project_id, asset_id, status=AnalysisStatus.RUNNING)
    if row is None:
        return
    try:
        # Not charged to a pipeline project: llm_usage.project_id points at video projects.
        with llm_scope(user_id=row.user_id, step="media_understanding"):
            key = await _build(row)
    except Exception as exc:
        log.exception("Media understanding failed: project=%s asset=%s", project_id, asset_id)
        detail = str(exc) if isinstance(exc, ValueError) else "please try again"
        await _set(project_id, asset_id, status=AnalysisStatus.FAILED, error=f"Couldn't understand this file: {detail}"[:500])
        return
    await _set(project_id, asset_id, status=AnalysisStatus.READY, mud_key=key, error=None)


async def _build(row: MediaAnalysis) -> str:
    s3, bucket = S3(), get_settings().S3_BUCKET_NAME
    async with AsyncSessionLocal() as session:
        is_pro = (await SubscriptionService.for_session(session).get_entitlements(row.user_id)).pro_ai_provider
    with tempfile.TemporaryDirectory(prefix="clipnera-mud-") as workdir:
        work = Path(workdir)
        local = work / f"source{Path(row.asset_key).suffix}"
        await asyncio.to_thread(s3.download_file, bucket, row.asset_key, str(local))
        mud = await build_mud(str(local), row.asset_id, row.kind, is_pro=is_pro, workdir=work)
    key = mud_key(row.asset_key)
    await asyncio.to_thread(s3.put_object, bucket, key, mud.model_dump_json(exclude_defaults=True),
                            ContentType="application/json")
    return key


async def _set(project_id: str, asset_id: str, **fields: object) -> MediaAnalysis | None:
    async with AsyncSessionLocal() as session:
        analysis = await session.scalar(select(MediaAnalysis).where(
            MediaAnalysis.project_id == project_id, MediaAnalysis.asset_id == asset_id))
        if analysis is None:
            return None
        for name, value in fields.items():
            setattr(analysis, name, value)
        await session.commit()
        return analysis
