from __future__ import annotations

import asyncio
import dataclasses
import functools
import json
import os
import shutil
import time
from pathlib import Path
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.logging_config import get_logger
from core.config import get_settings

from clip.source_video import ensure_local_copy
from clip.youtube_service import YouTubeService
from audio.extraction.service import AudioExtractionService
from audio.enhancement.service import AudioService
from audio.enhancement.schema import AudioEnhanceRequest
from transcription.service import WhisperXTranscriptionService
from transcription.schema import TranscriptionRequest
from transcription.language import spoken_language
from transcription.punctuate import punctuate_captions
from transcription.transliterate import CAPTION_SCRIPTS, romanize_captions, wants_roman
from broll.cutaways import plan_project_broll
from motion.service import plan_project_motion
from feature_flags.registry import BROLL_CUTAWAYS
from feature_flags.service import FeatureFlagService
from clip.repository import ClipRepository
from clip.model import ProjectStatus
from clip_generation.model import SOCIAL_PLATFORM_DEFAULTS, SocialPlatform
from clip_generation.schema import SocialExportRequest, SocialExportResponse
from clip_generation.service import ClipService
from depth_captions.pipeline import create_depth_captions_job
from depth_captions.schema import DepthCaptionRequest, StylePreset, DepthMode, TranscriptSegment
from core.database import AsyncSessionLocal

from pipeline.model import PipelineStepType, StepStatus
from pipeline.schema import PipelineStartRequest
from core.exceptions import CustomException
from notifications.service import notify_pipeline_outcome
from referral.service import refresh_referrals_of
from subscription.entitlements import Entitlements
from subscription.service import (
    InsufficientCreditsError,
    SubscriptionService,
    aspect_ratio_not_entitled,
    require_caption_style,
    resolve_output_aspect_ratios,
    require_hook_transition,
)
from video_processor.geometry import SUPPORTED_ASPECT_RATIOS
from hook_transitions.schema import HookTransitionConfig
from usage.context import RunBudget, llm_scope
from jobs.queue import Job, get_queue, handler, uses_workers
from subtitle_styling.templates import DEFAULT_STYLE

log = get_logger(__name__)

# Ledger reference types of a project's first run: its charge and its refunds.
RUN_CHARGE_REFERENCE = "video_project"
RUN_REFUND_REFERENCE = "video_project_refund"


ProgressCallback = Callable[[str, int, Optional[str], Optional[str], Optional[str]], None]

# Minimum gap between step-progress writes to the database. Step transitions
# always write; the chatty in-step updates are sampled.
PROGRESS_WRITE_INTERVAL_SECONDS = 2.0
INTERRUPTED_ERROR = "Processing was interrupted by a server restart. Resume to continue."


async def fail_interrupted_pipelines() -> None:
    """Fail runs left open by a previous process, so they do not show as processing forever.

    Only for in-process runs: with workers, an open run is still running on
    another machine, or its job will be redelivered and resumed.
    """
    if uses_workers():
        return
    from pipeline.repository import PipelineRepository

    async with AsyncSessionLocal() as session:
        project_ids = await PipelineRepository(session).fail_unfinished_pipelines(INTERRUPTED_ERROR)
        clip_repo = ClipRepository(session)
        for project_id in project_ids:
            await clip_repo.update_project_status(project_id, ProjectStatus.FAILED)
    if project_ids:
        log.warning("Marked %d interrupted pipeline(s) failed: %s", len(project_ids), project_ids)


def _clip_list(label: str, clips: list[dict]) -> str:
    """``3 highlight(s): 12.3-41.0s 0.82 "Title" ; ...`` for a step summary line."""
    entries = [
        f"{float(c.get('start_time', c.get('start', 0))):.1f}-{float(c.get('end_time', c.get('end', 0))):.1f}s "
        f"{float(c.get('score') or 0):.2f} \"{c.get('title') or ''}\""
        for c in clips
    ]
    return f"{len(clips)} {label}" + (": " + " ; ".join(entries) if entries else "")


