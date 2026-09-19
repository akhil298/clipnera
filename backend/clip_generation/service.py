from __future__ import annotations

import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any, Callable

from clients.services.s3 import S3
from clip_generation.model import ContentCategory, GeneratedClip, SocialPlatform, SOCIAL_PLATFORM_DEFAULTS
from clip_generation.repository import ClipRepository
from subtitle_styling.model import SubtitleStyle
from content_intelligence.service import ContentIntelligenceService
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from core.logging_config import get_logger
from video_processor.clip_cutter import ClipCutter, CutRequest
from video_processor.ffmpeg_service import FFmpegService
from content_intelligence.service import FALLBACK_ASPECT_RATIOS
from video_processor.geometry import SUPPORTED_ASPECT_RATIOS, output_dimensions

settings = get_settings()
log = get_logger(__name__)

# How many clips may be cut at once. Each cut runs its own FFmpeg encode, which
# is already multi-threaded, so a small number keeps the cores busy without the
# encodes starving each other.
MAX_CONCURRENT_CUTS = 3


class _CutProgress:
    """Tracks how many clips are cutting, done, failed and still queued.

    With clips running concurrently a bare index no longer says anything useful
    about progress, so state is kept per clip and reported as counts. Mutation
    happens from several tasks at once, hence the lock.
    """

    def __init__(self, total: int, notify: Callable[[str, int], Any]) -> None:
        self._total = total
        self._notify = notify
        self._running: dict[str, float] = {}
        self._done = 0
        self._failed = 0
        self._lock = asyncio.Lock()

    @property
    def _queued(self) -> int:
        return max(0, self._total - self._done - self._failed - len(self._running))

    def _percent(self) -> int:
        finished = self._done + self._failed
        # Cutting occupies the 40-95 band of the overall pipeline progress bar.
        return min(95, 40 + int(finished * 55 / max(1, self._total)))

    def _line(self) -> str:
        # Counts successes, not merely finished work: a failed clip is reported
        # in its own segment so "Cut 5/5" can never include one that failed.
        parts = [f"Cut {self._done}/{self._total} clips"]
        if self._running:
            now = time.monotonic()
            active = ", ".join(
                f"{clip_id} ({int(now - started)}s)"
                for clip_id, started in sorted(self._running.items(), key=lambda kv: kv[1])
            )
            parts.append(f"cutting {active}")
        if self._queued:
            parts.append(f"{self._queued} queued")
        if self._failed:
            parts.append(f"{self._failed} failed")
        return " | ".join(parts)

    async def mark_running(self, clip_id: str) -> None:
        async with self._lock:
            self._running[clip_id] = time.monotonic()
            line, percent = self._line(), self._percent()
        await self._notify(line, percent)

    async def mark_done(self, clip_id: str) -> None:
        async with self._lock:
            self._running.pop(clip_id, None)
            self._done += 1
            line, percent = self._line(), self._percent()
        await self._notify(line, percent)

    async def mark_failed(self, clip_id: str) -> None:
        async with self._lock:
            self._running.pop(clip_id, None)
            self._failed += 1
            line, percent = self._line(), self._percent()
        await self._notify(line, percent)

    async def notify_summary(self) -> None:
        async with self._lock:
            if self._failed:
                line = f"Cut {self._done}/{self._total} clips, {self._failed} failed"
            else:
                line = f"Cut all {self._done} clips"
        await self._notify(line, 95)


def _sanitize_str(s: str | None) -> str | None:
    if s is None:
        return None
    try:
        normalized = s.encode("utf-16", "surrogatepass").decode("utf-16", errors="replace")
        return normalized.encode("utf-8", errors="replace").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s.encode("utf-8", errors="replace").decode("utf-8")


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_str(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {_sanitize_str(str(key)): _sanitize_value(item) for key, item in value.items()}
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_sanitize_value(value), ensure_ascii=False, default=str)


