from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

from core.logging_config import get_logger
from core.config import get_settings

from clip.youtube_service import YouTubeService
from audio.extraction.service import AudioExtractionService
from audio.enhancement.service import AudioService
from audio.enhancement.schema import AudioEnhanceRequest
from transcription.service import WhisperXTranscriptionService
from transcription.schema import TranscriptionRequest
from clip.repository import ClipRepository
from clip.model import ProjectStatus
from clip_generation.service import ClipService
from depth_captions.pipeline import create_depth_captions_job
from depth_captions.schema import DepthCaptionRequest, StylePreset, DepthMode, TranscriptSegment
from core.database import AsyncSessionLocal

from pipeline.model import PipelineStepType, StepStatus
from hook_transitions.schema import HookTransitionConfig

log = get_logger(__name__)


ProgressCallback = Callable[[str, int, Optional[str], Optional[str], Optional[str]], None]

# Minimum gap between step-progress writes to the database. Step transitions
# always write; the chatty in-step updates are sampled.
PROGRESS_WRITE_INTERVAL_SECONDS = 2.0
INTERRUPTED_ERROR = "Processing was interrupted by a server restart. Resume to continue."


async def fail_interrupted_pipelines() -> None:
    """Fail runs left open by a previous process, so they do not show as processing forever.

    Runs execute as in-process tasks, so this assumes a single backend process.
    """
    from pipeline.repository import PipelineRepository

    async with AsyncSessionLocal() as session:
        project_ids = await PipelineRepository(session).fail_unfinished_pipelines(INTERRUPTED_ERROR)
        clip_repo = ClipRepository(session)
        for project_id in project_ids:
            await clip_repo.update_project_status(project_id, ProjectStatus.FAILED)
    if project_ids:
        log.warning("Marked %d interrupted pipeline(s) failed: %s", len(project_ids), project_ids)


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
        log.info(
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

    def cancel(self) -> None:
        self._cancel = True
        log.warning(
            "Pipeline cancel requested",
            extra={"project_id": self.project_id, "user_id": self.user_id},
        )

    @property
    def is_cancelled(self) -> bool:
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
                if self._cancel:
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
                "PIPELINE %s — %d/%d step(s) in %.1fs",
                "CANCELLED" if self._cancel else "COMPLETE",
                len(results), len(self.selected_steps),
                time.monotonic() - pipeline_started,
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
                return f"{len(result.get('highlights', []))} highlight(s)"
            if step == PipelineStepType.SCORING:
                return f"{len(result.get('scored_highlights', []))} scored"
            if step == PipelineStepType.METADATA_GENERATION:
                return f"{len(result.get('final_clips', []))} clip(s) planned"
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
        log.info(
            "Executing pipeline step",
            extra={"project_id": self.project_id, "step": step.value},
        )
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
        return await handler(context)

    async def _step_audio_extraction(self, context: dict) -> dict:
        # Get video path from project (download already completed before pipeline start)
        video_path = await self._project_video_path()
        log.info("Resolving video path for audio extraction", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            raise ValueError(
                "Missing downloaded video path for audio extraction. "
                "Video should have been downloaded before starting pipeline."
            )

        log.info("Starting audio extraction", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Extracting audio track...", 10)
        from audio.extraction.schema import ExtractionRequest, OutputFormat, AudioChannel
        request = ExtractionRequest(
            input_path=video_path,
            output_format=OutputFormat.WAV,
            sample_rate=16000,
            channels=AudioChannel.MONO,
            overwrite=True,
        )
        log.info(
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
        log.info(
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
        log.info("Resolving audio path for noise cancellation", extra={"project_id": self.project_id, "audio_path": audio_path})
        if not audio_path:
            raise ValueError("Missing extracted audio path for noise cancellation")

        self._notify("Running AI noise cancellation...", 20)

        audio_bytes = await asyncio.to_thread(_read_audio_file, audio_path)
        log.info(
            "Audio bytes loaded for enhancement",
            extra={"project_id": self.project_id, "audio_path": audio_path, "size_bytes": len(audio_bytes)},
        )

        request = AudioEnhanceRequest(audio_url=f"file://{audio_path}", config=self.audio_config)
        log.info(
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
            log.info(
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
        log.info("Resolving video path for transcription", extra={"project_id": self.project_id, "video_path": video_path})

        if not video_path or not Path(video_path).exists():
            raise ValueError("Missing video path for transcription")

        log.info("Starting transcription", extra={"project_id": self.project_id, "video_path": video_path})
        self._notify("Transcribing audio...", 10)

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
            chunk_duration=1200,
            chunk_overlap=10,
            word_timestamps=True,
            diarization=True,
            output_format="all",
            device="cpu",
        )
        log.info(
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
        log.info(
            "Transcription complete",
            extra={
                "project_id": self.project_id,
                "segment_count": len(segments),
                "duration_seconds": getattr(result, "duration_seconds", None),
            },
        )
        self._notify("Transcription complete", 100)
        return {"transcription_result": result}

    async def _step_topic_research(self, context: dict) -> dict:
        self._notify("Researching topic...", 20)
        segments = self._transcript_segments(context)
        log.info(
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
        )
        log.info(
            "Topic research complete",
            extra={"project_id": self.project_id, "analysis_keys": list(analysis.keys()) if isinstance(analysis, dict) else type(analysis).__name__},
        )
        self._notify("Topic research complete", 100)
        return {"topic_research": analysis.get("topic_research", {}), "analysis": analysis}

    async def _step_visual_analysis(self, context: dict) -> dict:
        self._notify("Analyzing video frames...", 20)
        log.info("Starting visual analysis", extra={"project_id": self.project_id})

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
        log.info(
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
        log.info(
            "Content classification complete",
            extra={"project_id": self.project_id, "classification": str(classification)},
        )
        self._notify("Content classification complete", 100)
        return {"classification": classification}

    async def _step_highlight_detection(self, context: dict) -> dict:
        self._notify("Detecting highlights...", 30)
        log.info("Starting highlight detection", extra={"project_id": self.project_id})

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
        log.info(
            "Highlight detection complete",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )
        self._notify(f"Found {len(highlights)} highlights", 100)
        return {"highlights": highlights}

    async def _step_scoring(self, context: dict) -> dict:
        self._notify("Scoring highlights...", 50)
        highlight_result = context.get(PipelineStepType.HIGHLIGHT_DETECTION.value, {})
        highlights = highlight_result.get("highlights", [])
        log.info(
            "Starting highlight scoring",
            extra={"project_id": self.project_id, "highlight_count": len(highlights)},
        )

        topic = context.get(PipelineStepType.TOPIC_RESEARCH.value, {})
        analysis = topic.get("analysis", {})

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        scored = await service.score_highlights(highlights, analysis, clip_settings=self.clip_settings)
        log.info(
            "Scoring complete",
            extra={"project_id": self.project_id, "scored_count": len(scored)},
        )
        self._notify("Scoring complete", 100)
        return {"scored_highlights": scored}

    async def _step_metadata_generation(self, context: dict) -> dict:
        self._notify("Generating metadata...", 50)
        score_result = context.get(PipelineStepType.SCORING.value, {})
        scored = score_result.get("scored_highlights", [])
        log.info(
            "Starting metadata generation",
            extra={"project_id": self.project_id, "scored_highlight_count": len(scored)},
        )

        from content_intelligence.service import ContentIntelligenceService
        service = ContentIntelligenceService(is_pro=self.is_pro)

        final_clips = await service.generate_metadata_for_clips(scored)
        log.info(
            "Metadata generation complete",
            extra={"project_id": self.project_id, "final_clip_count": len(final_clips)},
        )
        self._notify("Metadata generation complete", 100)
        return {"final_clips": final_clips}

    async def _step_clip_generation(self, context: dict) -> dict:
        self._notify("Generating clips...", 30)
        meta_result = context.get(PipelineStepType.METADATA_GENERATION.value, {})
        final_clips = meta_result.get("final_clips", [])
        log.info(
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
        log.info(
            "Clip generation complete",
            extra={"project_id": self.project_id, "result_type": type(result).__name__},
        )
        self._notify("Clip generation complete", 100)
        return result

    async def _project_video_path(self) -> str | None:
        async with AsyncSessionLocal() as session:
            repo = ClipRepository(session)
            project = await repo.get_project(self.project_id, self.user_id)
            return project.local_path if project else None

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
        )
        self._notify("Aspect-ratio crops calculated", 100)
        return {"rendered_clips": rendered_clips}

    async def _step_subtitle_styling(self, context: dict) -> dict:
        self._notify("Preparing subtitle styles...", 100)
        log.info("Starting subtitle styling step", extra={"project_id": self.project_id})
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
            log.info(
                "Phrase segmentation complete",
                extra={"project_id": self.project_id, "segment_count": len(caption_segments)},
            )

        log.info(
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
                styles[clip.id] = stored_style.style_type if stored_style else "default"

        log.info(
            "BURN-IN START | project=%s | %d clip(s) fetched from S3",
            self.project_id, len(clips),
        )
        burned = []
        for index, clip in enumerate(clips, start=1):
            tag = f"[BURN {index}/{len(clips)}]"
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
                continue
            log.info(
                "%s DONE    %s in %.1fs | style=%s",
                tag, clip.id, time.monotonic() - started, styles[clip.id],
                extra={"project_id": self.project_id, "clip_id": clip.id},
            )
            burned.append({"clip_id": clip.id, "title": clip.title, "s3_key": result["s3_key"]})
            self._notify(f"Burned {len(burned)}/{len(clips)} clips", 50 + int(index * 50 / len(clips)))

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
        log.info("Starting depth captions generation", extra={"project_id": self.project_id})

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

        log.info(
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
        log.info("Fetching processed bytes", extra={"project_id": self.project_id, "url": url})
        if url.startswith("processed://") or url.startswith("preview://"):
            return b""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
