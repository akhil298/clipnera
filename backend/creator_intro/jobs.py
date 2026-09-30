"""The intro's background job: write the line, render every rendition, store them."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from brand_kit.repository import BrandKitRepository
from clients.ai import get_text_client
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from creator_intro.copy import write_copy
from creator_intro.model import IntroStatus
from creator_intro.platforms import look_for
from creator_intro.render import SIZES, IntroSpec, render
from creator_intro.service import RENDER_JOB, key_prefix, load_intro
from jobs.queue import Job, handler
from usage.context import llm_scope

log = get_logger(__name__)


@handler(RENDER_JOB)
async def render_intro(job: Job) -> None:
    user_id = job.payload["user_id"]
    try:
        with llm_scope(user_id=user_id, step="intro_copy"):
            await _render(user_id)
    except Exception as exc:
        log.exception("Creator intro render failed: user=%s", user_id)
        async with AsyncSessionLocal() as session:
            intro = await load_intro(session, user_id)
            if intro:
                intro.status, intro.error = IntroStatus.FAILED, f"Render failed: {exc}"[:500]
                await session.commit()


async def _render(user_id: str) -> None:
    bucket = get_settings().S3_BUCKET_NAME
    s3 = S3()
    async with AsyncSessionLocal() as session:
        intro = await load_intro(session, user_id)
        kit = await BrandKitRepository(session).get_by_user_id(user_id)
    if intro is None:
        return

    tagline, theme = intro.tagline, intro.theme
    if not tagline or theme == "auto":
        # The intro is a Pro feature, so it writes on the Pro model for this step.
        copy = await write_copy(get_text_client(is_pro=True, step="intro_copy"), intro.platform, intro.niche,
                                intro.channel_name, intro.about)
        tagline = tagline or copy.tagline
        theme = copy.theme if theme == "auto" else theme

    with tempfile.TemporaryDirectory(prefix="clipnera-intro-") as tmp:
        work = Path(tmp)
        avatar = None
        if intro.avatar_key:
            avatar = work / Path(intro.avatar_key).name
            await asyncio.to_thread(s3.download_file, bucket, intro.avatar_key, str(avatar))
        spec = IntroSpec(
            name=intro.channel_name, tagline=tagline or "", theme=theme, handle=intro.handle, avatar=avatar,
            look=look_for(intro.platform, kit.primary_color if kit else None),
        )
        version = uuid4().hex[:10]
        files: dict[str, str] = {}
        for ratio in SIZES:
            out = await asyncio.to_thread(render, spec, ratio, work / f"intro_{ratio}.mp4", work)
            key = f"{key_prefix(user_id)}intro_{version}_{ratio}.mp4"
            await asyncio.to_thread(s3.upload_file, bucket, key, str(out), "video/mp4")
            files[ratio] = key

    async with AsyncSessionLocal() as session:
        intro = await load_intro(session, user_id)
        old = json.loads(intro.files)
        intro.files, intro.tagline, intro.theme_used = json.dumps(files), tagline, theme
        intro.status, intro.error = IntroStatus.READY, None
        await session.commit()
    for key in old.values():
        await asyncio.to_thread(s3.delete_object, bucket, key)
    log.info("Creator intro rendered: user=%s theme=%s", user_id, theme)
