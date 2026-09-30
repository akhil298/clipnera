"""The creator's channel intro: save it, render it once, play it before exports."""

from __future__ import annotations

import asyncio
import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branding.service import nearest
from broll.renditions import run
from clients.services.s3 import S3
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from creator_intro.model import CreatorIntro, IntroStatus
from creator_intro.render import DURATION_S, prepend_cmd
from creator_intro.schema import (
    CreatorIntroAvatarRequest,
    CreatorIntroAvatarUpload,
    CreatorIntroResponse,
    CreatorIntroSaveRequest,
)
from hook_transitions.graph import MediaInfo
from jobs.queue import Job, get_queue
from subscription.service import SubscriptionService
from video_processor.ffmpeg_service import FFmpegService

RENDER_JOB = "creator_intro.render"
URL_TTL_SECONDS = 3600
_AVATAR_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def key_prefix(user_id: str) -> str:
    return f"creator_intros/{user_id}/"


async def load_intro(session: AsyncSession, user_id: str) -> CreatorIntro | None:
    return (await session.execute(select(CreatorIntro).where(CreatorIntro.user_id == user_id))).scalar_one_or_none()


class CreatorIntroService:
    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3 = s3 or S3()
        self._bucket = get_settings().S3_BUCKET_NAME

    async def get(self, user_id: str) -> CreatorIntroResponse | None:
        intro = await load_intro(self._session, user_id)
        return self.response(intro) if intro else None

    async def avatar_upload(self, user_id: str, request: CreatorIntroAvatarRequest) -> CreatorIntroAvatarUpload:
        key = f"{key_prefix(user_id)}avatar_{uuid4().hex}{_AVATAR_EXTENSIONS[request.content_type]}"
        url = self._s3.presign_put(self._bucket, key, request.content_type, URL_TTL_SECONDS)
        return CreatorIntroAvatarUpload(key=key, url=url, content_type=request.content_type)

    async def save(self, user_id: str, request: CreatorIntroSaveRequest) -> CreatorIntroResponse:
        intro = await load_intro(self._session, user_id)
        if intro is None:
            intro = CreatorIntro(user_id=user_id, channel_name=request.channel_name)
            self._session.add(intro)
        if intro.status == IntroStatus.RENDERING:
            raise CustomException(message="Wait for the intro to finish rendering", code="INTRO_BUSY", status_code=409)
        if request.avatar_key and request.avatar_key != intro.avatar_key:
            if not request.avatar_key.startswith(key_prefix(user_id)):
                raise CustomException(message="Unknown upload", code="INVALID_BODY", status_code=400)
            await asyncio.to_thread(self._s3.object_size, self._bucket, request.avatar_key)  # raises if missing
            intro.avatar_key = request.avatar_key
        elif request.remove_avatar:
            intro.avatar_key = None
        intro.platform = request.platform
        intro.niche = (request.niche or "").strip() or None
        intro.channel_name = request.channel_name.strip()
        intro.handle = (request.handle or "").strip() or None
        intro.about = request.about.strip()
        intro.tagline = " ".join((request.tagline or "").split()) or None
        intro.theme = request.theme
        intro.enabled = request.enabled
        await self._commit(intro)
        return self.response(intro)

    async def render(self, user_id: str) -> CreatorIntroResponse:
        """Queue a render of the saved intro; counts toward the plan's daily intro renders."""
        intro = await load_intro(self._session, user_id)
        if intro is None:
            raise CustomException(message="Save your channel details first", code="NOT_FOUND", status_code=404)
        if intro.status == IntroStatus.RENDERING:
            raise CustomException(message="The intro is already rendering", code="INTRO_BUSY", status_code=409)
        await SubscriptionService.for_session(self._session).consume_daily_quota(user_id, "intro_renders")
        intro.status, intro.error = IntroStatus.RENDERING, None
        await self._commit(intro)
        await get_queue().enqueue(Job(RENDER_JOB, {"user_id": user_id}))
        return self.response(intro)

    async def _commit(self, intro: CreatorIntro) -> None:
        # updated_at is set by the database, so reload it rather than lazy-load it later.
        await self._session.commit()
        await self._session.refresh(intro)

    def response(self, intro: CreatorIntro) -> CreatorIntroResponse:
        files: dict[str, str] = json.loads(intro.files)
        return CreatorIntroResponse(
            status=intro.status.value, platform=intro.platform, niche=intro.niche, channel_name=intro.channel_name,
            handle=intro.handle, about=intro.about, tagline=intro.tagline, theme=intro.theme,
            theme_used=intro.theme_used, avatar_url=self._url(intro.avatar_key), enabled=intro.enabled,
            preview_urls={ratio: self._url(key) for ratio, key in files.items()},
            duration_s=DURATION_S, error=intro.error, updated_at=intro.updated_at,
        )

    def _url(self, key: str | None) -> str | None:
        return self._s3.generate_presigned_url(self._bucket, key, URL_TTL_SECONDS) if key else None


class ExportIntro:
    """The creator's rendered intro during one export, downloaded per rendition as needed."""

    def __init__(self, files: dict[str, str], work: Path, s3: S3) -> None:
        self._files, self._work, self._s3 = files, work, s3
        self._local: dict[str, str] = {}

    async def prepend(self, video: Path, out: Path) -> Path:
        """``video`` with the intro in front, written to ``out``."""
        media = MediaInfo.from_probe(await FFmpegService().get_video_info(str(video)))
        key = nearest(self._files, media.width, media.height)
        if key not in self._local:
            local = self._work / Path(key).name
            await asyncio.to_thread(self._s3.download_file, get_settings().S3_BUCKET_NAME, key, str(local))
            self._local[key] = str(local)
        await run(prepend_cmd(self._local[key], video, out, media))
        return out


@asynccontextmanager
async def export_intro(user_id: str) -> AsyncIterator[ExportIntro | None]:
    """The user's intro while an export runs; None when they have no ready, enabled one."""
    async with AsyncSessionLocal() as session:
        intro = await load_intro(session, user_id)
    files = json.loads(intro.files) if intro and intro.status == IntroStatus.READY and intro.enabled else {}
    if not files:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="clipnera-intro-") as work:
        yield ExportIntro(files, Path(work), S3())
