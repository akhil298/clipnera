from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from depth_captions.schema import (
    VideoNormalizationConfig,
    TranscriptSegment,
    PersonTrack,
    EditPlan,
    MaskQualityMetrics,
    ModelVersionInfo,
    PipelineStage,
)

log = get_logger(__name__)


class CacheManager:
    def __init__(self, cache_root: str = "./cache/depth_captions") -> None:
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories for different cache types
        self.analysis_dir = self.cache_root / "analysis"
        self.tracks_dir = self.cache_root / "tracks"
        self.masks_dir = self.cache_root / "masks"
        self.mattes_dir = self.cache_root / "mattes"
        self.plans_dir = self.cache_root / "plans"
        self.previews_dir = self.cache_root / "previews"
        
        for d in [self.analysis_dir, self.tracks_dir, self.masks_dir, 
                  self.mattes_dir, self.plans_dir, self.previews_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _compute_cache_key(
        self,
        video_path: str,
        transcript_segments: list[TranscriptSegment],
        config: VideoNormalizationConfig,
        model_versions: ModelVersionInfo,
    ) -> str:
        """Compute deterministic cache key from inputs"""
        hasher = hashlib.sha256()
        
        # Video hash (first 1MB for speed)
        with open(video_path, "rb") as f:
            video_sample = f.read(1024 * 1024)
        hasher.update(video_sample)
        
        # Transcript hash
        transcript_str = json.dumps([s.model_dump() for s in transcript_segments], sort_keys=True)
        hasher.update(transcript_str.encode())
        
        # Config hash
        config_str = json.dumps(config.model_dump(), sort_keys=True)
        hasher.update(config_str.encode())
        
        # Model versions
        model_str = json.dumps(model_versions.model_dump(), sort_keys=True)
        hasher.update(model_str.encode())
        
        return hasher.hexdigest()[:16]

    def get_analysis_cache_path(self, cache_key: str) -> Path:
        return self.analysis_dir / f"{cache_key}.json"

    def get_tracks_cache_path(self, cache_key: str) -> Path:
        return self.tracks_dir / f"{cache_key}.json"

    def get_masks_cache_dir(self, cache_key: str, track_id: str) -> Path:
        return self.masks_dir / cache_key / track_id

    def get_mattes_cache_dir(self, cache_key: str, track_id: str) -> Path:
        return self.mattes_dir / cache_key / track_id

    def get_plan_cache_path(self, cache_key: str) -> Path:
        return self.plans_dir / f"{cache_key}.json"

    def get_preview_cache_path(self, cache_key: str) -> Path:
        return self.previews_dir / f"{cache_key}.mp4"

    def has_analysis(self, cache_key: str) -> bool:
        return self.get_analysis_cache_path(cache_key).exists()

    def has_tracks(self, cache_key: str) -> bool:
        return self.get_tracks_cache_path(cache_key).exists()

    def has_masks(self, cache_key: str, track_id: str) -> bool:
        mask_dir = self.get_masks_cache_dir(cache_key, track_id)
        return mask_dir.exists() and any(mask_dir.glob("*.png"))

    def has_mattes(self, cache_key: str, track_id: str) -> bool:
        matte_dir = self.get_mattes_cache_dir(cache_key, track_id)
        return matte_dir.exists() and any(matte_dir.glob("*.png"))

    def has_plan(self, cache_key: str) -> bool:
        return self.get_plan_cache_path(cache_key).exists()

    def has_preview(self, cache_key: str) -> bool:
        return self.get_preview_cache_path(cache_key).exists()

    def load_analysis(self, cache_key: str) -> Optional[dict]:
        path = self.get_analysis_cache_path(cache_key)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def save_analysis(self, cache_key: str, data: dict) -> None:
        path = self.get_analysis_cache_path(cache_key)
        with open(path, "w") as f:
            json.dump(data, f)

    def load_tracks(self, cache_key: str) -> Optional[dict]:
        path = self.get_tracks_cache_path(cache_key)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def save_tracks(self, cache_key: str, tracks: dict[str, PersonTrack]) -> None:
        path = self.get_tracks_cache_path(cache_key)
        data = {tid: track.model_dump() for tid, track in tracks.items()}
        with open(path, "w") as f:
            json.dump(data, f)

    def load_plan(self, cache_key: str) -> Optional[EditPlan]:
        path = self.get_plan_cache_path(cache_key)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return EditPlan(**data)
        return None

    def save_plan(self, cache_key: str, plan: EditPlan) -> None:
        path = self.get_plan_cache_path(cache_key)
        with open(path, "w") as f:
            json.dump(plan.model_dump(), f)

    def copy_masks_to_job(self, cache_key: str, track_id: str, job_masks_dir: Path) -> bool:
        src = self.get_masks_cache_dir(cache_key, track_id)
        if src.exists():
            job_masks_dir.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.png"):
                shutil.copy2(f, job_masks_dir / f.name)
            return True
        return False

    def copy_mattes_to_job(self, cache_key: str, track_id: str, job_mattes_dir: Path) -> bool:
        src = self.get_mattes_cache_dir(cache_key, track_id)
        if src.exists():
            job_mattes_dir.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.png"):
                shutil.copy2(f, job_mattes_dir / f.name)
            return True
        return False

    def copy_preview_to_job(self, cache_key: str, job_preview_path: Path) -> bool:
        src = self.get_preview_cache_path(cache_key)
        if src.exists():
            job_preview_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, job_preview_path)
            return True
        return False

    def save_masks(self, cache_key: str, track_id: str, job_masks_dir: Path) -> None:
        dst = self.get_masks_cache_dir(cache_key, track_id)
        dst.mkdir(parents=True, exist_ok=True)
        for f in job_masks_dir.glob("*.png"):
            shutil.copy2(f, dst / f.name)

    def save_mattes(self, cache_key: str, track_id: str, job_mattes_dir: Path) -> None:
        dst = self.get_mattes_cache_dir(cache_key, track_id)
        dst.mkdir(parents=True, exist_ok=True)
        for f in job_mattes_dir.glob("*.png"):
            shutil.copy2(f, dst / f.name)

    def save_preview(self, cache_key: str, job_preview_path: Path) -> None:
        dst = self.get_preview_cache_path(cache_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(job_preview_path, dst)

    def cleanup_old_cache(self, max_age_days: int = 30) -> int:
        """Remove cache entries older than max_age_days"""
        removed = 0
        cutoff = time.time() - (max_age_days * 86400)
        
        for cache_dir in [self.analysis_dir, self.tracks_dir, self.masks_dir,
                          self.mattes_dir, self.plans_dir, self.previews_dir]:
            for item in cache_dir.rglob("*"):
                if item.is_file():
                    try:
                        if item.stat().st_mtime < cutoff:
                            item.unlink()
                            removed += 1
                    except OSError:
                        pass
        
        # Remove empty directories
        for cache_dir in [self.analysis_dir, self.tracks_dir, self.masks_dir,
                          self.mattes_dir, self.plans_dir, self.previews_dir]:
            for item in cache_dir.rglob("*"):
                if item.is_dir() and not any(item.iterdir()):
                    try:
                        item.rmdir()
                    except OSError:
                        pass
        
        return removed

    def get_cache_stats(self) -> dict[str, Any]:
        stats = {}
        for name, cache_dir in [
            ("analysis", self.analysis_dir),
            ("tracks", self.tracks_dir),
            ("masks", self.masks_dir),
            ("mattes", self.mattes_dir),
            ("plans", self.plans_dir),
            ("previews", self.previews_dir),
        ]:
            if cache_dir.exists():
                files = list(cache_dir.rglob("*"))
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                stats[name] = {
                    "count": len([f for f in files if f.is_file()]),
                    "size_bytes": total_size,
                    "size_mb": round(total_size / (1024 * 1024), 2),
                }
            else:
                stats[name] = {"count": 0, "size_bytes": 0, "size_mb": 0}
        return stats


class JobCheckpointManager:
    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        stage: PipelineStage,
        data: dict,
        completed: bool = True,
    ) -> None:
        checkpoint_file = self.job_dir / f"{stage.value}.checkpoint"
        checkpoint = {
            "stage": stage.value,
            "completed": completed,
            "data": data,
            "timestamp": time.time(),
        }
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint, f)

    def load_checkpoint(self, stage: PipelineStage) -> Optional[dict]:
        checkpoint_file = self.job_dir / f"{stage.value}.checkpoint"
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                return json.load(f)
        return None

    def is_stage_completed(self, stage: PipelineStage) -> bool:
        cp = self.load_checkpoint(stage)
        return cp is not None and cp.get("completed", False)

    def get_last_completed_stage(self) -> Optional[PipelineStage]:
        completed = []
        for stage in PipelineStage:
            if self.is_stage_completed(stage):
                completed.append(stage)
        return max(completed, key=lambda s: list(PipelineStage).index(s)) if completed else None

    def clear_checkpoints(self) -> None:
        for stage in PipelineStage:
            cp_file = self.job_dir / f"{stage.value}.checkpoint"
            if cp_file.exists():
                cp_file.unlink()