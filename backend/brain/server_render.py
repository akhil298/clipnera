"""Render on server (TODO 17.2): the backend Timeline, rendered at full size by edit_engine.render.

The studio's own export renders in the browser; this one renders the saved project on the
server (brain.render_adapter → edit_engine.render), uploads it next to the project's media and
hands back a signed download link.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brain.model import EditorRender
from brain.schema import RenderStatus
from brain.render_adapter import main_clips, render_timeline
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from editor.service import EditorService, asset_prefix
from jobs.queue import Job, get_queue, handler

log = get_logger(__name__)

RENDER_JOB = "editor.render"
URL_TTL_SECONDS = 3600


async def start(session: AsyncSession, user_id: str, project_id: str) -> EditorRender:
    service = EditorService(session)
    project = await service.get(user_id, project_id)
    if not main_clips(project.timeline):
        raise CustomException(message="Add a clip to the main track first.", code="NOTHING_TO_RENDER", status_code=422)
    render = EditorRender(project_id=project.id, user_id=user_id, version=project.version)
    session.add(render)
    await session.commit()
    await get_queue().enqueue(Job(RENDER_JOB, {"render_id": render.id}))
    return render


async def get(session: AsyncSession, user_id: str, render_id: str) -> EditorRender:
    render = await session.scalar(select(EditorRender).where(EditorRender.id == render_id, EditorRender.user_id == user_id))
    if render is None:
        raise CustomException(message="Render not found.", code="NOT_FOUND", status_code=404)
    return render


def status(render: EditorRender) -> RenderStatus:
    return RenderStatus(id=render.id, status=render.status, stage=render.stage, version=render.version,
                        download_url=download_url(render), error=render.error)


def download_url(render: EditorRender, s3: S3 | None = None) -> str | None:
    if render.status != "done" or not render.key:
        return None
    return (s3 or S3()).generate_presigned_url(get_settings().S3_BUCKET_NAME, render.key, URL_TTL_SECONDS,
                                               download_name="clipnera-edit.mp4")


async def _set(render_id: str, **fields: object) -> None:
    async with AsyncSessionLocal() as session:
        render = await session.get(EditorRender, render_id)
        for name, value in fields.items():
            setattr(render, name, value)
        await session.commit()


@handler(RENDER_JOB)
async def run_render(job: Job) -> None:
    render_id = job.payload["render_id"]
    try:
        await _render(render_id)
    except Exception as exc:
        log.exception("Server render failed: %s", render_id)
        await _set(render_id, status="failed", stage="Failed", error=f"The render failed: {exc}"[:500])


async def _render(render_id: str) -> None:
    async with AsyncSessionLocal() as session:
        render = await session.get(EditorRender, render_id)
        service = EditorService(session)
        project = await service.get(render.user_id, render.project_id)
        muds = (await service.media(render.user_id, render.project_id)).muds
        user_id, project_id = render.user_id, render.project_id
    await _set(render_id, status="rendering", stage="Fetching your media")
    with tempfile.TemporaryDirectory(prefix="clipnera-render-") as work:
        await _set(render_id, stage="Rendering")
        video = await render_timeline(project.timeline, muds, Path(work), preview=False)
        await _set(render_id, stage="Uploading")
        key = f"{asset_prefix(user_id, project_id)}renders/{render_id}.mp4"
        await asyncio.to_thread(S3().upload_file, get_settings().S3_BUCKET_NAME, key, str(video), "video/mp4")
    await _set(render_id, status="done", stage="Ready", key=key)
