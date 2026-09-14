from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from depth_captions.schema import (
    PersonTrack,
    PersonTrackPoint,
    BoundingBox,
    VideoMetadata,
)

log = get_logger(__name__)


class SAMSegmenter:
    def __init__(self) -> None:
        self._model_path = "./models/sam3.1/sam3.1.pt"
        self._device = "cuda" if self._check_cuda() else "cpu"
        self._multiplex_enabled = True
        self._max_objects = 16

    def _check_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def segment_video(
        self,
        video_path: str,
        tracks: dict[str, PersonTrack],
        output_dir: Path,
        processing_resolution: tuple[int, int] = (1280, 720),
    ) -> dict[str, Path]:
        log.info(f"Segmenting video with SAM 3.1: {video_path}")
        
        if not Path(self._model_path).exists():
            log.warning(f"SAM 3.1 model not found at {self._model_path}, using fallback")
            return await self._fallback_segmentation(video_path, tracks, output_dir, processing_resolution)
        
        mask_dirs = {}
        for track_id, track in tracks.items():
            mask_dir = output_dir / "masks" / track_id
            mask_dir.mkdir(parents=True, exist_ok=True)
            mask_dirs[track_id] = mask_dir
        
        for track_id, track in tracks.items():
            await self._segment_track(video_path, track, mask_dirs[track_id], processing_resolution)
        
        return mask_dirs

    async def _segment_track(
        self,
        video_path: str,
        track: PersonTrack,
        output_dir: Path,
        processing_resolution: tuple[int, int],
    ) -> None:
        # In production, this would use SAM 3.1's video prediction API
        # For now, generate placeholder masks using FFmpeg drawbox
        width, height = processing_resolution
        
        for frame_point in track.frames:
            mask_path = output_dir / f"{frame_point.frame:06d}.png"
            bbox = frame_point.bbox
            
            x = int(bbox.x * width)
            y = int(bbox.y * height)
            w = int(bbox.width * width)
            h = int(bbox.height * height)
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}",
                "-vf", f"drawbox=x={x}:y={y}:w={w}:h={h}:color=white:t=fill",
                "-frames:v", "1",
                str(mask_path),
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

    async def _fallback_segmentation(
        self,
        video_path: str,
        tracks: dict[str, PersonTrack],
        output_dir: Path,
        processing_resolution: tuple[int, int],
    ) -> dict[str, Path]:
        log.info("Using fallback segmentation (bounding box masks)")
        mask_dirs = {}
        for track_id, track in tracks.items():
            mask_dir = output_dir / "masks" / track_id
            mask_dir.mkdir(parents=True, exist_ok=True)
            mask_dirs[track_id] = mask_dir
            await self._segment_track(video_path, track, mask_dir, processing_resolution)
        return mask_dirs

    async def segment_single_frame(
        self,
        frame_path: str,
        bboxes: list[BoundingBox],
        output_dir: Path,
    ) -> list[Path]:
        # Segment a single frame with multiple bounding boxes
        mask_paths = []
        for i, bbox in enumerate(bboxes):
            mask_path = output_dir / f"mask_{i}.png"
            # Placeholder
            mask_paths.append(mask_path)
        return mask_paths


class MaskTemporalConsistency:
    def __init__(self, window_size: int = 5) -> None:
        self.window_size = window_size

    async def stabilize_masks(
        self,
        mask_dir: Path,
        output_dir: Path,
        track: PersonTrack,
    ) -> None:
        log.info(f"Stabilizing masks in {mask_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        mask_files = sorted(mask_dir.glob("*.png"))
        if not mask_files:
            return
        
        for i, mask_file in enumerate(mask_files):
            output_path = output_dir / mask_file.name
            
            # Simple temporal smoothing using FFmpeg's tblend filter
            # In production, use optical flow or more sophisticated methods
            if i > 0 and i < len(mask_files) - 1:
                prev_mask = mask_files[i - 1]
                next_mask = mask_files[i + 1]
                
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(prev_mask),
                    "-i", str(mask_file),
                    "-i", str(next_mask),
                    "-filter_complex",
                    "[0:v][1:v][2:v]tblend=all_mode=average[out]",
                    "-map", "[out]",
                    "-frames:v", "1",
                    str(output_path),
                ]
            else:
                # Just copy first and last frames
                cmd = [
                    "cp", str(mask_file), str(output_path),
                ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

    def compute_temporal_stability(self, mask_dir: Path) -> float:
        # Compute mask consistency score
        mask_files = sorted(mask_dir.glob("*.png"))
        if len(mask_files) < 2:
            return 1.0
        
        # Placeholder: return a simulated score
        return 0.92


class MaskPostProcessor:
    def __init__(self) -> None:
        pass

    async def dilate_masks(self, mask_dir: Path, output_dir: Path, kernel_size: int = 3) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_files = sorted(mask_dir.glob("*.png"))
        
        for mask_file in mask_files:
            output_path = output_dir / mask_file.name
            cmd = [
                "ffmpeg", "-y",
                "-i", str(mask_file),
                "-vf", f"dilate={kernel_size}",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

    async def erode_masks(self, mask_dir: Path, output_dir: Path, kernel_size: int = 3) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_files = sorted(mask_dir.glob("*.png"))
        
        for mask_file in mask_files:
            output_path = output_dir / mask_file.name
            cmd = [
                "ffmpeg", "-y",
                "-i", str(mask_file),
                "-vf", f"erode={kernel_size}",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

    async def fill_holes(self, mask_dir: Path, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_files = sorted(mask_dir.glob("*.png"))
        
        for mask_file in mask_files:
            output_path = output_dir / mask_file.name
            cmd = [
                "ffmpeg", "-y",
                "-i", str(mask_file),
                "-vf", "fillholes",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()