def _read_audio_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class PipelineOrchestrator:
    def __init__(
        self,
        project_id: str,
        user_id: str,
        url: str,
        selected_steps: list[PipelineStepType],
        audio_config: Optional[dict] = None,
        progress_callback: Optional[ProgressCallback] = None,
        watermark_enabled: bool = True,
        output_aspect_ratios: list[str] | None = None,
        resume: bool = False,
        clip_settings: Optional[dict] = None,
        is_pro: bool = False,
    ) -> None:
        log.debug(
            "Pipeline orchestrator initialized",
            extra={
                "project_id": project_id,
                "user_id": user_id,
                "url": url,
                "selected_steps": [s.value for s in selected_steps],
                "watermark_enabled": watermark_enabled,
                "resume": resume,
                "is_pro": is_pro,
            },
        )
        self.project_id = project_id
        self.user_id = user_id
        self.url = url
        self.selected_steps = selected_steps
        self.audio_config = audio_config or {}
        self.progress_callback = progress_callback
        self.watermark_enabled = watermark_enabled
        # Empty means "decide from the content category", which is only known
        # once classification has run -- so it stays empty here and the clip
        # service resolves it at render time.
        self.output_aspect_ratios = list(output_aspect_ratios or [])
        self.clip_settings = clip_settings or {}
        self.hook_transition = self._hook_transition(self.clip_settings)
        # Decides which AI provider every text step runs on. Resolved once at
        # the route from the user's active subscription, so a plan change
        # mid-run cannot switch providers half way through.
        self.is_pro = is_pro
        self._resume = resume
        self._youtube = YouTubeService()
        self._audio_extractor = AudioExtractionService()
        self._audio_service = AudioService()
        self._transcription_service = WhisperXTranscriptionService()
        self._clip_service = ClipService(is_pro=is_pro)
        self._cancel = False
        self._local_path: str | None = None
        self._step_statuses: dict[str, str] = {}
        self._current_step: str | None = None
        self._last_progress_write: float = 0.0
        # asyncio keeps only a weak reference to a running task, so a
        # fire-and-forget progress write can be collected before it commits.
        self._background_tasks: set[asyncio.Task] = set()
        # Cap set once the source's length is known, at the start of run().
        self._budget = RunBudget(cap_usd=0.0)
        # Loudness cues and the visual timeline need no transcript, so they
        # start beside transcription and topic research picks them up.
        self._media_signals: asyncio.Task | None = None

    def cancel(self) -> None:
        self._cancel = True
        log.warning(
            "Pipeline cancel requested",
            extra={"project_id": self.project_id, "user_id": self.user_id},
        )

    @property
    def is_cancelled(self) -> bool:
        return self._cancel

    async def _cancel_requested(self) -> bool:
        """Local cancel, or the run's database flag, which any process can set."""
        if not self._cancel:
            try:
                async with AsyncSessionLocal() as session:
                    self._cancel = await _pipeline_repository(session).is_cancel_requested(self.project_id)
            except Exception as exc:
                log.warning("Could not read the cancel flag: project=%s error=%s", self.project_id, exc)
        return self._cancel

    async def run(self) -> dict:
        results: dict[str, Any] = {}
        pipeline_started = time.monotonic()
        step_order = [
            PipelineStepType.AUDIO_EXTRACTION,
            PipelineStepType.AI_NOISE_CANCELLATION,
            PipelineStepType.TRANSCRIPTION,
            PipelineStepType.TOPIC_RESEARCH,
            PipelineStepType.VISUAL_ANALYSIS,
            PipelineStepType.CONTENT_CLASSIFICATION,
            PipelineStepType.HIGHLIGHT_DETECTION,
            PipelineStepType.SCORING,
            PipelineStepType.METADATA_GENERATION,
            PipelineStepType.ASPECT_RATIO_RENDER,
            PipelineStepType.CLIP_GENERATION,
            PipelineStepType.SUBTITLE_STYLING,
            PipelineStepType.BURN_IN_EXPORT,
            PipelineStepType.DEPTH_CAPTIONS,
        ]

        if self._resume:
            await self._load_step_statuses()
        await self._size_budget()

        log.info(
            "Pipeline started",
            extra={
                "project_id": self.project_id,
                "user_id": self.user_id,
                "url": self.url,
                "selected_steps": [s.value for s in self.selected_steps],
                "total_steps": len(step_order),
            },
        )

        try:
            for step in step_order:
                if await self._cancel_requested():
                    log.warning(
                        "Pipeline cancelled",
                        extra={"project_id": self.project_id, "user_id": self.user_id, "step": step.value},
                    )
                    break
                if step not in self.selected_steps:
                    log.debug(
                        "Step skipped (not selected)",
                        extra={"project_id": self.project_id, "step": step.value},
                    )
                    continue

                if self._resume and self._step_statuses.get(step.value) == "completed":
                    restored = await self._restore_step_artifact(step)
                    if restored is not None:
                        results[step.value] = restored
                        self._notify(
                            f"Skipping completed step: {step.value}", 100,
                            step=step.value, step_status="completed",
                        )
                        continue

                await asyncio.sleep(0)

                position = self.selected_steps.index(step) + 1 if step in self.selected_steps else 0
                total = len(self.selected_steps)
                step_started = time.monotonic()
                log.info(
                    "STEP %d/%d START %s",
                    position, total, step.value,
                    extra={"project_id": self.project_id, "step": step.value},
                )

                try:
                    await self._mark_step_running(step)
                    result = await self._execute_step(step, results)
                    results[step.value] = result
                    await self._mark_step_completed(step, result)
                    log.info(
                        "STEP %d/%d OK    %s in %.1fs — %s",
                        position, total, step.value, time.monotonic() - step_started,
                        self._summarize_step(step, result),
                        extra={
                            "project_id": self.project_id,
                            "step": step.value,
                            "elapsed_seconds": round(time.monotonic() - step_started, 2),
                        },
                    )
                except Exception as exc:
                    log.error(
                        "STEP %d/%d FAIL  %s after %.1fs: %s",
                        position, total, step.value, time.monotonic() - step_started, exc,
                        extra={
                            "project_id": self.project_id,
                            "step": step.value,
                            "error_type": type(exc).__name__,
                            "elapsed_seconds": round(time.monotonic() - step_started, 2),
                        },
                        exc_info=True,
                    )
                    await self._mark_step_failed(step, str(exc))
                    raise
                await asyncio.sleep(0)

            log.info(
                "PIPELINE %s — %d/%d step(s) in %.1fs, AI spend $%.4f",
                "CANCELLED" if self._cancel else "COMPLETE",
                len(results), len(self.selected_steps),
                time.monotonic() - pipeline_started,
                self._budget.spent_usd,
                extra={
                    "project_id": self.project_id,
                    "user_id": self.user_id,
                    "completed_steps": ",".join(results.keys()),
                    "elapsed_seconds": round(time.monotonic() - pipeline_started, 2),
                },
            )
            if self._cancel:
                await self._mark_pipeline_failed("Pipeline cancelled by user")
            else:
                await self._mark_pipeline_completed()
        except Exception as exc:
            await self._mark_pipeline_failed(str(exc))
            raise
        finally:
            if self._media_signals is not None and not self._media_signals.done():
                self._media_signals.cancel()
            # Cut clips are deleted as soon as they reach S3, and later renders
            # fetch them back from there. This sweeps whatever is left (cuts
            # that failed to upload, aborted renders) on every outcome.
            await self._cleanup_local_clips()
        return results

    @staticmethod
    def _hook_transition(clip_settings: dict) -> HookTransitionConfig | None:
        """The run's hook-transition choice; an invalid one falls back to Auto.

        Validated here, before any work, so a bad value is logged once rather
        than failing every clip's burn at the end of the run.
        """
        raw = clip_settings.get("hook_transition")
        if not raw:
            return None
        try:
            return HookTransitionConfig.model_validate(raw)
        except ValueError as exc:
            log.warning("Ignoring invalid hook_transition setting, using Auto: %s", exc)
            return None

    async def _cleanup_local_clips(self) -> None:
        """Delete this project's local render directory after the run.

        Everything worth keeping is in S3 by now. Failing to clean up must never
        fail the pipeline, so all errors here are logged and swallowed.
        """
        from core.config import get_settings

        try:
            safe_project = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in self.project_id
            )
            output_dir = Path(get_settings().CLIP_OUTPUT_DIR) / safe_project
            if not output_dir.exists():
                return
            freed = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
            await asyncio.to_thread(shutil.rmtree, output_dir, True)
            log.info(
                "Cleaned up local clip renders, freed %.1fMB",
                freed / (1024 * 1024),
                extra={"project_id": self.project_id, "path": str(output_dir)},
            )
        except Exception as exc:
            log.warning(
                "Local clip cleanup failed: project=%s error=%s", self.project_id, exc
            )

    @staticmethod
    def _summarize_step(step: PipelineStepType, result: Any) -> str:
        """One-line outcome per step, so the log says what a step produced.

        Previously every step logged only "Completed <name>", which said nothing
        about whether it had actually found anything.
        """
        if not isinstance(result, dict):
            return "done"
        try:
            if step == PipelineStepType.AUDIO_EXTRACTION:
                extraction = result.get("extraction_result", {})
                return f"{extraction.get('duration_seconds', 0):.0f}s audio"
            if step == PipelineStepType.TRANSCRIPTION:
                transcription = result.get("transcription_result")
                if hasattr(transcription, "model_dump"):
                    transcription = transcription.model_dump()
                segments = (transcription or {}).get("segments", []) if isinstance(transcription, dict) else []
                speakers = {s.get("speaker") for s in segments if s.get("speaker")}
                return f"{len(segments)} segment(s), {len(speakers)} speaker(s)"
            if step == PipelineStepType.TOPIC_RESEARCH:
                research = result.get("topic_research", {})
                return f"topic={research.get('title', 'unknown')!r}"
            if step == PipelineStepType.CONTENT_CLASSIFICATION:
                return f"category={result.get('classification', {}).get('category', 'unknown')}"
            if step == PipelineStepType.HIGHLIGHT_DETECTION:
                return _clip_list("highlight(s)", result.get("highlights", []))
            if step == PipelineStepType.SCORING:
                return _clip_list("scored", result.get("scored_highlights", []))
            if step == PipelineStepType.METADATA_GENERATION:
                return _clip_list("clip(s) planned", result.get("final_clips", []))
            if step == PipelineStepType.ASPECT_RATIO_RENDER:
                rendered = result.get("rendered_clips", []) or []
                files = sum(1 for c in rendered for path in (c.get("output_files") or {}).values() if path)
                return f"{len(rendered)} clip(s), {files} file(s)"
            if step == PipelineStepType.CLIP_GENERATION:
                return f"{result.get('clips_generated', 0)} clip(s) saved"
            if step == PipelineStepType.BURN_IN_EXPORT:
                return f"{len(result.get('burned_clips', []))} burned"
        except Exception:  # never let logging break the pipeline
            return "done"
        return "done"

    async def _execute_step(self, step: PipelineStepType, context: dict) -> Any:
        handlers = {
            PipelineStepType.AUDIO_EXTRACTION: self._step_audio_extraction,
            PipelineStepType.AI_NOISE_CANCELLATION: self._step_ai_noise_cancellation,
            PipelineStepType.TRANSCRIPTION: self._step_transcription,
            PipelineStepType.TOPIC_RESEARCH: self._step_topic_research,
            PipelineStepType.VISUAL_ANALYSIS: self._step_visual_analysis,
            PipelineStepType.CONTENT_CLASSIFICATION: self._step_content_classification,
            PipelineStepType.HIGHLIGHT_DETECTION: self._step_highlight_detection,
            PipelineStepType.SCORING: self._step_scoring,
            PipelineStepType.METADATA_GENERATION: self._step_metadata_generation,
            PipelineStepType.ASPECT_RATIO_RENDER: self._step_aspect_ratio_render,
            PipelineStepType.CLIP_GENERATION: self._step_clip_generation,
            PipelineStepType.SUBTITLE_STYLING: self._step_subtitle_styling,
            PipelineStepType.BURN_IN_EXPORT: self._step_burn_in_export,
            PipelineStepType.DEPTH_CAPTIONS: self._step_depth_captions,
        }
        handler = handlers.get(step)
        if handler is None:
            raise ValueError(f"Unknown pipeline step: {step.value}")
        # Every AI call the step makes is attributed to this project and step,
        # and counts against the run's budget.
        with llm_scope(
            project_id=self.project_id, user_id=self.user_id, step=step.value, budget=self._budget,
        ):
            return await handler(context)

    async def _size_budget(self) -> None:
        """Cap this run's AI spend in proportion to the source's length."""
        settings = get_settings()
        per_minute = float(
            settings.AI_BUDGET_PER_SOURCE_MINUTE_PRO if self.is_pro else settings.AI_BUDGET_PER_SOURCE_MINUTE_FREE
        )
        video_path = await self._project_video_path()
        if per_minute <= 0 or not video_path or not Path(video_path).exists():
            return
        from video_processor.ffmpeg_service import FFmpegService

        try:
            duration = await FFmpegService().probe_duration(video_path)
        except Exception as exc:
            log.warning("Could not size the AI budget, running uncapped: %s", exc)
            return
        # A floor so a very short video can still afford its handful of calls.
        self._budget.cap_usd = max(per_minute * 5, per_minute * duration / 60.0)
        log.info(
            "AI budget for this run: $%.3f (%.1f min at $%.4f/min, %s)",
            self._budget.cap_usd, duration / 60.0, per_minute, "pro" if self.is_pro else "free",
            extra={"project_id": self.project_id},
        )

    async def _step_audio_extraction(self, context: dict) -> dict:
        # Get video path from project (download already completed before pipeline start)
        video_path = await self._project_video_path()
        log.debug("Resolving video path for audio extraction", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            raise ValueError(
                "Missing downloaded video path for audio extraction. "
                "Video should have been downloaded before starting pipeline."
            )

        log.debug("Starting audio extraction", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Extracting audio track...", 10)
        from audio.extraction.schema import ExtractionRequest, OutputFormat, AudioChannel
        request = ExtractionRequest(
            input_path=video_path,
            output_format=OutputFormat.WAV,
            sample_rate=16000,
            channels=AudioChannel.MONO,
            overwrite=True,
        )
        log.debug(
            "Audio extraction request",
            extra={
                "project_id": self.project_id,
                "input_path": request.input_path,
                "output_format": request.output_format.value,
                "sample_rate": request.sample_rate,
                "channels": request.channels.value,
            },
        )
        result = await self._audio_extractor.extract(request)
        log.debug(
            "Audio extracted",
            extra={
                "project_id": self.project_id,
                "output_path": result.output_path,
                "duration_seconds": result.duration_seconds,
                "size_bytes": result.file_size_bytes,
            },
        )
        self._notify("Audio extracted", 100)
        return {"extraction_result": result.model_dump()}

    async def _step_ai_noise_cancellation(self, context: dict) -> dict:
        extraction = context.get(PipelineStepType.AUDIO_EXTRACTION.value, {})
        audio_path = extraction.get("extraction_result", {}).get("output_path")
        log.debug("Resolving audio path for noise cancellation", extra={"project_id": self.project_id, "audio_path": audio_path})
        if not audio_path:
            raise ValueError("Missing extracted audio path for noise cancellation")

        from audio.enhancement.service import estimate_snr_db

        snr_db = await asyncio.to_thread(estimate_snr_db, audio_path)
        if snr_db >= get_settings().NOISE_CANCEL_SKIP_SNR_DB:
            log.info(
                "Audio is already clean (SNR ~%.0f dB), skipping noise cancellation",
                snr_db, extra={"project_id": self.project_id},
            )
            self._notify("Audio is already clean, noise cancellation skipped", 100)
            return {"before_audio_path": audio_path, "after_audio_path": None, "skipped": True, "snr_db": round(snr_db, 1)}

        self._notify("Running AI noise cancellation...", 20)

        audio_bytes = await asyncio.to_thread(_read_audio_file, audio_path)
        log.debug(
            "Audio bytes loaded for enhancement",
            extra={"project_id": self.project_id, "audio_path": audio_path, "size_bytes": len(audio_bytes)},
        )

        request = AudioEnhanceRequest(audio_url=f"file://{audio_path}", config=self.audio_config)
        log.debug(
            "Starting AI noise cancellation",
            extra={"project_id": self.project_id, "audio_path": audio_path, "config": self.audio_config},
        )
        result = await self._audio_service.process_audio(request, audio_bytes)

        before_path = audio_path
        after_path = f"/tmp/{self.project_id}_enhanced.wav"
        log.info(
            "Noise cancellation result",
            extra={
                "project_id": self.project_id,
                "success": result.success,
                "processed_url": result.processed_url,
                "before_path": before_path,
                "after_path": after_path,
            },
        )

        if result.success and result.processed_url:
            processed_bytes = await self._fetch_processed_bytes(result.processed_url)
            with open(after_path, "wb") as f:
                f.write(processed_bytes)
            log.debug(
                "Enhanced audio saved",
                extra={"project_id": self.project_id, "after_path": after_path, "size_bytes": len(processed_bytes)},
            )

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            if project:
                project.audio_original_url = before_path
                project.audio_processed_url = after_path if result.success else None
                project.audio_reverted = False
                await session.commit()

        self._notify("AI noise cancellation complete", 100)
        return {
            "before_audio_path": before_path,
            "after_audio_path": after_path,
            "enhancement_result": result.model_dump(),
        }

    async def _step_transcription(self, context: dict) -> dict:
        # Get video path from project (download already completed before pipeline start)
        video_path = await self._project_video_path()
        log.debug("Resolving video path for transcription", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for transcription")

        log.debug("Starting transcription", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Transcribing audio...", 10)
        await self._prefetch_media_signals(video_path)

        audio_result = context.get(PipelineStepType.AUDIO_EXTRACTION.value, {})
        noise_result = context.get(PipelineStepType.AI_NOISE_CANCELLATION.value, {})
        enhanced_audio_path = noise_result.get("after_audio_path")
        extracted_audio_path = audio_result.get("extraction_result", {}).get("output_path")
        if enhanced_audio_path and Path(enhanced_audio_path).is_file() and Path(enhanced_audio_path).stat().st_size > 0:
            audio_input = enhanced_audio_path
        elif extracted_audio_path and Path(extracted_audio_path).is_file():
            audio_input = extracted_audio_path
        else:
            audio_input = video_path
        request = TranscriptionRequest(
            input_path=audio_input,
            model_size="small",
            language=None,
            # The title names the people and brands the video is about, so
            # Whisper spells them the way the creator does.
            prompt=await self._project_title(),
            chunk_duration=1200,
            chunk_overlap=10,
            word_timestamps=True,
            diarization=True,
            output_format="all",
            device="cpu",
        )
        log.debug(
            "Transcription request",
            extra={
                "project_id": self.project_id,
                "input_path": request.input_path,
                "model_size": request.model_size,
                "chunk_duration": request.chunk_duration,
                "device": request.device,
            },
        )

        def _progress(percent: float, message: str):
            self._notify(f"Transcription: {message}", int(percent))

        result = await self._transcription_service.transcribe(request, progress_callback=_progress)
        segments = getattr(result, "segments", [])
        await self._punctuate(segments)
        await self._romanize_captions(segments)
        log.debug(
            "Transcription complete",
            extra={
                "project_id": self.project_id,
                "segment_count": len(segments),
                "duration_seconds": getattr(result, "duration_seconds", None),
            },
        )
        self._notify("Transcription complete", 100)
        return {"transcription_result": result}

    async def _prefetch_media_signals(self, video_path: str) -> None:
        """Start the Map pass's non-transcript inputs now, when topic research will need them."""
        step = PipelineStepType.TOPIC_RESEARCH
        if step not in self.selected_steps or self._step_statuses.get(step.value) == "completed":
            return
        from content_intelligence.service import media_signals
        from video_processor.ffmpeg_service import FFmpegService

        duration = await FFmpegService().probe_duration(video_path)
        # Spend from this run's budget, attributed to topic research.
        with llm_scope(step=step.value):
            self._media_signals = asyncio.create_task(media_signals(video_path, duration))
        # A failure is retried inline by topic research; never let it go unobserved.
        self._media_signals.add_done_callback(lambda task: task.cancelled() or task.exception())

    async def _punctuate(self, segments: list) -> None:
        """Stretches Whisper wrote without punctuation get it back, so clips end on finished sentences."""
        changed = await punctuate_captions(segments, self.is_pro)
        if changed:
            log.info("Punctuated %d word(s)", changed, extra={"project_id": self.project_id})

    async def _romanize_captions(self, segments: list) -> None:
        """Hindi and Telugu speech gets Roman-script captions unless the user chose native script."""
        if not wants_roman(self.clip_settings.get("caption_script"), segments):
            return
        self._notify("Writing captions in Roman script...", 95)
        changed = await romanize_captions(segments, "roman", self.is_pro)
        log.info("Romanised %d caption word(s)", changed, extra={"project_id": self.project_id})

    async def _step_topic_research(self, context: dict) -> dict:
        self._notify("Researching topic...", 20)
        segments = self._transcript_segments(context)
        log.debug(
            "Starting topic research",
            extra={"project_id": self.project_id, "segment_count": len(segments)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        video_path = await self._project_video_path()
        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for topic research")

        analysis = await service.analyze_project(
            project_id=self.project_id,
            video_path=video_path,
            transcript_segments=segments,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
            clip_settings=self.clip_settings,
            signals=self._media_signals,
        )
        log.debug(
            "Topic research complete",
            extra={"project_id": self.project_id, "analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else type(analysis).__name__},
        )
        self._notify("Topic research complete", 100)
        return {"topic_research": analysis.get("topic_research", {}), "analysis": analysis}

    async def _step_visual_analysis(self, context: dict) -> dict:
        self._notify("Analyzing video frames...", 20)
        log.debug("Starting visual analysis", extra={"project_id": self.project_id})

        video_path = await self._project_video_path()
        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for visual analysis")

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})
        frame_result = analysis.get("frame_analysis")
        if not frame_result:
            from content_intelligence.analyzer import FrameAnalyzer

            category = analysis.get("classification", {}).get("category", "unknown")
            frame_result = await FrameAnalyzer().analyze(video_path, category)
        log.debug(
            "Visual analysis complete",
            extra={"project_id": self.project_id, "result_type": type(frame_result).__name__},
        )
        self._notify("Visual analysis complete", 100)
        return {"frame_analysis": frame_result}

    async def _step_content_classification(self, context: dict) -> dict:
        self._notify("Classifying content...", 50)
        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})
        segments = self._transcript_segments(context)
        classification = analysis.get("classification")
        if not classification:
            from content_intelligence.service import ContentIntelligenceService
            service = ContentIntelligenceService(is_pro=self.is_pro)
            classification = await service._classifier.classify(topic.get("topic_research", {}), segments)
        log.debug(
            "Content classification complete",
            extra={"project_id": self.project_id, "classification": str(classification)},
        )
        self._notify("Content classification complete", 100)
        return {"classification": classification}

    async def _step_highlight_detection(self, context: dict) -> dict:
        self._notify("Detecting highlights...", 30)
        log.debug("Starting highlight detection", extra={"project_id": self.project_id})

        video_path = await self._project_video_path()
        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for highlight detection")

        segments = self._transcript_segments(context)
        log.info(
            "Highlight detection inputs",
            extra={"project_id": self.project_id, "video_path": video_path, "segment_count": len(segments)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        highlights = await service.detect_highlights(
            project_id=self.project_id,
            video_path=video_path,
            transcript_segments=segments,
            analysis=analysis,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
            clip_settings=self.clip_settings,
        )
        log.debug(
            "Highlight detection complete",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )
        self._notify(f"Found {len(highlights)} highlights", 100)
        return {"highlights": highlights}

    async def _step_scoring(self, context: dict) -> dict:
        self._notify("Scoring highlights...", 50)
        highlight_result = context.get(PipelineStepType.HIGHLIGHT_DETECTION.value, {})
        highlights = highlight_result.get("highlights", [])
        log.debug(
            "Starting highlight scoring",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        scored = await service.score_highlights(highlights, analysis, clip_settings=self.clip_settings)
        log.debug(
            "Scoring complete",
            extra={"project_id": self.project_id, "scored_count": len(scored)},
        )
        self._notify("Scoring complete", 100)
        return {"scored_highlights": scored}

    async def _step_metadata_generation(self, context: dict) -> dict:
        self._notify("Generating metadata...", 50)
        score_result = context.get(PipelineStepType.SCORING.value, {})
        scored = score_result.get("scored_highlights", [])
        log.debug(
            "Starting metadata generation",
            extra={"project_id": self.project_id, "scored_highlight_count": len(scored)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        language = spoken_language(self._transcript_segments(context), self._reported_language(context))
        final_clips = await service.generate_metadata_for_clips(scored, language)
        log.debug(
            "Metadata generation complete",
            extra={"project_id": self.project_id, "final_clip_count": len(final_clips)},
        )
        self._notify("Metadata generation complete", 100)
        return {"final_clips": final_clips}

    async def _step_clip_generation(self, context: dict) -> dict:
        self._notify("Generating clips...", 30)
        meta_result = context.get(PipelineStepType.METADATA_GENERATION.value, {})
        final_clips = meta_result.get("final_clips", [])
        log.debug(
            "Starting clip generation",
            extra={"project_id": self.project_id, "clip_count": len(final_clips)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        highlight_result = context.get(PipelineStepType.HIGHLIGHT_DETECTION.value, {})
        score_result = context.get(PipelineStepType.SCORING.value, {})
        meta_result = context.get(PipelineStepType.METADATA_GENERATION.value, {})
        aspect_result = context.get(PipelineStepType.ASPECT_RATIO_RENDER.value, {})
        result = await self._clip_service.generate_clips_for_project(
            self.project_id,
            self.user_id,
            progress_callback=lambda msg, pct, _: self._notify(msg, pct),
            transcript_segments=self._transcript_segments(context),
            analysis=topic.get("analysis", {}),
            highlights=highlight_result.get("highlights", []),
            scored_highlights=score_result.get("scored_highlights", []),
            final_clips=meta_result.get("final_clips", []),
            rendered_clips=aspect_result.get("rendered_clips"),
            output_aspect_ratios=self.output_aspect_ratios,
            clip_settings=self.clip_settings,
        )
        log.debug(
            "Clip generation complete",
            extra={"project_id": self.project_id, "result_type": type(result).__name__},
        )
        if self.clip_settings.get("broll"):
            await self._plan_broll()
        await self._plan_motion()
        self._notify("Clip generation complete", 100)
        return result

    async def _plan_broll(self) -> None:
        """Cutaways for the new clips. Never fails the run: a clip without B-roll is still a clip."""
        async with AsyncSessionLocal() as session:
            if not await FeatureFlagService(session).is_enabled(BROLL_CUTAWAYS):
                log.info("B-roll cutaways are switched off; skipping: project=%s", self.project_id)
                return
        try:
            count = await plan_project_broll(
                self.project_id, self.user_id, self.is_pro,
                notify=lambda message, percent: self._notify(message, 90 + percent // 10),
            )
            self._notify(f"B-roll added to {count} clip(s)", 99)
        except Exception as exc:
            log.warning("B-roll planning failed: project=%s error=%s", self.project_id, exc)

    async def _plan_motion(self) -> None:
        """Motion graphics for the new clips (the light set below Pro). Never fails the run: a clip without graphics is still a clip."""
        try:
            count = await plan_project_motion(
                self.project_id, self.user_id, self.is_pro, video_path=await self._project_video_path(),
                notify=lambda message, percent: self._notify(message, 95 + percent // 25),
            )
            self._notify(f"Motion graphics planned for {count} clip(s)", 99)
        except Exception as exc:
            log.warning("Motion planning failed: project=%s error=%s", self.project_id, exc)

    async def _project_video_path(self) -> str | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            if not project:
                return None
            path = await ensure_local_copy(project)
            if path and path != project.local_path:
                await repo.set_local_path(project.id, path)
            return path

    async def _project_title(self) -> str | None:
        async with AsyncSessionLocal() as session:
            project = await ClipRepository(session).get_project(self.project_id, self.user_id)
        return (project.title or "")[:300] or None if project else None

    @staticmethod
    def _reported_language(context: dict) -> str | None:
        """The language Whisper reported for the transcript, if any."""
        transcription = context.get(PipelineStepType.TRANSCRIPTION.value, {})
        result = transcription.get("transcription_result") if isinstance(transcription, dict) else None
        if isinstance(result, dict):
            return result.get("language")
        return getattr(result, "language", None)

    def _transcript_segments(self, context: dict) -> list[dict]:
        transcription = context.get(PipelineStepType.TRANSCRIPTION.value, {})
        result = transcription.get("transcription_result", {}) if isinstance(transcription, dict) else getattr(transcription, "transcription_result", None)
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        if isinstance(result, dict):
            return list(result.get("segments", []) or [])
        return list(getattr(result, "segments", []) or [])

    async def _step_aspect_ratio_render(self, context: dict) -> dict:
        self._notify("Calculating aspect-ratio crops...", 40)
        meta_result = context.get(PipelineStepType.METADATA_GENERATION.value, {})
        final_clips = meta_result.get("final_clips", [])
        video_path = await self._project_video_path()
        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for aspect-ratio rendering")

        rendered_clips = await self._clip_service.prepare_clip_outputs(
            project_id=self.project_id,
            video_path=video_path,
            clips=final_clips,
            transcript_segments=self._transcript_segments(context),
            output_aspect_ratios=self.output_aspect_ratios,
            progress_callback=lambda message, percent, _: self._notify(
                message,
                percent,
                step=PipelineStepType.ASPECT_RATIO_RENDER.value,
                step_status="running",
            ),
            user_id=self.user_id,
        )
        self._notify("Aspect-ratio crops calculated", 100)
        return {"rendered_clips": rendered_clips}

    async def _step_subtitle_styling(self, context: dict) -> dict:
        self._notify("Preparing subtitle styles...", 100)
        log.debug("Starting subtitle styling step", extra={"project_id": self.project_id})
        from subtitle_styling.service import SubtitleStylingService
        from subtitle_styling.phrase_segmenter import segment_for_captions

        service = SubtitleStylingService()
        presets = await service.get_style_presets()

        segments = self._transcript_segments(context)
        caption_segments = []
        if segments:
            caption_segments = segment_for_captions(
                segments,
                max_chars=42,
                max_words_per_line=7,
            )
            log.debug(
                "Phrase segmentation complete",
                extra={"project_id": self.project_id, "segment_count": len(caption_segments)},
            )

        log.debug(
            "Subtitle styling step complete",
            extra={"project_id": self.project_id, "preset_count": len(presets), "caption_segment_count": len(caption_segments)},
        )
        return {"presets": presets, "caption_segments": caption_segments, "message": "User selects style before burn-in"}

    async def _step_burn_in_export(self, context: dict) -> dict:
        self._notify("Burning titles into clips...", 50)
        transcript_segments = self._transcript_segments(context)

        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            clips = [clip for clip in await repo.list_clips(self.project_id, self.user_id) if clip.s3_key]
            styles: dict[str, str] = {}
            for clip in clips:
                stored_style = (
                    await repo.get_subtitle_style(clip.subtitle_style_id, self.user_id)
                    if clip.subtitle_style_id else None
                )
                styles[clip.id] = stored_style.style_type if stored_style else DEFAULT_STYLE

        log.info(
            "BURN-IN START | project=%s | %d clip(s) fetched from S3",
            self.project_id, len(clips),
        )
        from clip_generation.service import MAX_CONCURRENT_CUTS

        burned = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CUTS)

        async def burn_one(index: int, clip: Any) -> None:
            tag = f"[BURN {index}/{len(clips)}]"
            async with semaphore:
                started = time.monotonic()
                try:
                    # Fetches the cut from S3, burns it, stores the result in S3.
                    result = await self._clip_service.process_clip_subtitles(
                        clip.id,
                        self.user_id,
                        {
                            "style_type": styles[clip.id],
                            "enable_watermark": self.watermark_enabled,
                            # Absent means Auto: every clip with a hook gets a bridge.
                            "hook_transition": self.hook_transition,
                        },
                        transcript_segments=transcript_segments,
                    )
                except Exception as exc:
                    log.error(
                        "%s FAILED  %s after %.1fs | %s: %s",
                        tag, clip.id, time.monotonic() - started, type(exc).__name__, exc,
                        extra={"project_id": self.project_id, "clip_id": clip.id},
                    )
                    return
            log.info(
                "%s DONE    %s in %.1fs | style=%s",
                tag, clip.id, time.monotonic() - started, styles[clip.id],
                extra={"project_id": self.project_id, "clip_id": clip.id},
            )
            burned.append({"clip_id": clip.id, "title": clip.title, "s3_key": result["s3_key"]})
            self._notify(f"Burned {len(burned)}/{len(clips)} clips", 50 + int(len(burned) * 50 / len(clips)))

        await asyncio.gather(*(burn_one(index, clip) for index, clip in enumerate(clips, start=1)))

        log.info(
            "BURN-IN DONE  | project=%s | %d/%d clip(s) burned",
            self.project_id, len(burned), len(clips),
        )
        if clips and not burned:
            raise RuntimeError(f"Burn-in failed for all {len(clips)} clips")
        self._notify(f"Burned {len(burned)}/{len(clips)} clips", 100)
        return {"status": "completed", "burned_clips": burned, "message": "Titles burned at export time"}

    async def _step_depth_captions(self, context: dict) -> dict:
        self._notify("Generating depth captions...", 10)
        log.debug("Starting depth captions generation", extra={"project_id": self.project_id})

        video_path = await self._project_video_path()
        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for depth captions")

        transcript_segments_data = self._transcript_segments(context)
        if not transcript_segments_data:
            raise ValueError("No transcript segments available for depth captions")

        transcript_segments = [TranscriptSegment(**s) for s in transcript_segments_data]

        request = DepthCaptionRequest(
            project_id=self.project_id,
            clip_id="auto",  # Will use the first clip
            style=StylePreset.GIANT_EDITORIAL,
            depth_mode=DepthMode.AUTO,
            language="en",
        )

        async def progress_cb(message: str, percent: int, stage: str | None = None):
            self._notify(f"Depth captions: {message}", percent, step="depth_captions", step_status=stage or "running")

        result = await create_depth_captions_job(
            request,
            transcript_segments,
            video_path,
            progress_callback=progress_cb,
        )

        if result.status.value == "failed":
            raise RuntimeError(f"Depth captions failed: {result.error}")

        log.debug(
            "Depth captions generation complete",
            extra={"project_id": self.project_id, "job_id": result.job_id, "output_url": result.output_url},
        )
        self._notify("Depth captions complete", 100)

        return {
            "job_id": result.job_id,
            "output_url": result.output_url,
            "preview_url": result.preview_url,
            "status": result.status.value,
        }

    async def _load_step_statuses(self) -> None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                logs = await repo.get_step_logs_for_pipeline(self.project_id)
                self._step_statuses = {log_entry.step.value: log_entry.status.value for log_entry in logs}
        except Exception as exc:
            log.debug(f"Failed to load step statuses for resume: {exc}")
            self._step_statuses = {}

    async def _restore_step_artifact(self, step: PipelineStepType) -> Any | None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                logs = await repo.get_step_logs_for_pipeline(self.project_id)
                for log_entry in logs:
                    if log_entry.step == step and log_entry.artifact_path:
                        import json as _json
                        try:
                            with open(log_entry.artifact_path, "r") as f:
                                return _json.load(f)
                        except Exception:
                            return None
        except Exception:
            pass
        return None

    async def _save_step_artifact(self, step: PipelineStepType, result: Any) -> None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                import json as _json
                import tempfile
                artifact_path = os.path.join(tempfile.gettempdir(), f"artifact_{self.project_id}_{step.value}.json")
                with open(artifact_path, "w") as f:
                    _json.dump(result, f, default=str)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.save_artifact(state.id, step, artifact_path)
        except Exception as exc:
            log.debug(f"Failed to save artifact for step {step.value}: {exc}")

    async def _mark_step_running(self, step: PipelineStepType) -> None:
        self._current_step = step.value
        self._notify(f"Starting {step.value}...", 0, step=step.value, step_status="running")
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.RUNNING)
        except Exception as exc:
            log.debug(f"Failed to update step status to running: {exc}")

    async def _mark_step_completed(self, step: PipelineStepType, result: Any) -> None:
        self._notify(f"Completed {step.value}", 100, step=step.value, step_status="completed")
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.COMPLETED)
            await self._save_step_artifact(step, result)
        except Exception as exc:
            log.debug(f"Failed to update step status to completed: {exc}")

    async def _mark_step_failed(self, step: PipelineStepType, error: str) -> None:
        self._notify(f"Failed: {step.value} - {error}", 0, step=step.value, step_status="failed")
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    await repo.update_step_status(state.id, step, StepStatus.FAILED, message=error)
        except Exception as exc:
            log.error(
                f"Could not persist FAILED status for step {step.value}: {exc}",
                extra={"project_id": self.project_id, "step": step.value},
                exc_info=True,
            )

    async def _mark_pipeline_completed(self) -> None:
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                last_step = self.selected_steps[-1] if self.selected_steps else PipelineStepType.CLIP_GENERATION
                await repo.update_pipeline_current_step(self.project_id, last_step, is_completed=True)
            await self._set_project_status(ProjectStatus.COMPLETED)
        except Exception as exc:
            log.error(f"Failed to mark pipeline completed: project={self.project_id} error={exc}", exc_info=True)

    async def _mark_pipeline_failed(self, error: str) -> None:
        """Record a terminal failure.

        `is_completed` stays False: it means "finished successfully", and clients
        check it before `error`, so setting it here made a failed run report success.
        """
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                state = await repo.get_pipeline(self.project_id)
                if state:
                    state.error = error
                    state.is_completed = False
                    await repo.fail_running_steps([state.id], error)
                    await session.commit()
                else:
                    log.error(f"No pipeline state to mark failed: project={self.project_id}")
            await self._set_project_status(ProjectStatus.FAILED)
        except Exception as exc:
            log.error(f"Failed to mark pipeline failed: project={self.project_id} error={exc}", exc_info=True)

    async def _set_project_status(self, status: ProjectStatus) -> None:
        try:
            from clip.repository import ClipRepository
            async with AsyncSessionLocal() as session:
                await ClipRepository(session).update_project_status(self.project_id, status)
        except Exception as exc:
            log.error(f"Failed to set project status to {status.value}: project={self.project_id} error={exc}")

    def _notify(
        self, message: str, percent: int, step: Optional[str] = None, step_status: Optional[str] = None
    ) -> None:
        target_step = step or self._current_step
        if self.progress_callback:
            try:
                result = self.progress_callback(message, percent, None, target_step, step_status)
                if asyncio.iscoroutine(result):
                    self._spawn(result)
            except Exception as e:
                log.debug(f"Progress notify failed: {e}")

        # The in-memory SSE store above lives in one worker process and is lost
        # on restart, so clients fall back to polling /status, which reads the
        # database. Without this the polled view reported 0% and no message for
        # every step and the UI could only ever show whole-step granularity.
        if target_step:
            self._schedule_progress_write(target_step, percent, message, step_status)

    def _schedule_progress_write(
        self, step: str, percent: int, message: str, step_status: Optional[str]
    ) -> None:
        """Persist step progress, rate-limited so a chatty step cannot flood the DB."""
        now = time.monotonic()
        is_transition = step_status is not None
        if not is_transition and now - self._last_progress_write < PROGRESS_WRITE_INTERVAL_SECONDS:
            return
        self._last_progress_write = now
        self._spawn(self._persist_step_progress(step, percent, message))

    def _spawn(self, coro) -> None:
        """Run a coroutine in the background, holding a reference until it ends."""
        try:
            task = asyncio.create_task(coro)
        except RuntimeError:
            # No running loop (synchronous caller); nothing to schedule onto.
            coro.close()
            log.debug("No event loop available for background pipeline task")
            return
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _persist_step_progress(self, step: str, percent: int, message: str) -> None:
        try:
            step_enum = PipelineStepType.resolve(step)
        except ValueError:
            return
        try:
            from pipeline.repository import PipelineRepository
            async with AsyncSessionLocal() as session:
                repo = PipelineRepository(session)
                await repo.update_step_progress(
                    self.project_id,
                    step_enum,
                    progress_percent=max(0, min(100, int(percent))),
                    message=message[:500] if message else None,
                )
        except Exception as exc:
            log.debug(f"Failed to persist progress for step {step}: {exc}")

    async def _fetch_processed_bytes(self, url: str) -> bytes:
        log.debug("Fetching processed bytes", extra={"project_id": self.project_id, "url": url})
        if url.startswith("processed://") or url.startswith("preview://"):
            return b""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content


# -- run management ------------------------------------------------------------
# Starting, resuming, cancelling and reporting on pipeline runs for the API.

# Clip generation plus a burn-in pass so a default run yields captioned clips.
# Re-styling later goes through /subtitle-styling/burn/{clip_id}, which replaces
# the burned track with the style the user picks.
DEFAULT_PIPELINE_STEPS = [
    "audio_extraction",
    "ai_noise_cancellation",
    "transcription",
    "topic_research",
    "visual_analysis",
    "content_classification",
    "highlight_detection",
    "scoring",
    "metadata_generation",
    "aspect_ratio_render",
    "clip_generation",
    # Without this the pipeline produced clips with no captions at all, because
    # nothing else in a default run ever calls the burner.
    "burn_in_export",
]

# Steps the orchestrator can actually run. A request naming anything else --
# the UI has long sent "bounding_box_detection", which has no handler -- would
# otherwise get a step row that stays "pending" forever, leaving a stuck entry
# in the UI and holding overall progress below 100% for the whole run.
RUNNABLE_PIPELINE_STEPS = {
    PipelineStepType.AUDIO_EXTRACTION,
    PipelineStepType.AI_NOISE_CANCELLATION,
    PipelineStepType.TRANSCRIPTION,
    PipelineStepType.TOPIC_RESEARCH,
    PipelineStepType.VISUAL_ANALYSIS,
    PipelineStepType.CONTENT_CLASSIFICATION,
    PipelineStepType.HIGHLIGHT_DETECTION,
    PipelineStepType.SCORING,
    PipelineStepType.METADATA_GENERATION,
    PipelineStepType.ASPECT_RATIO_RENDER,
    PipelineStepType.CLIP_GENERATION,
    PipelineStepType.SUBTITLE_STYLING,
    PipelineStepType.BURN_IN_EXPORT,
    PipelineStepType.DEPTH_CAPTIONS,
}

DEFAULT_AUDIO_CONFIG = {
    "ai_denoise": True,
    "noise_suppression_strength": 90,
    "de_reverb": True,
    "vocal_clarity_eq": True,
    "hum_filter": True,
}

_TERMINAL_PROGRESS_STATUSES = ("completed", "error", "cancelled")

_progress_store: dict[str, dict[str, Any]] = {}
_active_orchestrators: dict[str, PipelineOrchestrator] = {}
_progress_lock = asyncio.Lock()
_status_semaphore = asyncio.Semaphore(10)


def _pipeline_repository(session):
    # Imported late: pipeline.repository imports this module.
    from pipeline.repository import PipelineRepository

    return PipelineRepository(session)


def _resolve_steps(requested: list[str]) -> list[PipelineStepType]:
    """Map requested step names onto the steps the orchestrator implements."""
    resolved: list[PipelineStepType] = []
    for name in requested:
        try:
            step = PipelineStepType.resolve(name)
        except ValueError:
            log.warning("Ignoring unknown pipeline step requested by client: %s", name)
            continue
        if step not in RUNNABLE_PIPELINE_STEPS:
            log.info("Ignoring pipeline step with no handler: %s", step.value)
            continue
        if step not in resolved:
            resolved.append(step)
    if not resolved:
        raise CustomException(
            message="No runnable pipeline steps were requested.",
            code="NO_RUNNABLE_STEPS",
            status_code=400,
        )
    return resolved


def _apply_entitlements(
    entitlements: Entitlements,
    output_aspect_ratios: list[str],
    watermark_enabled: bool,
    clip_settings: dict | None,
) -> tuple[list[str], bool, dict | None]:
    """Clamp a run request to what the caller's plan permits.

    Enforced here rather than only in the UI, because hiding a control does not
    stop a crafted request. Over-reach is clamped rather than rejected, so a
    downgraded user's existing presets keep working at their new tier instead of
    erroring; an outright unusable request (no permitted ratio) still raises.
    """
    # Always a concrete list: an empty one would let the renderer pick shapes
    # from the content category, outside both the plan and the credit charge.
    allowed_ratios = resolve_output_aspect_ratios(entitlements, output_aspect_ratios)

    # A forced watermark cannot be switched off by the client.
    effective_watermark = True if entitlements.watermark_forced else watermark_enabled

    return allowed_ratios, effective_watermark, _clamp_clip_settings(entitlements, clip_settings)


def _clamp_clip_settings(entitlements: Entitlements, clip_settings: dict | None) -> dict:
    """Clamp clip count to the plan's cap and refuse styles it does not include."""
    settings = dict(clip_settings or {})
    requested_clips = settings.get("max_clips")
    cap = entitlements.max_clips_per_video
    if not isinstance(requested_clips, int) or requested_clips <= 0:
        settings["max_clips"] = cap
    else:
        settings["max_clips"] = min(requested_clips, cap)

    require_caption_style(entitlements, settings.get("caption_style") or settings.get("style_type"))
    if settings.get("caption_script") not in CAPTION_SCRIPTS:
        settings["caption_script"] = "auto"
    settings["broll"] = settings.get("broll") is True
    settings["story_clips"] = settings.get("story_clips") is True
    return settings


def _resolve_aspect_ratios(raw: Any) -> list[str]:
    """Validate the requested output formats; empty means "let the pipeline pick".

    An empty list is passed through rather than filled in here, so the renderer
    can choose from the video's content category -- naming every ratio at this
    point rendered four files per clip for content published in one shape. A
    client that does name ratios still gets exactly those.
    """
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list) or not raw:
        return []

    resolved: list[str] = []
    for item in raw:
        ratio = str(item).strip()
        if ratio in SUPPORTED_ASPECT_RATIOS and ratio not in resolved:
            resolved.append(ratio)
        elif ratio and ratio not in SUPPORTED_ASPECT_RATIOS:
            log.warning("Ignoring unsupported aspect ratio: %s", ratio)
    return resolved


def _check_export_entitlements(entitlements: Entitlements, request: SocialExportRequest) -> None:
    """Refuse an export the plan does not cover.

    Checked here as well as in the editor, which only hides locked options; the
    endpoint is reachable directly.
    """
    if request.aspect_ratio and request.aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        raise CustomException(
            message=f"Unsupported aspect ratio: {request.aspect_ratio}",
            code="INVALID_ASPECT_RATIO",
            status_code=400,
        )
    ratios = (
        {request.aspect_ratio}
        if request.aspect_ratio
        else {
            SOCIAL_PLATFORM_DEFAULTS[p.lower()]["aspect_ratio"]
            for p in request.platforms
            if p.lower() in SOCIAL_PLATFORM_DEFAULTS
        }
    )
    if any(not entitlements.allows_aspect_ratio(r) for r in ratios):
        raise aspect_ratio_not_entitled(entitlements)
    require_caption_style(entitlements, request.style_type)
    if request.hook_transition:
        require_hook_transition(entitlements, request.hook_transition.mode)


async def _update_progress(project_id: str, default: dict[str, Any], **fields: Any) -> None:
    async with _progress_lock:
        entry = _progress_store.get(project_id, dict(default))
        entry.update(fields)
        _progress_store[project_id] = entry


_IDLE_PROGRESS = {"status": "idle", "percent": 0, "message": ""}
_BLANK_PROGRESS = {"percent": 0, "message": ""}


def _progress_callback_factory(project_id: str) -> ProgressCallback:
    async def callback(message: str, percent: int, _: str | None, step: str | None = None, step_status: str | None = None) -> None:
        fields: dict[str, Any] = {"message": message, "percent": percent, "status": "running"}
        if step:
            fields["current_step"] = step
        if step_status:
            fields["step_status"] = step_status
        await _update_progress(project_id, _IDLE_PROGRESS, **fields)
    return callback


async def _stored_progress(project_id: str) -> dict[str, Any]:
    """Progress read from the database, for a run executing in another process."""
    async with AsyncSessionLocal() as session:
        repo = _pipeline_repository(session)
        state = await repo.get_pipeline(project_id)
        if not state:
            return dict(_IDLE_PROGRESS)
        if state.is_completed:
            return {"status": "completed", "percent": 100, "message": "Pipeline completed", "step_status": "completed"}
        if state.error:
            if state.cancel_requested:
                return {"status": "cancelled", "percent": 0, "message": "Pipeline cancelled by user", "step_status": "cancelled"}
            return {"status": "error", "percent": 0, "message": state.error, "step_status": "failed"}
        running = next((entry for entry in await repo.get_step_logs(state.id) if entry.status == StepStatus.RUNNING.value), None)
    if not running:
        return {"status": "running", "percent": 0, "message": ""}
    return {
        "status": "running",
        "percent": running.progress_percent,
        "message": running.message or "",
        "current_step": getattr(running.step, "value", running.step),
        "step_status": "running",
    }


async def _mark_cancelled(project_id: str) -> None:
    await _update_progress(
        project_id, _BLANK_PROGRESS,
        status="cancelled", message="Pipeline cancelled by user", step_status="cancelled",
    )


async def _run_pipeline(
    orchestrator: PipelineOrchestrator,
    project_id: str,
    user: dict | None = None,
    credit_refund_callback: Callable[[], Awaitable[None]] | None = None,
    requeue_on_interrupt: bool = False,
) -> None:
    try:
        results = await orchestrator.run()
        if orchestrator.is_cancelled:
            await _mark_cancelled(project_id)
            return
        await _update_progress(
            project_id, _IDLE_PROGRESS,
            status="completed", percent=100, message="Pipeline completed", step_status="completed",
        )

        if user:
            await notify_pipeline_outcome(user["user_id"], project_id, success=True)
            # A finished first video can complete a referral.
            await refresh_referrals_of(user["user_id"])
    except asyncio.CancelledError:
        if requeue_on_interrupt:
            # A worker shutting down: its job is redelivered and resumes from
            # the last completed step, so the run is neither failed nor refunded.
            log.warning(f"Pipeline interrupted, will resume on another worker: project={project_id}")
            raise
        # Raised when the server shuts down mid-run. It is not an Exception, so
        # the handler below never saw it and the run stayed "running" forever.
        log.warning(f"Pipeline interrupted: project={project_id}")
        await orchestrator._mark_pipeline_failed(INTERRUPTED_ERROR)
        if credit_refund_callback:
            await credit_refund_callback()
        raise
    except Exception as exc:
        log.error(f"Pipeline failed: project={project_id} error={exc}")
        await _update_progress(
            project_id, _IDLE_PROGRESS,
            status="error", percent=0, message=str(exc), step_status="failed",
        )

        # orchestrator.run() persists the failure itself, but it can also raise
        # before reaching that point (or while persisting) — make sure the DB
        # reflects the failure so /status does not report a stale running job.
        try:
            await orchestrator._mark_pipeline_failed(str(exc))
        except Exception as mark_exc:
            log.error(f"Could not persist pipeline failure: project={project_id} error={mark_exc}")

        if credit_refund_callback:
            await credit_refund_callback()

        if user:
            await notify_pipeline_outcome(
                user["user_id"], project_id, success=False, refunded=credit_refund_callback is not None
            )
    finally:
        _active_orchestrators.pop(project_id, None)


PIPELINE_JOB = "pipeline.run"


@handler(PIPELINE_JOB)
async def _run_pipeline_job(job: Job) -> None:
    """Runs one queued pipeline, in the API process or on a worker."""
    run = job.payload
    project_id = run["project_id"]
    user = run["user"]
    orchestrator = PipelineOrchestrator(
        project_id=project_id,
        user_id=user["user_id"],
        url=run["source_url"],
        selected_steps=[PipelineStepType(step) for step in run["steps"]],
        audio_config=run["audio_config"],
        progress_callback=_progress_callback_factory(project_id),
        watermark_enabled=run["watermark_enabled"],
        output_aspect_ratios=run["output_aspect_ratios"],
        clip_settings=run["clip_settings"],
        is_pro=run["is_pro"],
        # A redelivered job died part way through; skip the steps it finished.
        resume=run["resume"] or job.attempt > 1,
    )
    refund = functools.partial(_refund_run, user["user_id"], project_id, run["credit_cost"], run["resume"])
    _active_orchestrators[project_id] = orchestrator
    await _run_pipeline(
        orchestrator, project_id, user=user, credit_refund_callback=refund, requeue_on_interrupt=uses_workers(),
    )


async def _refund_run(user_id: str, project_id: str, amount: int, resume: bool) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await SubscriptionService.for_session(session).refund_credits(
                user_id=user_id,
                amount=amount,
                reason=f"Pipeline failed{' (resume)' if resume else ''}, refunding credits for project {project_id}",
                reference_id=project_id,
                reference_type=RUN_REFUND_REFERENCE,
            )
        except Exception as refund_exc:
            log.error(f"Credit refund failed: project={project_id} error={refund_exc}")


def _serialize_step(log_entry) -> dict[str, Any]:
    return {
        "step": log_entry.step,
        "status": log_entry.status,
        "progress_percent": log_entry.progress_percent,
        "message": log_entry.message,
        "artifact_path": log_entry.artifact_path,
        "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
        "finished_at": log_entry.finished_at.isoformat() if log_entry.finished_at else None,
    }


def _overall_status(state, steps: list[dict[str, Any]]) -> str:
    if state.error:
        return "error"
    if state.is_completed:
        return "completed"
    if any(s["status"] == "running" for s in steps):
        return "running"
    return "pending"


def _status_payload(project_id: str, state, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "status": _overall_status(state, steps),
        "current_step": state.current_step,
        "is_completed": state.is_completed,
        "error": state.error,
        "steps": steps,
    }


def _not_started(project_id: str) -> dict[str, Any]:
    return {"project_id": project_id, "status": "not_started", "steps": []}


@dataclass
class _RunQuote:
    """A run request resolved against the caller's plan, and what it costs."""

    selected_steps: list[PipelineStepType]
    output_aspect_ratios: list[str]
    audio_config: dict
    watermark_enabled: bool
    clip_settings: dict | None
    is_pro: bool
    credit_cost: int


async def _quote_run(
    subscription_service: SubscriptionService,
    user_id: str,
    project_id: str,
    duration_seconds: int,
    body: dict | None,
    resume: bool,
) -> _RunQuote:
    """Clamp a run request to the caller's plan and price it, without charging."""
    body = body or {}
    # Subtitles are burned at export time from the style the user picks, so
    # caption steps are deliberately absent from the default run.
    selected_steps = _resolve_steps(body.get("steps", DEFAULT_PIPELINE_STEPS))
    output_aspect_ratios = _resolve_aspect_ratios(body.get("output_aspect_ratios"))
    audio_config = body.get("audio_config", DEFAULT_AUDIO_CONFIG)
    watermark_enabled = body.get("watermark_enabled", True)
    clip_settings = body.get("clip_settings") if isinstance(body.get("clip_settings"), dict) else None

    # Which AI provider this run uses. Resolved once, here, so the whole
    # run is consistent even if the plan changes while it is in flight.
    entitlements = await subscription_service.get_entitlements(user_id)
    log.info(
        "Pipeline provider tier resolved: project=%s user=%s plan=%s is_pro=%s",
        project_id, user_id, entitlements.plan, entitlements.pro_ai_provider,
    )

    output_aspect_ratios, watermark_enabled, clip_settings = _apply_entitlements(
        entitlements, output_aspect_ratios, watermark_enabled, clip_settings
    )

    if duration_seconds <= 0:
        message = (
            "Video duration not available."
            if resume
            else "Video duration not available. Please wait for download to complete."
        )
        raise CustomException(message=message, code="DURATION_UNAVAILABLE", status_code=400)
    if duration_seconds > entitlements.max_upload_duration_seconds:
        raise CustomException(
            message=(
                f"This video is {duration_seconds // 60} minutes. Your {entitlements.plan} plan "
                f"supports up to {entitlements.max_upload_duration_seconds // 60} minutes per video."
            ),
            code="DURATION_NOT_ENTITLED",
            status_code=403,
        )

    return _RunQuote(
        selected_steps=selected_steps,
        output_aspect_ratios=output_aspect_ratios,
        audio_config=audio_config,
        watermark_enabled=watermark_enabled,
        clip_settings=clip_settings,
        is_pro=entitlements.pro_ai_provider,
        credit_cost=subscription_service.calculate_video_credit_cost(duration_seconds, len(output_aspect_ratios)),
    )


async def _settle_charge(
    subscription_service: SubscriptionService,
    user_id: str,
    project_id: str,
    quote: _RunQuote,
    amount: int,
    resume: bool,
    duration_seconds: int | None = None,
) -> None:
    """Take ``amount`` credits for a run, or give them back when it is negative
    (a run charged up front whose video turned out shorter)."""
    if amount < 0:
        await subscription_service.refund_credits(
            user_id=user_id,
            amount=-amount,
            reason="Video processing: video shorter than estimated",
            reference_id=project_id,
            reference_type=RUN_REFUND_REFERENCE,
        )
        return
    if amount == 0:
        return
    seconds = f"{duration_seconds}s, " if duration_seconds else ""
    try:
        await subscription_service.deduct_credits(
            user_id=user_id,
            amount=amount,
            reason=(
                f"Video processing{' (resume)' if resume else ''}: "
                f"{seconds}ratios {', '.join(quote.output_aspect_ratios)}"
            ),
            reference_id=project_id,
            reference_type="video_project_resume" if resume else RUN_CHARGE_REFERENCE,
        )
    except InsufficientCreditsError as exc:
        raise CustomException(message=str(exc), code="INSUFFICIENT_CREDITS", status_code=402)


async def _prepaid_credits(session, user_id: str, project_id: str) -> int:
    """Credits a project's first run has already paid for: charged when the
    download was requested and not yet refunded. Zero once a run exists, as
    that run's own charge and refund cover it from then on."""
    if await _pipeline_repository(session).get_pipeline(project_id):
        return 0
    return await SubscriptionService.for_session(session).net_charged(
        user_id, project_id, (RUN_CHARGE_REFERENCE, RUN_REFUND_REFERENCE)
    )


async def prepay_run(project_id: str, user_id: str, duration_seconds: int, request: PipelineStartRequest) -> int:
    """Charge for a run the moment its download is requested, so the balance
    drops right away and a second request cannot spend the same credits.
    The run settles any difference the real length makes when it starts."""
    async with AsyncSessionLocal() as session:
        subscription_service = SubscriptionService.for_session(session)
        quote = await _quote_run(subscription_service, user_id, project_id, duration_seconds, request.body(), resume=False)
        await _settle_charge(
            subscription_service, user_id, project_id, quote, quote.credit_cost, resume=False,
            duration_seconds=duration_seconds,
        )
        return quote.credit_cost


async def release_prepaid(project_id: str, user_id: str) -> None:
    """Refund an up-front charge when no run follows it: the download failed,
    the run was refused, or the project was deleted first."""
    async with AsyncSessionLocal() as session:
        try:
            amount = await _prepaid_credits(session, user_id, project_id)
            if amount > 0:
                await SubscriptionService.for_session(session).refund_credits(
                    user_id=user_id,
                    amount=amount,
                    reason=f"Video was not processed, refunding credits for project {project_id}",
                    reference_id=project_id,
                    reference_type=RUN_REFUND_REFERENCE,
                )
        except Exception:
            log.exception("Up-front charge refund failed: project=%s", project_id)


@dataclass
class _RunPlan(_RunQuote):
    """A run request resolved against the caller's plan and already charged."""

    refund: Callable[[], Awaitable[None]]

    def job(self, project, user: dict, resume: bool = False) -> Job:
        """The run as a queue message: plain JSON, so any worker can rebuild it."""
        return Job(PIPELINE_JOB, {
            "project_id": project.id,
            "source_url": project.source_url or "",
            "user": user,
            "resume": resume,
            "steps": [step.value for step in self.selected_steps],
            "audio_config": self.audio_config,
            "watermark_enabled": self.watermark_enabled,
            "output_aspect_ratios": self.output_aspect_ratios,
            "clip_settings": self.clip_settings,
            "is_pro": self.is_pro,
            "credit_cost": self.credit_cost,
        })

    def response(self, project_id: str, status: str) -> dict[str, Any]:
        return {
            "project_id": project_id,
            "status": status,
            "selected_steps": [s.value for s in self.selected_steps],
            "output_aspect_ratios": self.output_aspect_ratios,
            "watermark_enabled": self.watermark_enabled,
            "credits_deducted": self.credit_cost,
            "is_pro": self.is_pro,
        }


class PipelineRunService:
    """Starts, resumes, cancels and reports on pipeline runs."""

    @staticmethod
    async def _require_project(clip_repo: ClipRepository, project_id: str, user_id: str):
        project = await clip_repo.get_project(project_id, user_id)
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)
        return project

    @staticmethod
    async def _plan_run(session, project, user_id: str, body: dict | None, resume: bool) -> _RunPlan:
        """Resolve the request, clamp it to the plan and charge credits for it."""
        project_id = project.id
        subscription_service = SubscriptionService.for_session(session)
        quote = await _quote_run(subscription_service, user_id, project_id, project.duration_seconds or 0, body, resume)

        # A run asked for with its download was charged when it was asked for;
        # only the difference the real length makes is settled here.
        prepaid = 0 if resume else await _prepaid_credits(session, user_id, project_id)
        await _settle_charge(
            subscription_service, user_id, project_id, quote, quote.credit_cost - prepaid, resume,
            duration_seconds=project.duration_seconds,
        )

        return _RunPlan(
            **dataclasses.asdict(quote),
            refund=functools.partial(_refund_run, user_id, project_id, quote.credit_cost, resume),
        )

    async def start(self, project_id: str, user: dict, body: dict | None) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            project = await self._require_project(ClipRepository(session), project_id, user["user_id"])

            if project.status != ProjectStatus.UPLOADED or not project.duration_seconds:
                raise CustomException(
                    message="Video download and metadata save are not complete yet. Please wait for the upload to finish.",
                    code="VIDEO_NOT_READY",
                    status_code=409,
                )

            plan = await self._plan_run(session, project, user["user_id"], body, resume=False)

            # After the charge, so a refused charge leaves no run that looks in progress.
            try:
                await _pipeline_repository(session).create_pipeline(project_id, plan.selected_steps)
            except Exception:
                await plan.refund()
                raise

            try:
                await get_queue().enqueue(plan.job(project, user))
            except Exception:
                await plan.refund()
                raise
            return plan.response(project_id, "started")

    async def resume(self, project_id: str, user: dict, body: dict | None) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            clip_repo = ClipRepository(session)
            project = await self._require_project(clip_repo, project_id, user["user_id"])

            state = await _pipeline_repository(session).get_pipeline(project_id)
            if not state:
                raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

            plan = await self._plan_run(session, project, user["user_id"], body, resume=True)

            # Clients read either field as "failed", so a resumed run that kept them
            # showed as failed throughout, and even after it succeeded.
            state.error = None
            state.cancel_requested = False
            await session.commit()
            await clip_repo.update_project_status(project_id, ProjectStatus.PROCESSING)

            try:
                await get_queue().enqueue(plan.job(project, user, resume=True))
            except Exception:
                await plan.refund()
                raise
            return plan.response(project_id, "resumed")

    async def cancel(self, project_id: str, user_id: str) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            await self._require_project(ClipRepository(session), project_id, user_id)
            state = await _pipeline_repository(session).get_pipeline(project_id)
            if not state or state.is_completed or state.error:
                raise CustomException(message="No active pipeline found", code="PIPELINE_NOT_RUNNING", status_code=409)
            # The process running it -- this one or a worker -- stops at the next step.
            state.cancel_requested = True
            await session.commit()

        orchestrator = _active_orchestrators.get(project_id)
        if orchestrator:
            orchestrator.cancel()
        await _mark_cancelled(project_id)
        return {"project_id": project_id, "status": "cancelled"}

    async def require_owned_project(self, project_id: str, user_id: str) -> None:
        """404 unless the caller owns the project; checked before a stream opens."""
        async with AsyncSessionLocal() as session:
            await self._require_project(ClipRepository(session), project_id, user_id)

    @staticmethod
    async def progress_events(project_id: str) -> AsyncIterator[str]:
        """Server-sent events with the run's progress, once a second until it ends."""
        while True:
            async with _progress_lock:
                local = _progress_store.get(project_id)
            data = dict(local) if local else await _stored_progress(project_id)
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("status") in _TERMINAL_PROGRESS_STATUSES:
                break
            await asyncio.sleep(1)

    async def status_batch(self, body: dict[str, Any], user_id: str) -> dict[str, Any]:
        """Status for many projects in one round trip.

        The dashboard previously issued one GET /status/{id} per project on load.
        Those calls share a semaphore and a 15-connection pool, so a user with a
        dozen projects queued them and every other request -- including the ones
        behind a button click -- waited on the pool. This answers the whole list
        with three queries regardless of project count.
        """
        project_ids = body.get("project_ids") or []
        if not isinstance(project_ids, list):
            raise CustomException(message="project_ids must be a list", code="INVALID_BODY", status_code=400)
        project_ids = [str(pid) for pid in project_ids][:200]
        if not project_ids:
            return {"statuses": {}}

        async with AsyncSessionLocal() as session:
            pipeline_repo = _pipeline_repository(session)

            owned = await ClipRepository(session).list_projects(user_id)
            owned_ids = {p.id for p in owned} & set(project_ids)
            if not owned_ids:
                return {"statuses": {}}

            states = await pipeline_repo.get_latest_pipelines(list(owned_ids))
            logs_by_pipeline = await pipeline_repo.get_step_logs_for_pipelines(
                [state.id for state in states.values()]
            )

            statuses: dict[str, Any] = {}
            for project_id in owned_ids:
                state = states.get(project_id)
                if not state:
                    statuses[project_id] = _not_started(project_id)
                    continue
                steps = [_serialize_step(entry) for entry in logs_by_pipeline.get(state.id, [])]
                statuses[project_id] = _status_payload(project_id, state, steps)
            return {"statuses": statuses}

    async def status(self, project_id: str, user_id: str) -> dict[str, Any]:
        async with _status_semaphore:
            try:
                async with AsyncSessionLocal() as session:
                    pipeline_repo = _pipeline_repository(session)

                    project = await ClipRepository(session).get_project(project_id, user_id)
                    if not project:
                        return _not_started(project_id)

                    state = await pipeline_repo.get_pipeline(project_id)
                    if not state:
                        return _not_started(project_id)

                    steps = [_serialize_step(entry) for entry in await pipeline_repo.get_step_logs(state.id)]
                    return _status_payload(project_id, state, steps)
            except Exception as exc:
                log.error(f"Pipeline status failed: project={project_id} error={exc}")
                return {
                    "project_id": project_id,
                    "status": "error",
                    "error": str(exc),
                    "steps": [],
                }

    async def revert_step(self, project_id: str, step: str, user_id: str) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            pipeline_repo = _pipeline_repository(session)
            project = await self._require_project(ClipRepository(session), project_id, user_id)

            try:
                step_enum = PipelineStepType.resolve(step)
            except ValueError:
                raise CustomException(message=f"Invalid step: {step}", code="INVALID_STEP", status_code=400)

            state = await pipeline_repo.get_pipeline(project_id)
            if not state:
                raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

            await pipeline_repo.mark_step_reverted(state.id, step_enum)

            if step_enum == PipelineStepType.AI_NOISE_CANCELLATION:
                await pipeline_repo.save_artifact(state.id, step_enum, project.presigned_url or "")

            await pipeline_repo.update_pipeline_current_step(project_id, step_enum)

            return {"project_id": project_id, "step": step, "status": "reverted"}

    @staticmethod
    def social_platforms() -> dict[str, Any]:
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
        return {"platforms": platforms}

    async def export_for_social(
        self, project_id: str, request: SocialExportRequest, user_id: str
    ) -> SocialExportResponse:
        async with AsyncSessionLocal() as session:
            await self._require_project(ClipRepository(session), project_id, user_id)
            subscription_service = SubscriptionService.for_session(session)
            entitlements = await subscription_service.get_entitlements(user_id)
            _check_export_entitlements(entitlements, request)
            # Each exported clip counts toward the daily export limit.
            await subscription_service.consume_daily_quota(
                user_id, "exports", len(request.clip_ids) if request.clip_ids else max(1, request.max_clips or 1)
            )

        # A forced watermark cannot be switched off by the client.
        watermark_enabled = request.watermark_enabled or entitlements.watermark_forced

        return await ClipService().export_clips_for_social(
            project_id=project_id,
            user_id=user_id,
            platforms=request.platforms,
            clip_ids=request.clip_ids,
            aspect_ratio=request.aspect_ratio,
            style_type=request.style_type,
            custom_config=request.custom_config,
            max_clips=request.max_clips,
            max_duration_override=request.max_duration,
            enable_emoji=request.enable_emoji,
            watermark_enabled=watermark_enabled,
            burn_subtitles=request.burn_subtitles,
            show_title=request.show_title,
            animation_speed=request.animation_speed,
            hook_transition=request.hook_transition,
            bundle=request.bundle,
            channel_intro=request.channel_intro and entitlements.creator_intro,
        )


async def start_when_source_ready(project_id: str, user_id: str, request: PipelineStartRequest) -> str | None:
    """Start the run a download or upload asked for, once its source is stored.

    Runs on the server, so the run starts even if the browser that asked for
    it has been reloaded or closed. Returns why it could not start, if it
    could not (the caller shows that as the download's error).
    """
    try:
        await PipelineRunService().start(project_id, {"user_id": user_id}, request.body())
    except CustomException as exc:
        log.warning("Pipeline not started after download: project=%s reason=%s", project_id, exc.message)
        await release_prepaid(project_id, user_id)
        return exc.message
    except Exception:
        log.exception("Pipeline not started after download: project=%s", project_id)
        await release_prepaid(project_id, user_id)
        return "Processing could not be started. Please try again."
    return None
