from __future__ import annotations

import asyncio
import json
import os
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from core.logging_config import get_logger
from core.exceptions import CustomException
from depth_captions.schema import (
    DepthCaptionRequest,
    DepthCaptionJobResponse,
    DepthCaptionJobStatus,
    PipelineStage,
    JobCheckpoint,
    ModelVersionInfo,
    TranscriptSegment,
    EditPlan,
    VideoNormalizationConfig,
    MaskQualityMetrics,
)
from depth_captions.analyzer import VideoAnalyzer, TranscriptAnalyzer
from depth_captions.subject_tracker import SubjectTracker
from depth_captions.segmentation import SAMSegmenter, MaskTemporalConsistency
from depth_captions.matting import MattingRefiner
from depth_captions.mask_quality import MaskQualityScorer
from depth_captions.planner import LLMPlanner, PlanValidator
from depth_captions.typography import TypographyEngine
from depth_captions.layout import LayoutEngine, DepthPlanner
from depth_captions.compositor import Compositor
from depth_captions.preview import PreviewRenderer, QualityValidator
from depth_captions.cache import CacheManager, JobCheckpointManager
from depth_captions.fallback import (
    FallbackRenderer,
    SimplifiedDepthRenderer,
    QualityBasedFallback,
    ErrorRecovery,
)

log = get_logger(__name__)


