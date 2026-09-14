from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from depth_captions.schema import VideoMetadata

log = get_logger(__name__)


class MattingRefiner:
    def __init__(self) -> None:
        self._model_path = "./models/vitmatte/vitmatte_base.pt"
        self._device = "cuda" if self._check_cuda() else "cpu"
        self._trimap_erosion = 5
        self._trimap_dilation = 5

    def _check_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def refine_masks(
        self,
        video_path: str,
        mask_dir: Path,
        output_dir: Path,
        video_metadata: VideoMetadata,
    ) -> Path:
        log.info(f"Refining masks to alpha mattes: {mask_dir} -> {output_dir}")
        
        if not Path(self._model_path).exists():
            log.warning(f"ViTMatte model not found at {self._model_path}, using fallback")
            return await self._fallback_matting(mask_dir, output_dir, video_metadata)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_files = sorted(mask_dir.glob("*.png"))
        
        for mask_file in mask_files:
            output_path = output_dir / mask_file.name
            await self._refine_single_frame(video_path, mask_file, output_path, video_metadata)
        
        return output_dir

    async def _refine_single_frame(
        self,
        video_path: str,
        mask_path: Path,
        output_path: Path,
        video_metadata: VideoMetadata,
    ) -> None:
        # In production, this would call ViTMatte with the frame and mask
        # For now, use FFmpeg to create a soft alpha matte from the binary mask
        frame_idx = int(mask_path.stem)
        timestamp = frame_idx / video_metadata.fps
        
        # Extract the corresponding frame from the video
        frame_path = mask_path.parent.parent / f"frame_{frame_idx:06d}.jpg"
        
        cmd_extract = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            str(frame_path),
        ]
        proc = await asyncio.create_subprocess_exec(*cmd_extract, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        
        if frame_path.exists():
            # Create trimap from mask (erode for definite foreground, dilate for definite background)
            trimap_path = mask_path.parent.parent / f"trimap_{frame_idx:06d}.png"
            cmd_trimap = [
                "ffmpeg", "-y",
                "-i", str(mask_path),
                "-vf", f"erode={self._trimap_erosion},dilate={self._trimap_dilation}",
                str(trimap_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd_trimap, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            
            # Blend frame with mask to create alpha matte
            # This is a simplified version - real ViTMatte would do much better
            cmd_matte = [
                "ffmpeg", "-y",
                "-i", str(frame_path),
                "-i", str(mask_path),
                "-filter_complex",
                "[1:v]format=gray,geq=lum='p(X,Y)':a='lum(X,Y)'[alpha];"
                "[0:v][alpha]alphamerge",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd_matte, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
        else:
            # Just convert mask to alpha if frame extraction failed
            cmd = [
                "ffmpeg", "-y",
                "-i", str(mask_path),
                "-vf", "format=gray,geq=lum='p(X,Y)':a='lum(X,Y)'",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

    async def _fallback_matting(
        self,
        mask_dir: Path,
        output_dir: Path,
        video_metadata: VideoMetadata,
    ) -> Path:
        log.info("Using fallback matting (feathered binary masks)")
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_files = sorted(mask_dir.glob("*.png"))
        
        for mask_file in mask_files:
            output_path = output_dir / mask_file.name
            # Simple feathering: blur the mask edges
            cmd = [
                "ffmpeg", "-y",
                "-i", str(mask_file),
                "-vf", "gblur=sigma=2,format=gray,geq=lum='p(X,Y)':a='lum(X,Y)'",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
        
        return output_dir


class TrimapGenerator:
    def __init__(self, erosion_kernel: int = 5, dilation_kernel: int = 5) -> None:
        self.erosion_kernel = erosion_kernel
        self.dilation_kernel = dilation_kernel

    async def generate_trimap(self, mask_path: Path, output_path: Path) -> None:
        # Generate trimap: 0 = background, 128 = unknown, 255 = foreground
        cmd = [
            "ffmpeg", "-y",
            "-i", str(mask_path),
            "-vf",
            f"split=3[in1][in2][in3];"
            f"[in1]erode={self.erosion_kernel}[fg];"
            f"[in2]dilate={self.dilation_kernel}[bg];"
            f"[fg][bg]blend=all_mode=difference[diff];"
            f"[diff]threshold=128[unknown];"
            f"[fg][unknown][bg]combine=mode=addition",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()


class AlphaMattePostProcessor:
    def __init__(self) -> None:
        pass

    async def feather_edges(self, matte_dir: Path, output_dir: Path, sigma: float = 1.5) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        matte_files = sorted(matte_dir.glob("*.png"))
        
        for matte_file in matte_files:
            output_path = output_dir / matte_file.name
            cmd = [
                "ffmpeg", "-y",
                "-i", str(matte_file),
                "-vf", f"gblur=sigma={sigma}",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

    async def remove_halo(self, matte_dir: Path, output_dir: Path, threshold: float = 0.1) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        matte_files = sorted(matte_dir.glob("*.png"))
        
        for matte_file in matte_files:
            output_path = output_dir / matte_file.name
            cmd = [
                "ffmpeg", "-y",
                "-i", str(matte_file),
                "-vf", f"geq=lum='p(X,Y)':a='if(gt(alpha(X,Y),{threshold}*255),255,0)'",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

    async def temporal_smooth(
        self,
        matte_dir: Path,
        output_dir: Path,
        window: int = 3,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        matte_files = sorted(matte_dir.glob("*.png"))
        
        for i, matte_file in enumerate(matte_files):
            output_path = output_dir / matte_file.name
            
            if i >= window // 2 and i < len(matte_files) - window // 2:
                inputs = []
                filter_parts = []
                for j in range(-window // 2, window // 2 + 1):
                    idx = i + j
                    if 0 <= idx < len(matte_files):
                        inputs.extend(["-i", str(matte_files[idx])])
                        filter_parts.append(f"[{len(filter_parts)}:v]")
                
                filter_str = "".join(filter_parts) + f"tblend=all_mode=average[out]"
                
                cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_str, "-map", "[out]", "-frames:v", "1", str(output_path)]
            else:
                cmd = ["cp", str(matte_file), str(output_path)]
            
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()


class MattingAnythingRefiner:
    """Alternative matting refinement using Matting Anything model"""
    
    def __init__(self) -> None:
        self._model_path = "./models/matting_anything/matting_anything.pt"
        self._device = "cuda" if self._check_cuda() else "cpu"

    def _check_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def refine(
        self,
        video_path: str,
        mask_dir: Path,
        output_dir: Path,
        video_metadata: VideoMetadata,
    ) -> Path:
        # Placeholder for Matting Anything integration
        log.info("Matting Anything refinement not yet implemented, using ViTMatte")
        refiner = MattingRefiner()
        return await refiner.refine_masks(video_path, mask_dir, output_dir, video_metadata)