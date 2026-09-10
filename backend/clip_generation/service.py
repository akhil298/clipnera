from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from clients.services.s3 import S3
from clients.ai.gemini import Gemini
from clients.ai.openai import OpenAI
from core.config import get_settings
from core.logging_config import get_logger
from core.database import AsyncSessionLocal
from clip_generation.model import GeneratedClip, ContentCategory
from subtitle_styling.model import SubtitleStyle
from clip_generation.repository import ClipRepository
from content_intelligence.service import ContentIntelligenceService
from video_processor.ffmpeg_service import FFmpegService
from core.exceptions import CustomException

settings = get_settings()
log = get_logger(__name__)


class ClipService:
    def __init__(self) -> None:
        self._s3 = S3()
        self._bucket = settings.S3_BUCKET_NAME
        self._ffmpeg = FFmpegService()
        self._content_ai = ContentIntelligenceService()

    async def list_clips(self, project_id: str, user_id: str) -> list[dict]:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = await repo.list_clips(project_id, user_id)
            return [self._serialize_clip(c) for c in clips]

    async def get_clip(self, clip_id: str, user_id: str) -> dict | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clip = await repo.get_clip(clip_id, user_id)
            return self._serialize_clip(clip) if clip else None

    async def generate_clips_for_project(self, project_id: str, user_id: str, progress_callback: Callable[[str, int, str | None], None] | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project_repo = ClipRepository
            from clip.repository import ClipRepository as ProjectRepo
            async with AsyncSessionLocal() as psession:
                p = ProjectRepo(psession)
                project = await p.get_project(project_id, user_id)
            if not project:
                raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        video_path = project.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Video file not found on disk. Re-download may be required.", code="VIDEO_MISSING", status_code=404)

        if progress_callback:
            await self._notify(progress_callback, "Starting content analysis...", 5)

        analysis = await self._content_ai.analyze_project(
            project_id=project_id,
            video_path=video_path,
            transcript_segments=[],
            progress_callback=progress_callback,
        )

        if progress_callback:
            await self._notify(progress_callback, "Detecting highlights...", 40)

        highlights = await self._content_ai.detect_highlights(
            project_id=project_id,
            video_path=video_path,
            transcript_segments=[],
            analysis=analysis,
            progress_callback=progress_callback,
        )

        if progress_callback:
            await self._notify(progress_callback, f"Scoring and generating {len(highlights)} candidate clips...", 60)

        scored = await self._content_ai.score_highlights(highlights, analysis)

        if progress_callback:
            await self._notify(progress_callback, "Generating clip metadata...", 75)

        final_clips = await self._content_ai.generate_metadata_for_clips(scored)

        if progress_callback:
            await self._notify(progress_callback, "Saving clips to database...", 85)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            saved_clips = []
            for clip_data in final_clips:
                clip = await repo.create_clip(
                    project_id=project_id,
                    user_id=user_id,
                    title=clip_data["title"],
                    description=clip_data.get("description"),
                    start_time=clip_data["start_time"],
                    end_time=clip_data["end_time"],
                    duration_seconds=clip_data["end_time"] - clip_data["start_time"],
                    score=clip_data["score"],
                    content_category=clip_data.get("content_category", ContentCategory.UNKNOWN.value),
                    status="pending",
                )
                saved_clips.append(clip)

        if progress_callback:
            await self._notify(progress_callback, "Clip generation completed", 100)

        return {
            "project_id": project_id,
            "clips_generated": len(saved_clips),
            "clips": [self._serialize_clip(c) for c in saved_clips],
        }

    async def process_clip_subtitles(self, clip_id: str, user_id: str, burn_request: dict) -> dict:
        clip = await self._get_clip(clip_id, user_id)
        if not clip:
            raise CustomException(message="Clip not found", code="NOT_FOUND", status_code=404)

        video_path = clip.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Clip video file missing", code="VIDEO_MISSING", status_code=404)

        from subtitle_styling.service import SubtitleStylingService
        styling = SubtitleStylingService()
        burned_path = await styling.burn_subtitles(
            video_path=video_path,
            clip_start=clip.start_time,
            clip_end=clip.end_time,
            style_type=burn_request.get("style_type", "bold_captions"),
            custom_config=burn_request.get("custom_config"),
            subtitles=burn_request.get("subtitles"),
            title_text=clip.title,
            enable_watermark=burn_request.get("enable_watermark", True),
        )

        s3_key = f"clips/{user_id}/{clip.project_id}/{clip_id}_burned.mp4"
        s3_bucket = self._bucket
        try:
            s3_bucket_obj = self._s3.create_bucket(s3_bucket)
        except Exception:
            pass

        with open(burned_path, "rb") as f:
            file_bytes = f.read()
        self._s3.put_object(s3_bucket, s3_key, file_bytes)
        presigned_url = self._s3.generate_presigned_url(s3_bucket, s3_key, expires_in=3600)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            await repo.update_clip(
                clip_id=clip_id,
                user_id=user_id,
                burned_subtitle_path=burned_path,
                burned_presigned_url=presigned_url,
                status="burned",
            )

        return {
            "clip_id": clip_id,
            "burned_presigned_url": presigned_url,
            "local_path": burned_path,
        }

    async def list_subtitle_styles(self, user_id: str) -> list[dict]:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            styles = await repo.list_subtitle_styles(user_id)
            return [self._serialize_style(s) for s in styles]

    async def create_subtitle_style(self, user_id: str, name: str, style_type: str, config: str | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            style = await repo.create_subtitle_style(user_id, name, style_type, config)
            return self._serialize_style(style)

    async def _get_clip(self, clip_id: str, user_id: str) -> GeneratedClip | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            return await repo.get_clip(clip_id, user_id)

    def _serialize_clip(self, clip: GeneratedClip | None) -> dict | None:
        if not clip:
            return None
        return {
            "id": clip.id,
            "project_id": clip.project_id,
            "user_id": clip.user_id,
            "title": clip.title,
            "description": clip.description,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "duration_seconds": clip.duration_seconds,
            "score": clip.score,
            "content_category": clip.content_category,
            "presigned_url": clip.presigned_url,
            "local_path": clip.local_path,
            "status": clip.status,
            "subtitle_style_id": clip.subtitle_style_id,
            "burned_subtitle_path": clip.burned_subtitle_path,
            "burned_presigned_url": clip.burned_presigned_url,
            "created_at": clip.created_at.isoformat() if clip.created_at else None,
        }

    def _serialize_style(self, style: SubtitleStyle) -> dict:
        return {
            "id": style.id,
            "user_id": style.user_id,
            "name": style.name,
            "style_type": style.style_type,
            "config": style.config,
            "is_preset": style.is_preset,
            "created_at": style.created_at.isoformat() if style.created_at else None,
        }

    async def _notify(self, cb, message: str, percent: int) -> None:
        if cb:
            try:
                result = cb(message, percent, None)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                log.debug(f"Progress notify failed: {e}")