class ClipService:
    def __init__(self, is_pro: bool = False) -> None:
        self._ffmpeg = FFmpegService()
        self._s3 = S3()
        self._bucket = settings.S3_BUCKET_NAME
        self._content_ai = ContentIntelligenceService(is_pro=is_pro)
        self._output_dir = Path(settings.CLIP_OUTPUT_DIR)

    async def list_clips(self, project_id: str, user_id: str) -> list[dict]:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = await repo.list_clips(project_id, user_id)
            return [self._serialize_clip(clip) for clip in clips]

    async def get_clip(self, clip_id: str, user_id: str) -> dict | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clip = await repo.get_clip(clip_id, user_id)
            return self._serialize_clip(clip) if clip else None

    async def process_clip_subtitles(self, clip_id: str, user_id: str, burn_request: dict) -> dict:
        clip = await self._get_clip(clip_id, user_id)
        if not clip:
            raise CustomException(message="Clip not found", code="NOT_FOUND", status_code=404)

        video_path = clip.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Clip video file missing", code="VIDEO_MISSING", status_code=404)

        from subtitle_styling.service import SubtitleStylingService
        styling = SubtitleStylingService()

        transcript_segments = json.loads(clip.transcript or "[]") if clip.transcript else None

        burned_path = await styling.burn_subtitles(
            video_path=clip.local_path,
            clip_start=clip.start_time,
            clip_end=clip.end_time,
            style_type=burn_request.get("style_type", "bold_captions"),
            custom_config=burn_request.get("custom_config"),
            subtitles=burn_request.get("subtitles"),
            title_text=clip.title,
            enable_watermark=burn_request.get("enable_watermark", True),
            transcript_segments=transcript_segments,
        )

        s3_key = f"clips/{user_id}/{clip.project_id}/{clip_id}_burned.mp4"
        s3_bucket = self._bucket
        try:
            self._s3.create_bucket(s3_bucket)
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

    async def export_clips_for_social(
        self,
        project_id: str,
        user_id: str,
        platforms: list[str],
        style_type: str | None = None,
        custom_config: dict | None = None,
        max_clips: int | None = None,
        max_duration_override: int | None = None,
        enable_emoji: bool = True,
        watermark_enabled: bool = True,
        burn_subtitles: bool = True,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
        animation_speed: float = 1.0,
    ) -> dict:
        project = await self._get_project(project_id, user_id)
        video_path = project.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Video file not found on disk", code="VIDEO_MISSING", status_code=404)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = await repo.list_clips(project_id, user_id)

        if not clips:
            raise CustomException(message="No clips found for project", code="NO_CLIPS", status_code=404)

        sorted_clips = sorted(clips, key=lambda c: c.score, reverse=True)
        if max_clips:
            sorted_clips = sorted_clips[:max_clips]

        transcript_segments = []
        for clip in sorted_clips:
            if clip.transcript:
                transcript_segments = json.loads(clip.transcript) if clip.transcript else []
                break
        if not transcript_segments:
            transcript_segments = await self._transcribe_if_missing(project_id, video_path, progress_callback)

        from subtitle_styling.service import SubtitleStylingService
        styling = SubtitleStylingService()

        exported_clips: list[dict] = []
        total_exports = len(sorted_clips) * len(platforms)
        completed = 0

        for clip in sorted_clips:
            clip_transcript = json.loads(clip.transcript) if clip.transcript else transcript_segments

            for platform_name in platforms:
                platform = self._validate_platform(platform_name)
                platform_defaults = SOCIAL_PLATFORM_DEFAULTS[platform.value]
                aspect_ratio = platform_defaults["aspect_ratio"]
                effective_style = style_type or platform_defaults["subtitle_style"]
                platform_max_duration = max_duration_override or platform_defaults.get("max_duration", 60)

                if progress_callback:
                    await self._notify(
                        progress_callback,
                        f"Exporting {platform.value} for clip {clip.title[:40]}...",
                        int(completed / max(1, total_exports) * 100),
                    )

                rendered_clips = await self.prepare_clip_outputs(
                    project_id=project_id,
                    video_path=video_path,
                    clips=[{
                        "clip_id": clip.id,
                        "title": clip.title,
                        "start_time": clip.start_time,
                        "end_time": clip.end_time,
                        "duration": max(0.0, min(clip.duration_seconds, float(platform_max_duration))),
                    }],
                    transcript_segments=clip_transcript,
                    output_aspect_ratios=[aspect_ratio],
                )

                for rendered in rendered_clips:
                    output_files = rendered.get("output_files", {})
                    platform_path = output_files.get(aspect_ratio, "")
                    burned_path = platform_path
                    presigned_url = None

                    if burn_subtitles and platform_path and Path(platform_path).exists():
                        s = float(rendered.get("start_time", clip.start_time))
                        e = float(rendered.get("end_time", clip.end_time))
                        ai_cues = json.loads(clip.analysis_json or "{}").get("clip", {}).get("ai_emoji_cues", []) if clip.analysis_json else []
                        
                        # Merge custom_config with animation_speed
                        merged_config = dict(custom_config or {})
                        merged_config["animation_speed"] = animation_speed
                        
                        burned_path = await styling.burn_subtitles(
                            video_path=clip.local_path or platform_path,
                            clip_start=s,
                            clip_end=e,
                            style_type=effective_style,
                            custom_config=merged_config,
                            title_text=clip.title,
                            enable_watermark=watermark_enabled,
                            transcript_segments=clip_transcript,
                            ai_cues=ai_cues if enable_emoji else None,
                        )

                        s3_key = f"social/{user_id}/{project_id}/{clip.id}_{platform.value}.mp4"
                        s3_bucket = self._bucket
                        try:
                            self._s3.create_bucket(s3_bucket)
                        except Exception:
                            pass

                        with open(burned_path, "rb") as f:
                            file_bytes = f.read()
                        self._s3.put_object(s3_bucket, s3_key, file_bytes)
                        presigned_url = self._s3.generate_presigned_url(s3_bucket, s3_key, expires_in=3600)

                    async with AsyncSessionLocal() as session:
                        repo = ClipRepository(session)
                        await repo.update_clip(
                            clip_id=clip.id,
                            user_id=user_id,
                            burned_subtitle_path=burned_path if burned_path != platform_path else None,
                            burned_presigned_url=presigned_url,
                        )

                    exported_clips.append({
                        "clip_id": clip.id,
                        "platform": platform.value,
                        "aspect_ratio": aspect_ratio,
                        "burned_presigned_url": presigned_url,
                        "local_path": burned_path,
                        "s3_key": f"social/{user_id}/{project_id}/{clip.id}_{platform.value}.mp4",
                    })

                completed += 1

        if progress_callback:
            await self._notify(progress_callback, "Social export completed", 100)

        return {
            "project_id": project_id,
            "exported_clips": exported_clips,
            "platforms": [p for p in platforms],
            "total_exported": len(exported_clips),
        }

    @staticmethod
    def _validate_platform(platform_name: str) -> SocialPlatform:
        try:
            return SocialPlatform(platform_name.lower())
        except ValueError:
            valid = ", ".join(p.value for p in SocialPlatform)
            raise CustomException(
                message=f"Invalid platform: {platform_name}. Valid platforms: {valid}",
                code="INVALID_PLATFORM",
                status_code=400,
            )

    async def list_subtitle_styles(self, user_id: str) -> list[dict]:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            styles = await repo.list_subtitle_styles(user_id)
            return [self._serialize_style(style) for style in styles]

    async def create_subtitle_style(self, user_id: str, name: str, style_type: str, config: str | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            style = await repo.create_subtitle_style(user_id, name, style_type, config)
            return self._serialize_style(style)

    async def _get_clip(self, clip_id: str, user_id: str) -> GeneratedClip | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            return await repo.get_clip(clip_id, user_id)

    async def generate_clips_for_project(
        self,
        project_id: str,
        user_id: str,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
        transcript_segments: list[dict[str, Any]] | None = None,
        analysis: dict[str, Any] | None = None,
        highlights: list[dict[str, Any]] | None = None,
        scored_highlights: list[dict[str, Any]] | None = None,
        final_clips: list[dict[str, Any]] | None = None,
        rendered_clips: list[dict[str, Any]] | None = None,
        output_aspect_ratios: list[str] | None = None,
        clip_settings: dict[str, Any] | None = None,
    ) -> dict:
        project = await self._get_project(project_id, user_id)
        video_path = project.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Video file not found on disk. Re-download may be required.", code="VIDEO_MISSING", status_code=404)
        video_metadata = await self._video_metadata(video_path)

        transcript_segments = list(transcript_segments or [])
        if not transcript_segments and video_path:
            if progress_callback:
                await self._notify(progress_callback, "No transcript provided, transcribing audio...", 3)
            transcript_segments = await self._transcribe_if_missing(project_id, video_path, progress_callback)

        if isinstance(output_aspect_ratios, str):
            output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
        if analysis is None:
            if progress_callback:
                await self._notify(progress_callback, "Starting content analysis...", 5)
            analysis = await self._content_ai.analyze_project(
                project_id=project_id,
                video_path=video_path,
                transcript_segments=transcript_segments,
                progress_callback=progress_callback,
            )

        if highlights is None:
            if progress_callback:
                await self._notify(progress_callback, "Detecting highlights...", 40)
            highlights = await self._content_ai.detect_highlights(
                project_id=project_id,
                video_path=video_path,
                transcript_segments=transcript_segments,
                analysis=analysis,
                progress_callback=progress_callback,
                clip_settings=clip_settings,
            )

        if scored_highlights is None:
            scored_highlights = await self._content_ai.score_highlights(highlights, analysis, clip_settings=clip_settings)

        if final_clips is None:
            if progress_callback:
                await self._notify(progress_callback, "Generating clip metadata...", 75)
            final_clips = await self._content_ai.generate_metadata_for_clips(scored_highlights)

        # Fallback: if no AI highlights were generated, create clips from transcript segments
        if not final_clips and transcript_segments:
            if progress_callback:
                await self._notify(progress_callback, "No AI highlights found, creating clips from transcript...", 78)
            final_clips = self._create_fallback_clips(transcript_segments, video_metadata.get("duration", 0), clip_settings=clip_settings)

        if rendered_clips is None:
            if progress_callback:
                await self._notify(progress_callback, f"Rendering {len(final_clips)} clips...", 88)
            rendered_clips = await self.prepare_clip_outputs(
                project_id=project_id,
                video_path=video_path,
                clips=final_clips,
                transcript_segments=transcript_segments,
                output_aspect_ratios=output_aspect_ratios,
                clip_settings=clip_settings,
            )

        if progress_callback:
            await self._notify(progress_callback, "Saving clip analysis...", 95)

        saved_clips = await self._save_rendered_clips(
            project_id=project_id,
            user_id=user_id,
            clips=rendered_clips,
            transcript_segments=transcript_segments,
            analysis=analysis,
            video_metadata=video_metadata,
        )

        if not saved_clips:
            raise CustomException(
                message="Clip generation produced no clips. Check the transcript and highlight detection steps.",
                code="NO_CLIPS_GENERATED",
                status_code=422,
            )

        rendered_count = sum(1 for clip in saved_clips if clip.local_path)
        if rendered_count == 0:
            raise CustomException(
                message="Clip files could not be rendered. Check the FFmpeg video encoder configuration.",
                code="CLIP_RENDER_FAILED",
                status_code=500,
            )

        if progress_callback:
            await self._notify(progress_callback, "Clip generation completed", 100)

        topic_analysis = analysis.get("topic_research", {}) if isinstance(analysis, dict) else {}
        r = {
            "video_id": project_id,
            "project_id": project_id,
            "video": video_metadata,
            "analysis": {
                "title": topic_analysis.get("title", ""),
                "summary": topic_analysis.get("summary", ""),
                "topics": topic_analysis.get("topics", []),
                "entities": topic_analysis.get("entities", []),
                "important_statements": topic_analysis.get("important_statements", []),
                "events": topic_analysis.get("events", []),
                "key_moments": topic_analysis.get("key_moments", []),
                "context_required": topic_analysis.get("context_required", []),
                "current_relevance": topic_analysis.get("current_relevance", ""),
                "research_queries": topic_analysis.get("research_queries", []),
                "sources": topic_analysis.get("sources", []),
                "research_method": topic_analysis.get("research_method", "groq_llm"),
                "understanding": analysis,
            },
            "clips_generated": len(saved_clips),
            "clips": [self._serialize_clip(clip) for clip in saved_clips],
            "understanding": analysis,
        }
        return r

    async def prepare_clip_outputs(
        self,
        project_id: str,
        video_path: str,
        clips: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]] | None = None,
        output_aspect_ratios: list[str] | None = None,
        progress_callback: Any | None = None,
        clip_settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Cut every clip, delegating framing and rendering to ClipCutter."""
        transcript_segments = list(transcript_segments or [])
        if isinstance(output_aspect_ratios, str):
            output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
        # A caller-supplied list is honoured exactly; only the fallback consults
        # the content category, which the clips all share by this point.
        if not output_aspect_ratios:
            category = next(
                (str(c.get("content_category")) for c in clips if c.get("content_category")),
                "unknown",
            )
            output_aspect_ratios = self._content_ai.default_aspect_ratios(category)
        ratios = [r for r in output_aspect_ratios if r in SUPPORTED_ASPECT_RATIOS]
        if not ratios:
            ratios = list(FALLBACK_ASPECT_RATIOS)

        render_errors: list[str] = []

        log.info(
            "Rendering %d clip(s) for project %s into %s (max %d at a time)",
            len(clips), project_id, ", ".join(ratios), MAX_CONCURRENT_CUTS,
        )

        async def notify_status(message: str, percent: int) -> None:
            if progress_callback:
                await self._notify(progress_callback, message, percent)

        # Two clips at a time: each FFmpeg encode already uses several cores, so
        # more workers than this just makes them contend for the same CPU.
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CUTS)
        tracker = _CutProgress(total=len(clips), notify=notify_status)

        async def cut_one(index: int, clip: dict[str, Any]) -> dict[str, Any]:
            clip_copy = dict(clip)
            clip_id = str(clip_copy.get("clip_id") or clip_copy.get("id") or f"clip_{index + 1:03d}")
            clip_copy["clip_id"] = clip_id
            start = float(clip_copy.get("start_time", clip_copy.get("start", 0.0)))
            end = float(clip_copy.get("end_time", clip_copy.get("end", start)))

            request = CutRequest(
                source_path=video_path,
                output_dir=self._output_dir / self._safe_name(project_id),
                clip_id=clip_id,
                start=start,
                end=end,
                aspect_ratios=ratios,
                content_category=str(clip_copy.get("content_category", "unknown")),
                transcript_segments=transcript_segments,
            )

            async with semaphore:
                await tracker.mark_running(clip_id)
                try:
                    # A cutter per clip, not one shared: ClipCutter's
                    # FaceDetector reconfigures the underlying cv2 model per
                    # frame size, and detection runs in a worker thread, so two
                    # concurrent clips sharing one would race on that model.
                    result = await ClipCutter().cut(request)
                except BaseException:
                    await tracker.mark_failed(clip_id)
                    raise

            # A clip that rendered no file at all is a failure to the user even
            # though cut() returned normally, so count it as one.
            if result.rendered:
                await tracker.mark_done(clip_id)
            else:
                await tracker.mark_failed(clip_id)

            render_errors.extend(f"clip={clip_id} {err}" for err in result.errors)

            clip_copy["transcript"] = self._clip_transcript(transcript_segments, start, end)
            clip_copy["scores"] = self._clip_scores(clip_copy, [])
            clip_copy["visual_analysis"] = result.faces
            clip_copy["bounding_boxes"] = result.faces
            clip_copy["crop_tracking"] = result.crop_tracking
            clip_copy["output_files"] = result.output_files
            clip_copy["output_formats"] = {
                ratio: {
                    "target_width": output_dimensions(ratio)[0],
                    "target_height": output_dimensions(ratio)[1],
                    "layout": result.layout,
                    "strategy": result.strategy,
                    "speaker_count": result.speaker_count,
                }
                for ratio in ratios
            }
            clip_copy["duration"] = result.duration
            clip_copy["layout"] = result.layout
            clip_copy["reason"] = str(clip_copy.get("reason") or clip_copy.get("description") or "")
            return clip_copy

        # gather preserves input order regardless of completion order, so the
        # returned clips stay in the ranking the caller sorted them into.
        outcomes = await asyncio.gather(
            *(cut_one(index, clip) for index, clip in enumerate(clips)),
            return_exceptions=True,
        )

        rendered: list[dict[str, Any]] = []
        for index, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                clip_id = str(clips[index].get("clip_id") or clips[index].get("id") or f"clip_{index + 1:03d}")
                # One clip blowing up must not lose the clips that did render.
                log.error("Clip cut failed: clip=%s error=%s", clip_id, outcome)
                render_errors.append(f"clip={clip_id} {outcome}")
                continue
            rendered.append(outcome)

        await tracker.notify_summary()

        if rendered and not any(c.get("output_files", {}).values() for c in rendered):
            raise CustomException(
                message=f"All clip renders failed. First error: {render_errors[0] if render_errors else 'unknown'}",
                code="CLIP_RENDER_FAILED",
                status_code=500,
            )
        return rendered

    async def _save_rendered_clips(
        self,
        project_id: str,
        user_id: str,
        clips: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]],
        analysis: dict[str, Any],
        video_metadata: dict[str, Any],
    ) -> list[GeneratedClip]:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            saved = []
            for clip in clips:
                clip_id = str(clip.get("clip_id", ""))
                start = float(clip.get("start_time", clip.get("start", 0.0)))
                end = float(clip.get("end_time", clip.get("end", start)))
                output_files = clip.get("output_files", {})
                local_path = output_files.get("9:16") or next((path for path in output_files.values() if path), None)
                transcript = self._clip_transcript(transcript_segments, start, end)
                visual_analysis = clip.get("visual_analysis", [])
                clip_analysis = {
                    "clip": clip,
                    "transcript": transcript,
                    "visual_analysis": visual_analysis,
                    "video": video_metadata,
                    "analysis": analysis,
                }
                presigned_url = None
                s3_key = None
                poster_url = None
                s3_keys: dict[str, str] = {}
                if local_path and Path(local_path).exists():
                    presigned_url, s3_key, poster_url, s3_keys = await self._upload_clip_and_thumbnail(
                        local_path, clip_id, user_id, project_id, output_files
                    )
                saved_clip = await repo.create_clip(
                    project_id=project_id,
                    user_id=user_id,
                    title=_sanitize_str(str(clip.get("title") or f"Clip {clip_id}")),
                    description=_sanitize_str(clip.get("description")),
                    start_time=start,
                    end_time=end,
                    duration_seconds=float(clip.get("duration", end - start)),
                    score=float(clip.get("score", 0.0)),
                    scores=_json_dumps(clip.get("scores", {})),
                    content_category=clip.get("content_category", ContentCategory.UNKNOWN.value),
                    status="completed" if local_path else "pending",
                    local_path=local_path,
                    s3_key=s3_key,
                    s3_bucket=self._bucket if presigned_url else None,
                    presigned_url=presigned_url,
                    poster_url=poster_url,
                    transcript=_json_dumps(transcript),
                    visual_analysis=_json_dumps(visual_analysis),
                    bounding_boxes=_json_dumps(clip.get("bounding_boxes", [])),
                    crop_tracking=_json_dumps(clip.get("crop_tracking", {})),
                    output_formats=_json_dumps(clip.get("output_formats", {})),
                    output_files=_json_dumps(output_files),
                    analysis_json=_json_dumps({**clip_analysis, "s3_keys": s3_keys}),
                )
                saved.append(saved_clip)
            return saved

    def _clip_s3_prefix(self, user_id: str, project_id: str, clip_id: str) -> str:
        """Every artefact for one clip lives under one prefix, its own folder."""
        return f"clips/{user_id}/{project_id}/{self._safe_name(clip_id)}"

    async def _upload_clip_and_thumbnail(
        self,
        local_path: str,
        clip_id: str,
        user_id: str,
        project_id: str,
        output_files: dict[str, str] | None = None,
    ) -> tuple[str | None, str | None, str | None, dict[str, str]]:
        """Upload every rendered aspect ratio plus a poster frame to S3.

        Returns ``(presigned_url, s3_key, poster_url, s3_keys_by_ratio)`` where
        the presigned url and key refer to ``local_path`` (the primary ratio).
        Previously only the primary ratio was uploaded, so the other ratios
        existed solely on the local disk and were lost with it.
        """
        prefix = self._clip_s3_prefix(user_id, project_id, clip_id)
        s3_bucket = self._bucket
        try:
            self._s3.create_bucket(s3_bucket)
        except Exception:
            pass

        # Upload every rendered ratio, not just the primary one. Keyed by ratio
        # so one clip's folder holds 9x16.mp4, 1x1.mp4 and so on side by side.
        uploads: dict[str, str] = dict(output_files or {})
        if local_path and not any(
            path == local_path for path in uploads.values()
        ):
            uploads.setdefault("primary", local_path)

        s3_keys: dict[str, str] = {}
        primary_key: str | None = None
        presigned_url: str | None = None

        for ratio, path in uploads.items():
            if not path or not Path(path).exists():
                continue
            key = f"{prefix}/{ratio.replace(':', 'x')}.mp4"
            try:
                await asyncio.to_thread(
                    self._s3.upload_file, s3_bucket, key, path, "video/mp4"
                )
            except Exception as exc:
                log.warning(
                    "S3 upload failed: clip=%s ratio=%s error=%s", clip_id, ratio, exc
                )
                continue
            s3_keys[ratio] = key
            if path == local_path:
                primary_key = key

        if primary_key:
            try:
                presigned_url = self._s3.generate_presigned_url(
                    s3_bucket, primary_key, expires_in=3600
                )
            except Exception as exc:
                log.warning("Presign failed: clip=%s error=%s", clip_id, exc)

        poster_url = None
        if primary_key and local_path:
            thumbnail_path = str(Path(local_path).with_suffix(".jpg"))
            try:
                await self._ffmpeg.extract_frame(local_path, 0.5, thumbnail_path)
                thumb_key = f"{prefix}/thumbnail.jpg"
                await asyncio.to_thread(
                    self._s3.upload_file, s3_bucket, thumb_key, thumbnail_path, "image/jpeg"
                )
                s3_keys["thumbnail"] = thumb_key
                poster_url = self._s3.generate_presigned_url(
                    s3_bucket, thumb_key, expires_in=3600
                )
            except Exception as exc:
                log.warning(f"Thumbnail extraction failed: clip={clip_id} error={exc}")
            finally:
                Path(thumbnail_path).unlink(missing_ok=True)

        return presigned_url, primary_key, poster_url, s3_keys

    async def _video_metadata(self, video_path: str) -> dict[str, Any]:
        info = await self._ffmpeg.get_video_info(video_path)
        streams = info.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type") == "video"), streams[0] if streams else {})
        width = int(stream.get("width", 0) or 0)
        height = int(stream.get("height", 0) or 0)
        divisor = math.gcd(width, height) if width and height else 1
        duration = float((info.get("format") or {}).get("duration", stream.get("duration", 0.0)) or 0.0)
        return {
            "duration": round(duration, 3),
            "width": width,
            "height": height,
            "aspect_ratio": f"{width // divisor}:{height // divisor}" if divisor else "unknown",
        }

    async def _get_project(self, project_id: str, user_id: str) -> Any:
        async with AsyncSessionLocal() as session:
            from clip.repository import ClipRepository as ProjectRepository

            repo = ProjectRepository(session)
            project = await repo.get_project(project_id, user_id)
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)
        return project

    def _output_path(self, project_id: str, clip_id: str, aspect_ratio: str) -> Path:
        safe_project = self._safe_name(project_id)
        safe_clip = self._safe_name(clip_id)
        safe_ratio = aspect_ratio.replace(":", "x")
        path = self._output_dir / safe_project / safe_clip / f"{safe_ratio}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(character if character.isalnum() or character in ("-", "_") else "_" for character in value)

    @staticmethod
    def _clip_transcript(transcript_segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
        """Slice the transcript to a clip, keeping absolute source timestamps.

        Timings stay absolute because the ASS generator rebases them against
        clip_start itself; rebasing here would double-subtract the offset.

        Word timings are carried through. Dropping them (as this used to) made
        every downstream consumer fall back to whole-segment lines: the burner
        lost word-level karaoke, and the editor had nothing to sync against.
        """
        sliced: list[dict[str, Any]] = []
        for segment in transcript_segments:
            seg_start = float(segment.get("start", 0.0))
            seg_end = float(segment.get("end", 0.0))
            if seg_end <= start or seg_start >= end:
                continue

            entry: dict[str, Any] = {
                "start": seg_start,
                "end": seg_end,
                "text": str(segment.get("text", "")),
            }
            if segment.get("speaker"):
                entry["speaker"] = segment["speaker"]

            words = []
            for word in segment.get("words") or []:
                w_start = float(word.get("start", 0.0))
                w_end = float(word.get("end", w_start))
                if w_end <= start or w_start >= end:
                    continue
                text = str(word.get("word", word.get("text", ""))).strip()
                if not text:
                    continue
                words.append({"start": w_start, "end": w_end, "word": text})
            if words:
                entry["words"] = words
            sliced.append(entry)
        return sliced

    @staticmethod
    def _clip_captions(
        transcript: list[dict[str, Any]],
        start: float,
        end: float,
        ai_cues: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Word-level captions on the *clip's own* timeline, for the editor.

        The rendered mp4 starts at zero while `transcript` carries absolute
        source timestamps, so a player comparing its currentTime against the
        stored transcript never matches a single word. Rebasing belongs here,
        once, next to the burner's own rebasing - not in each client.
        """
        from subtitle_styling.emoji_annotator import annotate_caption_words

        duration = max(0.0, end - start)
        words: list[dict[str, Any]] = []
        for segment in transcript:
            raw_words = segment.get("words") or [
                {
                    "start": segment.get("start", 0.0),
                    "end": segment.get("end", 0.0),
                    "word": segment.get("text", ""),
                }
            ]
            for word in raw_words:
                w_start = float(word.get("start", 0.0))
                w_end = float(word.get("end", w_start))
                text = str(word.get("word", word.get("text", ""))).strip()
                if not text or w_end <= start or w_start >= end:
                    continue
                words.append({
                    "text": text,
                    "start": round(min(max(0.0, w_start - start), duration), 3),
                    "end": round(min(max(0.0, w_end - start), duration), 3),
                    "speaker": segment.get("speaker") or "Speaker",
                })

        words.sort(key=lambda w: w["start"])
        emoji_by_index, emphasis_indices = annotate_caption_words(words, ai_cues)
        for index, word in enumerate(words):
            if index in emoji_by_index:
                word["emoji"] = emoji_by_index[index]
            if index in emphasis_indices:
                word["emphasis"] = True
        return words

    @staticmethod
    def _clip_scores(clip: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, float]:
        raw_scores = clip.get("scores", {}) if isinstance(clip.get("scores", {}), dict) else {}

        def normalized(value: Any) -> float:
            try:
                score = float(value)
            except (TypeError, ValueError):
                return 0.0
            return min(1.0, max(0.0, score / 100.0 if score > 1.0 else score))

        visual_scores = [
            normalized(frame.get("visual_quality", {}).get("score", 0.0))
            for frame in frames
            if isinstance(frame.get("visual_quality"), dict)
        ]
        visual_quality = sum(visual_scores) / len(visual_scores) if visual_scores else 0.0
        overall = normalized(clip.get("score", 0.0))

        # The scorer's virality breakdown lives under scoring_factors and was
        # never surfaced, so every client that asked for hook_score or
        # engagement_score fell back to the overall score and showed the same
        # number three times. Each component is scored out of 25, the total out
        # of 100; they are normalised here like every other score.
        factors = clip.get("scoring_factors", {}) if isinstance(clip.get("scoring_factors"), dict) else {}
        virality = factors.get("virality_scores", {}) if isinstance(factors.get("virality_scores"), dict) else {}

        def component(key: str) -> float:
            try:
                return round(min(1.0, max(0.0, float(virality.get(key, 0.0)) / 25.0)), 4)
            except (TypeError, ValueError):
                return 0.0

        return {
            "hook_score": component("hook_score"),
            "engagement_score": component("engagement_score"),
            "value_score": component("value_score"),
            "shareability_score": component("shareability_score"),
            "virality_score": normalized(virality.get("virality_score", overall * 100)),
            "relevance": normalized(raw_scores.get("relevance", overall)),
            "importance": normalized(raw_scores.get("importance", overall)),
            "emotional_impact": normalized(raw_scores.get("emotional_impact", overall)),
            "information_value": normalized(raw_scores.get("information_value", overall)),
            "standalone_context": normalized(raw_scores.get("standalone_context", overall)),
            "social_media_value": normalized(raw_scores.get("social_media_value", overall)),
            "current_relevance": normalized(raw_scores.get("current_relevance", overall)),
            "visual_quality": round(visual_quality, 4),
            "clip_quality": round(overall, 4),
        }

    @staticmethod
    def _bounding_boxes(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        boxes = []
        for frame in frames:
            for subject in (
                list(frame.get("subjects", []))
                + list(frame.get("faces", []))
                + list(frame.get("objects", []))
            ):
                if subject.get("bounding_box"):
                    boxes.append({
                        "timestamp": frame.get("timestamp", 0.0),
                        "frame_width": frame.get("frame_width", 0),
                        "frame_height": frame.get("frame_height", 0),
                        "label": subject.get("label", "subject"),
                        "confidence": subject.get("confidence", 0.0),
                        "bounding_box": subject.get("bounding_box"),
                    })
        return boxes

    @staticmethod
    def list_social_platforms() -> list[dict[str, Any]]:
        platforms = []
        for platform in SocialPlatform:
            defaults = SOCIAL_PLATFORM_DEFAULTS[platform.value]
            platforms.append({
                "platform": platform.value,
                "aspect_ratio": defaults["aspect_ratio"],
                "dimensions": defaults["dimensions"],
                "default_style": defaults["subtitle_style"],
                "max_duration": defaults["max_duration"],
                "emoji_enabled": defaults["emoji_enabled"],
            })
        return platforms

    async def _transcribe_if_missing(
        self,
        project_id: str,
        video_path: str,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
    ) -> list[dict[str, Any]]:
        from transcription.service import WhisperXTranscriptionService
        from transcription.schema import TranscriptionRequest

        if progress_callback:
            await self._notify(progress_callback, "Transcribing audio for export...", 0)

        transcribe_service = WhisperXTranscriptionService()
        request = TranscriptionRequest(
            input_path=video_path,
            model_size="small",
            language=None,
            chunk_duration=1200,
            chunk_overlap=10,
            word_timestamps=True,
            diarization=True,
            output_format="all",
            device="cpu",
        )

        def _progress(percent: float, message: str):
            if progress_callback:
                asyncio.create_task(self._notify(progress_callback, f"Transcription: {message}", int(percent)))

        result = await transcribe_service.transcribe(request, progress_callback=_progress)
        segments = getattr(result, "segments", [])
        if progress_callback:
            await self._notify(progress_callback, "Transcription complete", 100)
        return list(segments)

    def _create_fallback_clips(self, transcript_segments: list[dict], video_duration: float, clip_settings: dict[str, Any] | None = None) -> list[dict]:
        """Create fallback clips from transcript segments when AI highlight detection fails."""
        if not transcript_segments:
            return []
        
        clips = []
        settings = clip_settings or {}
        MIN_CLIP_DURATION = float(settings.get("min_clip_duration") or 20.0)
        MAX_CLIP_DURATION = float(settings.get("max_clip_duration") or 60.0)
        TARGET_DURATION = float(settings.get("target_clip_duration") or 32.0)
        MAX_CLIPS = int(settings.get("max_clips") or max(1, (video_duration / 3600.0) * 6 + 1 if video_duration > 0 else 10))
        
        current_clip_start = None
        current_clip_text = ""
        current_speaker = None
        
        for segment in transcript_segments:
            seg_start = float(segment.get("start", 0))
            seg_end = float(segment.get("end", 0))
            seg_text = segment.get("text", "").strip()
            seg_speaker = segment.get("speaker")
            
            if not seg_text:
                continue
            
            # Start new clip if speaker changes or clip would be too long
            if current_clip_start is None:
                current_clip_start = seg_start
                current_clip_text = seg_text
                current_speaker = seg_speaker
            elif seg_speaker != current_speaker or (seg_end - current_clip_start) >= MAX_CLIP_DURATION:
                # Finalize current clip if it meets minimum duration
                if (current_clip_start is not None and 
                    len(current_clip_text) > 50 and 
                    seg_start - current_clip_start >= MIN_CLIP_DURATION):
                    clips.append({
                        "clip_id": f"fallback_{len(clips) + 1:03d}",
                        "title": current_clip_text[:60] + ("..." if len(current_clip_text) > 60 else ""),
                        "description": current_clip_text[:200],
                        "start_time": current_clip_start,
                        "end_time": min(seg_start, current_clip_start + TARGET_DURATION),
                        "duration": min(TARGET_DURATION, seg_start - current_clip_start),
                        "score": 50.0,
                        "content_category": "unknown",
                        "reason": "Fallback clip from transcript segment",
                        "scores": {},
                        "transcript_excerpt": current_clip_text[:500],
                        "speakers": [current_speaker] if current_speaker else [],
                    })
                # Start new clip
                current_clip_start = seg_start
                current_clip_text = seg_text
                current_speaker = seg_speaker
            else:
                current_clip_text += " " + seg_text
        
        # Don't forget the last clip
        if (current_clip_start is not None and 
            len(current_clip_text) > 50 and 
            video_duration - current_clip_start >= MIN_CLIP_DURATION):
            clips.append({
                "clip_id": f"fallback_{len(clips) + 1:03d}",
                "title": current_clip_text[:60] + ("..." if len(current_clip_text) > 60 else ""),
                "description": current_clip_text[:200],
                "start_time": current_clip_start,
                "end_time": min(video_duration, current_clip_start + TARGET_DURATION),
                "duration": min(TARGET_DURATION, video_duration - current_clip_start),
                "score": 50.0,
                "content_category": "unknown",
                "reason": "Fallback clip from transcript segment",
                "scores": {},
                "transcript_excerpt": current_clip_text[:500],
                "speakers": [current_speaker] if current_speaker else [],
            })
        
        # Limit to reasonable number of clips
        return clips[:MAX_CLIPS]

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

    def _serialize_clip(self, clip: GeneratedClip | None) -> dict | None:
        if not clip:
            return None
        analysis = self._loads(clip.analysis_json, {})
        transcript = self._loads(clip.transcript, [])
        ai_cues = analysis.get("clip", {}).get("ai_emoji_cues", []) if isinstance(analysis, dict) else []
        return {
            "video_id": clip.project_id,
            "clip_id": analysis.get("clip", {}).get("clip_id", clip.id),
            "id": clip.id,
            "project_id": clip.project_id,
            "user_id": clip.user_id,
            "title": clip.title,
            "description": clip.description,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "duration_seconds": clip.duration_seconds,
            "timestamps": {
                "start": clip.start_time,
                "end": clip.end_time,
                "duration": clip.duration_seconds,
            },
            "reason": analysis.get("clip", {}).get("reason", ""),
            "score": clip.score,
            "scores": self._loads(clip.scores, {}),
            "content_category": clip.content_category,
            "presigned_url": clip.presigned_url,
            "poster_url": clip.poster_url,
            "local_path": clip.local_path,
            "status": clip.status,
            "subtitle_style_id": clip.subtitle_style_id,
            "burned_subtitle_path": clip.burned_subtitle_path,
            "burned_presigned_url": clip.burned_presigned_url,
            "transcript": transcript,
            # Absolute-time transcript above, clip-relative words below: the
            # player needs the latter, the burner needs the former.
            "captions": self._clip_captions(transcript, clip.start_time, clip.end_time, ai_cues),
            "visual_analysis": self._loads(clip.visual_analysis, []),
            "bounding_boxes": self._loads(clip.bounding_boxes, []),
            "crop_tracking": self._loads(clip.crop_tracking, {}),
            "output_formats": self._loads(clip.output_formats, {}),
            "output_files": self._loads(clip.output_files, {}),
            "analysis_json": analysis,
            "created_at": clip.created_at.isoformat() if clip.created_at else None,
        }

    @staticmethod
    def _loads(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback

    async def _notify(self, cb, message: str, percent: int) -> None:
        if cb:
            try:
                result = cb(message, percent, None)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log.debug(f"Progress notify failed: {exc}")
