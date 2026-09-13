from __future__ import annotations

import asyncio
import json
import math
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
from video_processor.ffmpeg_service import FFmpegService

settings = get_settings()
log = get_logger(__name__)


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
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()
        self._s3 = S3()
        self._bucket = settings.S3_BUCKET_NAME
        self._content_ai = ContentIntelligenceService()
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
            word_snapping=burn_request.get("word_snapping", True),
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
    ) -> dict:
        project = await self._get_project(project_id, user_id)
        video_path = project.local_path
        if not video_path or not Path(video_path).exists():
            raise CustomException(message="Video file not found on disk", code="VIDEO_MISSING", status_code=404)

        video_metadata = await self._video_metadata(video_path)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = await repo.list_clips(project_id, user_id)

        if not clips:
            raise CustomException(message="No clips found for project", code="NO_CLIPS", status_code=404)

        sorted_clips = sorted(clips, key=lambda c: c.score, reverse=True)
        if max_clips:
            sorted_clips = sorted_clips[:max_clips]

        transcript_segments = []
        analysis_json = {}
        for clip in sorted_clips:
            if clip.transcript:
                transcript_segments = json.loads(clip.transcript) if clip.transcript else []
                break
        if not transcript_segments:
            transcript_segments = await self._transcribe_if_missing(project_id, video_path, progress_callback)

        from subtitle_styling.service import SubtitleStylingService
        styling = SubtitleStylingService()

        from content_intelligence.service import ContentIntelligenceService
        content_ai = ContentIntelligenceService()

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
                    candidate_visual_analysis=json.loads(clip.visual_analysis or "{}"),
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
                        burned_path = await styling.burn_subtitles(
                            video_path=clip.local_path or platform_path,
                            clip_start=s,
                            clip_end=e,
                            style_type=effective_style,
                            custom_config=custom_config,
                            title_text=clip.title,
                            enable_watermark=watermark_enabled,
                            transcript_segments=clip_transcript,
                            word_snapping=True,
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
        candidate_visual_analysis: dict[str, list[dict[str, Any]]] | None = None,
        rendered_clips: list[dict[str, Any]] | None = None,
        output_aspect_ratios: list[str] | None = None,
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
            )

        if scored_highlights is None:
            scored_highlights = await self._content_ai.score_highlights(highlights, analysis)

        if final_clips is None:
            if progress_callback:
                await self._notify(progress_callback, "Generating clip metadata...", 75)
            final_clips = await self._content_ai.generate_metadata_for_clips(scored_highlights)

        # Fallback: if no AI highlights were generated, create clips from transcript segments
        if not final_clips and transcript_segments:
            if progress_callback:
                await self._notify(progress_callback, "No AI highlights found, creating clips from transcript...", 78)
            final_clips = self._create_fallback_clips(transcript_segments, video_metadata.get("duration", 0))

        if candidate_visual_analysis is None:
            if progress_callback:
                await self._notify(progress_callback, "Analyzing candidate clip frames...", 80)
            candidate_visual_analysis = await self._content_ai.analyze_candidate_clips(
                video_path,
                final_clips,
                max_frames_per_clip=settings.CANDIDATE_MAX_FRAMES,
                frame_interval=settings.CANDIDATE_FRAME_INTERVAL,
            )

        if rendered_clips is None:
            if progress_callback:
                await self._notify(progress_callback, f"Rendering {len(final_clips)} clips...", 88)
            rendered_clips = await self.prepare_clip_outputs(
                project_id=project_id,
                video_path=video_path,
                clips=final_clips,
                transcript_segments=transcript_segments,
                candidate_visual_analysis=candidate_visual_analysis,
                output_aspect_ratios=output_aspect_ratios,
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
        return {
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

    async def prepare_clip_outputs(
        self,
        project_id: str,
        video_path: str,
        clips: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]] | None = None,
        candidate_visual_analysis: dict[str, list[dict[str, Any]]] | None = None,
        output_aspect_ratios: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        video_info = await self._ffmpeg.get_video_info(video_path)
        streams = video_info.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type") == "video"), streams[0] if streams else {})
        if not stream or not stream.get("width") or not stream.get("height"):
            raise CustomException(message="Source video dimensions are unavailable", code="VIDEO_DIMENSIONS_UNAVAILABLE", status_code=400)

        source_width = int(stream["width"])
        source_height = int(stream["height"])
        transcript_segments = list(transcript_segments or [])
        candidate_visual_analysis = candidate_visual_analysis or {}
        if isinstance(output_aspect_ratios, str):
            output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
        ratios = output_aspect_ratios or self._content_ai.default_aspect_ratios()
        rendered: list[dict[str, Any]] = []

        for index, clip in enumerate(clips):
            clip_copy = dict(clip)
            clip_id = str(clip_copy.get("clip_id") or clip_copy.get("id") or f"clip_{index + 1:03d}")
            clip_copy["clip_id"] = clip_id
            start = float(clip_copy.get("start_time", clip_copy.get("start", 0.0)))
            end = float(clip_copy.get("end_time", clip_copy.get("end", start)))
            duration = max(0.0, end - start)
            frames = list(candidate_visual_analysis.get(clip_id) or candidate_visual_analysis.get(str(index)) or [])
            output_formats = self._content_ai.build_output_formats(frames, source_width, source_height, ratios)
            output_files: dict[str, str] = {}

            for aspect_ratio, output_config in output_formats.items():
                output_path = self._output_path(project_id, clip_id, aspect_ratio)
                try:
                    await self._ffmpeg.crop_with_tracking(
                        input_path=video_path,
                        output_path=str(output_path),
                        start_time=start,
                        duration=duration,
                        crop_tracking=output_config.get("crop_tracking", []),
                        target_width=int(output_config["target_width"]),
                        target_height=int(output_config["target_height"]),
                        source_width=source_width,
                        source_height=source_height,
                    )
                    output_files[aspect_ratio] = str(output_path)
                except Exception as exc:
                    log.warning(f"Clip render failed: clip={clip_id} format={aspect_ratio} error={exc}")
                    output_files[aspect_ratio] = ""

            clip_copy["transcript"] = self._clip_transcript(transcript_segments=transcript_segments, start=start, end=end)
            clip_copy["scores"] = self._clip_scores(clip_copy, frames)
            clip_copy["visual_analysis"] = frames
            clip_copy["bounding_boxes"] = self._bounding_boxes(frames)
            clip_copy["crop_tracking"] = {
                aspect_ratio: output_formats[aspect_ratio].get("crop_tracking", [])
                for aspect_ratio in output_formats
            }
            clip_copy["output_formats"] = output_formats
            clip_copy["output_files"] = output_files
            clip_copy["duration"] = duration
            clip_copy["reason"] = str(clip_copy.get("reason") or clip_copy.get("description") or "")
            rendered.append(clip_copy)

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
                if local_path and Path(local_path).exists():
                    presigned_url, s3_key, poster_url = await self._upload_clip_and_thumbnail(
                        local_path, clip_id, user_id, project_id
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
                    analysis_json=_json_dumps(clip_analysis),
                )
                saved.append(saved_clip)
            return saved

    async def _upload_clip_and_thumbnail(
        self,
        local_path: str,
        clip_id: str,
        user_id: str,
        project_id: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Upload clip video and thumbnail to S3, returning (presigned_url, s3_key, poster_url)."""
        s3_key = f"clips/{user_id}/{project_id}/{clip_id}.mp4"
        s3_bucket = self._bucket
        try:
            self._s3.create_bucket(s3_bucket)
        except Exception:
            pass

        presigned_url = None
        poster_url = None
        try:
            with open(local_path, "rb") as f:
                file_bytes = f.read()
            self._s3.put_object(s3_bucket, s3_key, file_bytes)
            presigned_url = self._s3.generate_presigned_url(s3_bucket, s3_key, expires_in=3600)
        except Exception as exc:
            log.warning(f"S3 upload failed for clip: clip={clip_id} error={exc}")
            s3_key = None

        if presigned_url:
            thumbnail_path = str(Path(local_path).with_suffix(".jpg"))
            try:
                await self._ffmpeg.extract_frame(local_path, 0.5, thumbnail_path)
                thumb_key = f"clips/{user_id}/{project_id}/{clip_id}_thumb.jpg"
                with open(thumbnail_path, "rb") as f:
                    thumb_bytes = f.read()
                self._s3.put_object(s3_bucket, thumb_key, thumb_bytes)
                poster_url = self._s3.generate_presigned_url(s3_bucket, thumb_key, expires_in=3600)
            except Exception as exc:
                log.warning(f"Thumbnail extraction failed: clip={clip_id} error={exc}")

        return presigned_url, s3_key, poster_url

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
        return [
            {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": str(segment.get("text", "")),
                **({"speaker": segment["speaker"]} if segment.get("speaker") else {}),
            }
            for segment in transcript_segments
            if float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
        ]

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
        return {
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

    def _create_fallback_clips(self, transcript_segments: list[dict], video_duration: float) -> list[dict]:
        """Create fallback clips from transcript segments when AI highlight detection fails."""
        if not transcript_segments:
            return []
        
        clips = []
        MIN_CLIP_DURATION = 20.0
        MAX_CLIP_DURATION = 90.0
        TARGET_DURATION = 45.0
        
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
        max_clips = int((video_duration / 3600.0) * 6) + 1 if video_duration > 0 else 10
        return clips[:max_clips]

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

    def _local_to_url(self, local_path: str | None) -> str | None:
        """Convert a local clip file path to a static URL fallback."""
        if not local_path:
            return None
        try:
            rel = Path(local_path).resolve().relative_to(Path(settings.CLIP_OUTPUT_DIR).resolve())
            return f"/static/clips/{rel.as_posix()}"
        except (ValueError, OSError):
            return None

    def _serialize_clip(self, clip: GeneratedClip | None) -> dict | None:
        if not clip:
            return None
        return {
            "video_id": clip.project_id,
            "clip_id": self._loads(clip.analysis_json, {}).get("clip", {}).get("clip_id", clip.id),
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
            "reason": self._loads(clip.analysis_json, {}).get("clip", {}).get("reason", "") if clip.analysis_json else "",
            "score": clip.score,
            "scores": self._loads(clip.scores, {}),
            "content_category": clip.content_category,
            "presigned_url": clip.presigned_url or self._local_to_url(clip.local_path),
            "poster_url": clip.poster_url,
            "local_path": clip.local_path,
            "status": clip.status,
            "subtitle_style_id": clip.subtitle_style_id,
            "burned_subtitle_path": clip.burned_subtitle_path,
            "burned_presigned_url": clip.burned_presigned_url,
            "transcript": self._loads(clip.transcript, []),
            "visual_analysis": self._loads(clip.visual_analysis, []),
            "bounding_boxes": self._loads(clip.bounding_boxes, []),
            "crop_tracking": self._loads(clip.crop_tracking, {}),
            "output_formats": self._loads(clip.output_formats, {}),
            "output_files": self._loads(clip.output_files, {}),
            "analysis_json": self._loads(clip.analysis_json, {}),
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