class WorkerState(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    RETRY = "retry"
    OFFLINE = "offline"
    ERROR = "error"


class DepthCaptionWorker:
    def __init__(
        self,
        worker_id: str | None = None,
        cache_root: str = "./cache/depth_captions",
        output_dir: str = "./generated_clips/depth_captions",
    ) -> None:
        self.worker_id = worker_id or f"worker_{uuid4().hex[:8]}"
        self.state = WorkerState.IDLE
        self.current_job_id: Optional[str] = None
        
        self.cache = CacheManager(cache_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize pipeline components
        self.analyzer = VideoAnalyzer()
        self.transcript_analyzer = TranscriptAnalyzer()
        self.subject_tracker = SubjectTracker()
        self.segmenter = SAMSegmenter()
        self.temporal_consistency = MaskTemporalConsistency()
        self.matting_refiner = MattingRefiner()
        self.quality_scorer = MaskQualityScorer()
        self.planner = LLMPlanner()
        self.typography = TypographyEngine()
        self.layout_engine = LayoutEngine()
        self.depth_planner = DepthPlanner(self.layout_engine)
        self.compositor = Compositor()
        self.preview_renderer = PreviewRenderer()
        self.quality_validator = QualityValidator()
        self.fallback_renderer = FallbackRenderer()
        self.simplified_renderer = SimplifiedDepthRenderer()
        
        log.info(f"Depth caption worker {self.worker_id} initialized")

    async def process_job(
        self,
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        video_path: str,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
    ) -> DepthCaptionJobResponse:
        self.state = WorkerState.BUSY
        job_id = str(uuid4())
        self.current_job_id = job_id
        
        job_dir = self.cache.cache_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_mgr = JobCheckpointManager(job_dir)
        
        model_versions = ModelVersionInfo()
        config = VideoNormalizationConfig()
        
        try:
            await self._notify(progress_callback, "Initializing job", 0, "queued")
            
            # Compute cache key
            cache_key = self.cache._compute_cache_key(
                video_path, transcript_segments, config, model_versions
            )
            
            # STAGE 1: Video Normalization & Analysis
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.PREPARATION,
                "Preparing video", 5, progress_callback,
                lambda: self._stage_preparation(video_path, job_dir, config)
            )
            
            # STAGE 2: Video Analysis
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.ANALYSIS,
                "Analyzing video", 10, progress_callback,
                lambda: self._stage_analysis(video_path, transcript_segments, job_dir)
            )
            
            # STAGE 3: Subject Tracking
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.TRACKING,
                "Tracking subject", 20, progress_callback,
                lambda: self._stage_tracking(video_path, transcript_segments, job_dir)
            )
            
            # STAGE 4: Segmentation
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.SEGMENTATION,
                "Segmenting person", 35, progress_callback,
                lambda: self._stage_segmentation(video_path, job_dir, checkpoint_mgr)
            )
            
            # STAGE 5: Temporal Consistency
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.MATTING,
                "Stabilizing masks", 45, progress_callback,
                lambda: self._stage_temporal_consistency(job_dir, checkpoint_mgr)
            )
            
            # STAGE 6: Matting Refinement
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.MATTING,
                "Refining masks to alpha mattes", 50, progress_callback,
                lambda: self._stage_matting(video_path, job_dir, checkpoint_mgr)
            )
            
            # STAGE 7: Quality Check
            quality = await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.QUALITY_CHECK,
                "Checking mask quality", 60, progress_callback,
                lambda: self._stage_quality_check(job_dir, checkpoint_mgr)
            )
            
            # Check if we should use fallback
            fallback_tier = QualityBasedFallback.get_fallback_tier(quality)
            if fallback_tier == "normal_captions":
                return await ErrorRecovery.recover_from_segmentation_failure(
                    request, transcript_segments, video_path, job_id, self.output_dir
                )
            elif fallback_tier == "simplified_depth":
                # Will use simplified renderer later
                pass
            
            # STAGE 8: Planning
            edit_plan = await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.PLANNING,
                "Planning caption layout", 70, progress_callback,
                lambda: self._stage_planning(
                    request, transcript_segments, job_dir, checkpoint_mgr, quality, fallback_tier
                )
            )
            
            # STAGE 9: Composition
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.COMPOSITION,
                "Building composition", 80, progress_callback,
                lambda: self._stage_composition(edit_plan, job_dir, checkpoint_mgr)
            )
            
            # STAGE 10: Preview
            preview_path = await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.PREVIEW,
                "Rendering preview", 85, progress_callback,
                lambda: self._stage_preview(edit_plan, video_path, job_dir, checkpoint_mgr)
            )
            
            # Validate preview
            valid, errors = await self.quality_validator.validate_preview(preview_path, edit_plan)
            if not valid:
                log.warning(f"Preview validation failed: {errors}")
                # Could retry or continue with warning
            
            # STAGE 11: Final Render
            output_path = await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.RENDER,
                "Rendering final video", 90, progress_callback,
                lambda: self._stage_final_render(
                    edit_plan, video_path, job_dir, checkpoint_mgr, fallback_tier
                )
            )
            
            # STAGE 12: Validate final render
            await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.ENCODING,
                "Validating output", 95, progress_callback,
                lambda: self._stage_validate_render(output_path, edit_plan, video_path)
            )
            
            # STAGE 13: Upload
            output_url = await self._run_stage(
                job_dir, checkpoint_mgr, PipelineStage.UPLOAD,
                "Uploading result", 98, progress_callback,
                lambda: self._stage_upload(output_path, job_id)
            )
            
            # Save to cache
            self.cache.save_plan(cache_key, edit_plan)
            
            self.state = WorkerState.IDLE
            self.current_job_id = None
            
            await self._notify(progress_callback, "Job completed", 100, "completed")
            
            return DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.COMPLETED,
                progress=100,
                stage="completed",
                output_url=output_url,
                preview_url=preview_path,
            )
            
        except Exception as e:
            log.exception(f"Job {job_id} failed")
            self.state = WorkerState.ERROR
            self.current_job_id = None
            
            return DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.FAILED,
                progress=0,
                stage="failed",
                error=str(e),
                retryable=True,
            )

    async def _run_stage(
        self,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
        stage: PipelineStage,
        message: str,
        progress: int,
        progress_callback: Callable[[str, int, str | None], None] | None,
        stage_fn: Callable,
    ) -> Any:
        # Check if stage already completed (idempotency)
        if checkpoint_mgr.is_stage_completed(stage):
            log.info(f"Stage {stage.value} already completed, loading from checkpoint")
            cp = checkpoint_mgr.load_checkpoint(stage)
            await self._notify(progress_callback, message, progress, stage.value)
            return cp["data"] if cp else None
        
        await self._notify(progress_callback, message, progress, stage.value)
        
        try:
            result = await stage_fn()
            
            checkpoint_mgr.save_checkpoint(stage, {"data": result}, completed=True)
            return result
            
        except Exception as e:
            log.error(f"Stage {stage.value} failed: {e}")
            checkpoint_mgr.save_checkpoint(stage, {"error": str(e)}, completed=False)
            raise

    async def _stage_preparation(
        self,
        video_path: str,
        job_dir: Path,
        config: VideoNormalizationConfig,
    ) -> dict:
        normalized_path, metadata = await self.analyzer.normalize_video(
            video_path, job_dir, config
        )
        return {"normalized_path": normalized_path, "metadata": metadata.model_dump()}

    async def _stage_analysis(
        self,
        video_path: str,
        transcript_segments: list[TranscriptSegment],
        job_dir: Path,
    ) -> dict:
        metadata = await self.analyzer.get_video_metadata(video_path)
        
        analysis = {
            "video_metadata": metadata.model_dump(),
            "transcript_segments": [s.model_dump() for s in transcript_segments],
        }
        
        analysis_path = job_dir / "analysis.json"
        with open(analysis_path, "w") as f:
            json.dump(analysis, f)
        
        return analysis

    async def _stage_tracking(
        self,
        video_path: str,
        transcript_segments: list[TranscriptSegment],
        job_dir: Path,
    ) -> dict:
        # Detect persons
        detections = await self.subject_tracker.detect_persons(video_path)
        
        # Track persons
        tracks = await self.subject_tracker.track_persons(video_path, detections)
        
        # Associate speaker with track
        metadata = await self.analyzer.get_video_metadata(video_path)
        speaker_track_id = await self.subject_tracker.associate_speaker_with_track(
            transcript_segments, tracks, metadata
        )
        
        tracks_data = {tid: track.model_dump() for tid, track in tracks.items()}
        return {
            "tracks": tracks_data,
            "speaker_track_id": speaker_track_id,
        }

    async def _stage_segmentation(
        self,
        video_path: str,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> dict:
        # Load tracks
        tracks_cp = checkpoint_mgr.load_checkpoint(PipelineStage.TRACKING)
        tracks_data = tracks_cp.get("data", {}).get("tracks", {}) if tracks_cp else {}
        
        from depth_captions.schema import PersonTrack
        tracks = {tid: PersonTrack(**td) for tid, td in tracks_data.items()}
        
        # Segment
        mask_dirs = await self.segmenter.segment_video(
            video_path, tracks, job_dir
        )
        
        return {"mask_dirs": {tid: str(d) for tid, d in mask_dirs.items()}}

    async def _stage_temporal_consistency(
        self,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> dict:
        seg_cp = checkpoint_mgr.load_checkpoint(PipelineStage.SEGMENTATION)
        mask_dirs_data = seg_cp.get("data", {}).get("mask_dirs", {}) if seg_cp else {}
        
        tracks_cp = checkpoint_mgr.load_checkpoint(PipelineStage.TRACKING)
        tracks_data = tracks_cp.get("data", {}).get("tracks", {}) if tracks_cp else {}
        
        from depth_captions.schema import PersonTrack
        tracks = {tid: PersonTrack(**td) for tid, td in tracks_data.items()}
        
        stabilized_dirs = {}
        for track_id, mask_dir_str in mask_dirs_data.items():
            mask_dir = Path(mask_dir_str)
            stable_dir = job_dir / "masks_stable" / track_id
            stable_dir.mkdir(parents=True, exist_ok=True)
            
            await self.temporal_consistency.stabilize_masks(
                mask_dir, stable_dir, tracks.get(track_id)
            )
            stabilized_dirs[track_id] = str(stable_dir)
        
        return {"stabilized_dirs": stabilized_dirs}

    async def _stage_matting(
        self,
        video_path: str,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> dict:
        stable_cp = checkpoint_mgr.load_checkpoint(PipelineStage.MATTING)
        stable_dirs_data = stable_cp.get("data", {}).get("stabilized_dirs", {}) if stable_cp else {}
        
        metadata = await self.analyzer.get_video_metadata(video_path)
        
        matte_dirs = {}
        for track_id, stable_dir_str in stable_dirs_data.items():
            stable_dir = Path(stable_dir_str)
            matte_dir = job_dir / "mattes" / track_id
            
            result_dir = await self.matting_refiner.refine_masks(
                video_path, stable_dir, matte_dir, metadata
            )
            matte_dirs[track_id] = str(result_dir)
        
        return {"matte_dirs": matte_dirs}

    async def _stage_quality_check(
        self,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> MaskQualityMetrics:
        matte_cp = checkpoint_mgr.load_checkpoint(PipelineStage.MATTING)
        matte_dirs_data = matte_cp.get("data", {}).get("matte_dirs", {}) if matte_cp else {}
        
        tracks_cp = checkpoint_mgr.load_checkpoint(PipelineStage.TRACKING)
        tracks_data = tracks_cp.get("data", {}).get("tracks", {}) if tracks_cp else {}
        
        from depth_captions.schema import PersonTrack
        tracks = {tid: PersonTrack(**td) for tid, td in tracks_data.items()}
        
        metadata = await self.analyzer.get_video_metadata("")
        # Use first track's matte dir
        first_track_id = list(matte_dirs_data.keys())[0] if matte_dirs_data else None
        first_track = tracks.get(first_track_id) if first_track_id else None
        
        if first_track_id and first_track:
            matte_dir = Path(matte_dirs_data[first_track_id])
            quality = await self.quality_scorer.score_masks(
                matte_dir, first_track, metadata
            )
        else:
            quality = MaskQualityMetrics(
                temporal_stability=0.5,
                boundary_quality=0.5,
                subject_confidence=0.5,
                coverage=0.5,
                overall=0.5,
            )
        
        return quality

    async def _stage_planning(
        self,
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
        quality: MaskQualityMetrics,
        fallback_tier: str,
    ) -> EditPlan:
        analysis_cp = checkpoint_mgr.load_checkpoint(PipelineStage.ANALYSIS)
        analysis = analysis_cp.get("data", {}) if analysis_cp else {}
        
        tracks_cp = checkpoint_mgr.load_checkpoint(PipelineStage.TRACKING)
        tracks_data = tracks_cp.get("data", {}).get("tracks", {}) if tracks_cp else {}
        
        from depth_captions.schema import PersonTrack
        tracks = {tid: PersonTrack(**td) for tid, td in tracks_data.items()}
        
        video_metadata = analysis.get("video_metadata", {})
        
        style = STYLE_PRESETS.get(request.style, STYLE_PRESETS[StylePreset.GIANT_EDITORIAL])
        
        canvas = CanvasConfig(
            width=video_metadata.get("width", 1080),
            height=video_metadata.get("height", 1920),
        )
        
        safe_zones = SafeZones()
        
        edit_plan = await self.planner.generate_edit_plan(
            transcript_segments, canvas, style, tracks,
            request.depth_mode, safe_zones, video_metadata
        )
        
        # Apply fallback tier adjustments
        if fallback_tier == "simplified_depth":
            edit_plan = QualityBasedFallback.create_simplified_plan(edit_plan)
        
        # Validate
        valid, errors = PlanValidator.validate(edit_plan)
        if not valid:
            log.warning(f"Plan validation errors: {errors}")
            edit_plan = PlanValidator.repair(edit_plan, canvas)
        
        return edit_plan

    async def _stage_composition(
        self,
        edit_plan: EditPlan,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> dict:
        matte_cp = checkpoint_mgr.load_checkpoint(PipelineStage.MATTING)
        matte_dirs_data = matte_cp.get("data", {}).get("matte_dirs", {}) if matte_cp else {}
        
        # Use first track's matte dir
        first_track_id = list(matte_dirs_data.keys())[0] if matte_dirs_data else None
        matte_dir = Path(matte_dirs_data[first_track_id]) if first_track_id else job_dir / "mattes" / "person_01"
        
        composition = {
            "edit_plan": edit_plan.model_dump(),
            "matte_dir": str(matte_dir),
        }
        
        return composition

    async def _stage_preview(
        self,
        edit_plan: EditPlan,
        video_path: str,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
    ) -> str:
        comp_cp = checkpoint_mgr.load_checkpoint(PipelineStage.COMPOSITION)
        matte_dir_str = comp_cp.get("data", {}).get("matte_dir", "") if comp_cp else ""
        matte_dir = Path(matte_dir_str) if matte_dir_str else job_dir / "mattes" / "person_01"
        
        preview_path = await self.preview_renderer.render_preview(
            edit_plan, video_path, matte_dir, job_id=job_dir.name
        )
        
        return preview_path

    async def _stage_final_render(
        self,
        edit_plan: EditPlan,
        video_path: str,
        job_dir: Path,
        checkpoint_mgr: JobCheckpointManager,
        fallback_tier: str,
    ) -> str:
        comp_cp = checkpoint_mgr.load_checkpoint(PipelineStage.COMPOSITION)
        matte_dir_str = comp_cp.get("data", {}).get("matte_dir", "") if comp_cp else ""
        matte_dir = Path(matte_dir_str) if matte_dir_str else job_dir / "mattes" / "person_01"
        
        output_path = self.output_dir / f"{job_dir.name}.mp4"
        
        if fallback_tier == "simplified_depth":
            tracks_cp = checkpoint_mgr.load_checkpoint(PipelineStage.TRACKING)
            tracks_data = tracks_cp.get("data", {}).get("tracks", {}) if tracks_cp else {}
            from depth_captions.schema import PersonTrack
            tracks = {tid: PersonTrack(**td) for tid, td in tracks_data.items()}
            
            return await self.simplified_renderer.render_with_bbox_depth(
                edit_plan, video_path, tracks, output_path
            )
        else:
            return await self.compositor.compose(
                edit_plan, video_path, matte_dir, output_path
            )

    async def _stage_validate_render(
        self,
        output_path: str,
        edit_plan: EditPlan,
        original_video_path: str,
    ) -> bool:
        valid, errors = await RenderValidator.validate_final_render(
            output_path, edit_plan, original_video_path
        )
        if not valid:
            raise RuntimeError(f"Render validation failed: {errors}")
        return True

    async def _stage_upload(self, output_path: str, job_id: str) -> str:
        from clients.services.s3 import S3
        from core.config import get_settings
        
        settings = get_settings()
        s3 = S3()
        bucket = settings.S3_BUCKET_NAME
        s3_key = f"depth_captions/{job_id}.mp4"
        
        try:
            s3.create_bucket(bucket)
        except Exception:
            pass
        
        with open(output_path, "rb") as f:
            file_bytes = f.read()
        s3.put_object(bucket, s3_key, file_bytes)
        presigned_url = s3.generate_presigned_url(bucket, s3_key, expires_in=3600)
        
        return presigned_url

    async def _notify(
        self,
        cb: Callable[[str, int, str | None], None] | None,
        message: str,
        percent: int,
        stage: str | None = None,
    ) -> None:
        if cb:
            try:
                result = cb(message, percent, stage)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log.debug(f"Progress notify failed: {exc}")


class WorkerPool:
    def __init__(self, num_workers: int = 2) -> None:
        self.workers: list[DepthCaptionWorker] = []
        self.num_workers = num_workers
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        for i in range(self.num_workers):
            worker = DepthCaptionWorker(worker_id=f"worker_{i}")
            self.workers.append(worker)
        
        self._running = True
        asyncio.create_task(self._process_queue())
        log.info(f"Worker pool started with {self.num_workers} workers")

    async def stop(self) -> None:
        self._running = False
        for worker in self.workers:
            worker.state = WorkerState.OFFLINE
        log.info("Worker pool stopped")

    def submit_job(
        self,
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        video_path: str,
        progress_callback: Callable[[str, int, str | None], None] | None = None,
    ) -> str:
        job_id = str(uuid4())
        self._job_queue.put_nowait({
            "job_id": job_id,
            "request": request,
            "transcript_segments": transcript_segments,
            "video_path": video_path,
            "progress_callback": progress_callback,
        })
        return job_id

    async def _process_queue(self) -> None:
        while self._running:
            try:
                job = await asyncio.wait_for(self._job_queue.get(), timeout=1.0)
                
                # Find available worker
                worker = next((w for w in self.workers if w.state == WorkerState.IDLE), None)
                if worker is None:
                    # Re-queue
                    await asyncio.sleep(1)
                    self._job_queue.put_nowait(job)
                    continue
                
                # Process job
                asyncio.create_task(self._process_job(worker, job))
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(f"Queue processing error: {e}")

    async def _process_job(
        self,
        worker: DepthCaptionWorker,
        job: dict,
    ) -> None:
        try:
            result = await worker.process_job(
                job["request"],
                job["transcript_segments"],
                job["video_path"],
                job["progress_callback"],
            )
            # In production, store result for retrieval
        except Exception as e:
            log.error(f"Job {job['job_id']} failed: {e}")


# Global worker pool instance
_worker_pool: Optional[WorkerPool] = None


async def get_worker_pool() -> WorkerPool:
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = WorkerPool(num_workers=2)
        await _worker_pool.start()
    return _worker_pool


async def shutdown_worker_pool() -> None:
    global _worker_pool
    if _worker_pool:
        await _worker_pool.stop()
        _worker_pool = None