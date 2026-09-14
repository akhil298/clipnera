from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.logging_config import get_logger
from depth_captions.schema import (
    MaskQualityMetrics,
    PersonTrack,
    VideoMetadata,
)

log = get_logger(__name__)


class MaskQualityScorer:
    def __init__(self) -> None:
        self.temporal_weight = 0.3
        self.boundary_weight = 0.3
        self.confidence_weight = 0.2
        self.coverage_weight = 0.2

    async def score_masks(
        self,
        matte_dir: Path,
        track: PersonTrack,
        video_metadata: VideoMetadata,
    ) -> MaskQualityMetrics:
        log.info(f"Scoring mask quality for {matte_dir}")
        
        temporal_stability = await self._compute_temporal_stability(matte_dir)
        boundary_quality = await self._compute_boundary_quality(matte_dir, video_metadata)
        subject_confidence = self._compute_subject_confidence(track)
        coverage = await self._compute_coverage(matte_dir, track, video_metadata)
        
        overall = (
            temporal_stability * self.temporal_weight +
            boundary_quality * self.boundary_weight +
            subject_confidence * self.confidence_weight +
            coverage * self.coverage_weight
        )
        
        return MaskQualityMetrics(
            temporal_stability=temporal_stability,
            boundary_quality=boundary_quality,
            subject_confidence=subject_confidence,
            coverage=coverage,
            overall=overall,
        )

    async def _compute_temporal_stability(self, matte_dir: Path) -> float:
        matte_files = sorted(matte_dir.glob("*.png"))
        if len(matte_files) < 2:
            return 1.0
        
        # Simplified: compare consecutive frames
        # In production, use SSIM or optical flow based comparison
        scores = []
        for i in range(1, min(len(matte_files), 10)):
            # Placeholder score
            scores.append(0.9 + (i % 3) * 0.02)
        
        return sum(scores) / len(scores) if scores else 1.0

    async def _compute_boundary_quality(
        self,
        matte_dir: Path,
        video_metadata: VideoMetadata,
    ) -> float:
        # Check for sharp transitions at boundaries (good) vs gradual (bad)
        # In production, use gradient analysis on alpha channel
        matte_files = list(matte_dir.glob("*.png"))
        if not matte_files:
            return 0.0
        
        # Placeholder
        return 0.88

    def _compute_subject_confidence(self, track: PersonTrack) -> float:
        if not track.frames:
            return 0.0
        
        confidences = [f.confidence for f in track.frames]
        return sum(confidences) / len(confidences)

    async def _compute_coverage(
        self,
        matte_dir: Path,
        track: PersonTrack,
        video_metadata: VideoMetadata,
    ) -> float:
        # Check if masks cover the expected person region consistently
        matte_files = sorted(matte_dir.glob("*.png"))
        if not matte_files or not track.frames:
            return 0.0
        
        # Placeholder: assume good coverage if we have masks for most frames
        expected_frames = int(video_metadata.duration * video_metadata.fps)
        actual_frames = len(matte_files)
        
        if expected_frames > 0:
            return min(1.0, actual_frames / (expected_frames * 0.5))  # Sample every 2 frames
        return 1.0

    def get_quality_tier(self, metrics: MaskQualityMetrics) -> str:
        overall = metrics.overall
        if overall >= 0.90:
            return "premium"
        elif overall >= 0.75:
            return "good"
        elif overall >= 0.50:
            return "acceptable"
        else:
            return "poor"

    def should_use_depth_effect(self, metrics: MaskQualityMetrics) -> bool:
        return metrics.overall >= 0.50

    def should_use_premium_depth(self, metrics: MaskQualityMetrics) -> bool:
        return metrics.overall >= 0.90


class MaskValidator:
    @staticmethod
    def validate_mask_directory(matte_dir: Path) -> tuple[bool, str]:
        matte_files = list(matte_dir.glob("*.png"))
        if not matte_files:
            return False, "No mask files found"
        
        # Check file sizes (empty files indicate failure)
        for f in matte_files[:10]:
            if f.stat().st_size < 100:
                return False, f"Mask file too small: {f.name}"
        
        return True, "OK"

    @staticmethod
    def check_alpha_channel(matte_path: Path) -> bool:
        # In production, verify the PNG has an alpha channel
        return True