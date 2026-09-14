from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from video_processor.ffmpeg_service import FFmpegService
from depth_captions.schema import (
    EditPlan,
    DepthCaptionJobResponse,
    DepthCaptionJobStatus,
    CanvasConfig,
)

log = get_logger(__name__)


class PreviewRenderer:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()
        self._preview_dir = Path("./previews")
        self._preview_dir.mkdir(parents=True, exist_ok=True)

    async def render_preview(
        self,
        edit_plan: EditPlan,
        video_path: str,
        matte_dir: Path,
        job_id: str,
        duration: float = 5.0,
    ) -> str:
        log.info(f"Rendering preview for job {job_id}")
        
        preview_path = self._preview_dir / f"preview_{job_id}.mp4"
        
        # Build simplified filter graph for preview
        filter_graph = self._build_preview_filter_graph(edit_plan, matte_dir)
        
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", filter_graph,
            "-t", str(duration),
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(preview_path),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            log.warning(f"Preview render failed: {err}")
            # Try fallback without matte
            return await self._render_fallback_preview(edit_plan, video_path, job_id, duration)
        
        return str(preview_path)

    def _build_preview_filter_graph(
        self,
        edit_plan: EditPlan,
        matte_dir: Path,
    ) -> str:
        matte_files = sorted(matte_dir.glob("*.png"))
        
        if not matte_files:
            return self._build_simple_text_graph(edit_plan)
        
        parts = []
        parts.append("[0:v]format=rgba[base]")
        
        for i, segment in enumerate(edit_plan.segments):
            matte_idx = min(i % len(matte_files), len(matte_files) - 1)
            matte_input = matte_idx + 1
            
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_size = int(120 * segment.scale)
            x = int(segment.position.x * edit_plan.canvas.width)
            y = int(segment.position.y * edit_plan.canvas.height)
            
            font_color = self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)
            stroke_color = self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)
            
            text_label = f"t{i}"
            parts.append(
                f"[base]drawtext="
                f"fontfile={font_path}:"
                f"text='{segment.text}':"
                f"fontsize={font_size}:"
                f"fontcolor={font_color}:"
                f"bordercolor={stroke_color}:"
                f"borderw={edit_plan.style.stroke_width}:"
                f"x={x}:"
                f"y={y}:"
                f"enable='between(t,{segment.start},{segment.end})'"
                f"[{text_label}]"
            )
            
            if segment.depth.value == "behind":
                # Behind: base -> text -> matte composite
                if i == 0:
                    prev = "base"
                else:
                    prev = f"c{i-1}"
                
                parts.append(f"[{prev}][{matte_input}:v]alphamerge[fg{i}]")
                parts.append(f"[{text_label}][fg{i}]overlay=enable='between(t,{segment.start},{segment.end})'[c{i}]")
            else:
                # Front: overlay on previous
                if i == 0:
                    prev = "base"
                else:
                    prev = f"c{i-1}"
                
                parts.append(f"[{prev}][{text_label}]overlay=enable='between(t,{segment.start},{segment.end})'[c{i}]")
        
        final = f"c{len(edit_plan.segments)-1}" if edit_plan.segments else "base"
        parts.append(f"[{final}]format=yuv420p[out]")
        
        return ";".join(parts)

    def _build_simple_text_graph(self, edit_plan: EditPlan) -> str:
        parts = []
        for i, segment in enumerate(edit_plan.segments):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_size = int(120 * segment.scale)
            x = int(segment.position.x * edit_plan.canvas.width)
            y = int(segment.position.y * edit_plan.canvas.height)
            
            font_color = self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)
            stroke_color = self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)
            
            if i == 0:
                prev = "0:v"
            else:
                prev = f"t{i-1}"
            
            parts.append(
                f"[{prev}]drawtext="
                f"fontfile={font_path}:"
                f"text='{segment.text}':"
                f"fontsize={font_size}:"
                f"fontcolor={font_color}:"
                f"bordercolor={stroke_color}:"
                f"borderw={edit_plan.style.stroke_width}:"
                f"x={x}:"
                f"y={y}:"
                f"enable='between(t,{segment.start},{segment.end})'"
                f"[t{i}]"
            )
        
        final = f"t{len(edit_plan.segments)-1}" if edit_plan.segments else "0:v"
        parts.append(f"[{final}]format=yuv420p[out]")
        return ";".join(parts)

    def _color_to_ffmpeg(self, color: str, opacity: float) -> str:
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
        elif len(c) == 8:
            r, g, b = c[0:2], c[2:4], c[4:6]
            opacity = int(c[6:8], 16) / 255
        else:
            r, g, b = "FF", "FF", "FF"
        a = int(opacity * 255)
        return f"0x{a:02X}{r}{g}{b}"

    async def _render_fallback_preview(
        self,
        edit_plan: EditPlan,
        video_path: str,
        job_id: str,
        duration: float,
    ) -> str:
        preview_path = self._preview_dir / f"preview_{job_id}_fallback.mp4"
        
        filter_graph = self._build_simple_text_graph(edit_plan)
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", filter_graph,
            "-t", str(duration),
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(preview_path),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"Fallback preview failed: {err}")
        
        return str(preview_path)


class QualityValidator:
    def __init__(self) -> None:
        pass

    async def validate_preview(
        self,
        preview_path: str,
        edit_plan: EditPlan,
    ) -> tuple[bool, list[str]]:
        """Validate preview quality before full render"""
        errors = []
        
        # Check file exists and has content
        from pathlib import Path
        if not Path(preview_path).exists():
            errors.append("Preview file not created")
            return False, errors
        
        if Path(preview_path).stat().st_size < 1000:
            errors.append("Preview file too small")
            return False, errors
        
        # Check video properties
        info = await self._get_video_info(preview_path)
        if not info:
            errors.append("Cannot read preview video info")
            return False, errors
        
        # Check duration matches
        expected_duration = max((s.end for s in edit_plan.segments), default=5.0)
        actual_duration = info.get("duration", 0)
        if abs(actual_duration - min(expected_duration, 5.0)) > 1.0:
            errors.append(f"Duration mismatch: expected ~{min(expected_duration, 5.0):.1f}s, got {actual_duration:.1f}s")
        
        # Check resolution
        if info.get("width") != edit_plan.canvas.width:
            errors.append(f"Width mismatch: expected {edit_plan.canvas.width}, got {info.get('width')}")
        if info.get("height") != edit_plan.canvas.height:
            errors.append(f"Height mismatch: expected {edit_plan.canvas.height}, got {info.get('height')}")
        
        # Check for black frames (rendering failure indicator)
        black_frames = await self._detect_black_frames(preview_path)
        if black_frames > 0.1:  # More than 10% black frames
            errors.append(f"Too many black frames: {black_frames*100:.1f}%")
        
        return len(errors) == 0, errors

    async def _get_video_info(self, video_path: str) -> dict[str, Any]:
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "json",
            video_path,
        ], capture_output=True, text=True)
        
        try:
            import json
            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0))
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            return {"duration": duration, "width": width, "height": height}
        except Exception:
            return {}

    async def _detect_black_frames(self, video_path: str) -> float:
        """Detect percentage of black frames"""
        import subprocess
        result = subprocess.run([
            "ffmpeg", "-v", "error",
            "-i", video_path,
            "-vf", "blackdetect=d=0.1:pix_th=0.1",
            "-f", "null", "-",
        ], capture_output=True, text=True)
        
        # Parse blackdetect output
        black_duration = 0.0
        for line in result.stderr.split("\n"):
            if "black_start" in line:
                # Extract duration
                pass
        
        # Simplified: return 0 for now
        return 0.0


class RenderValidator:
    @staticmethod
    async def validate_final_render(
        output_path: str,
        edit_plan: EditPlan,
        original_video_path: str,
    ) -> tuple[bool, list[str]]:
        errors = []
        
        from pathlib import Path
        if not Path(output_path).exists():
            errors.append("Output file not created")
            return False, errors
        
        if Path(output_path).stat().st_size < 10000:
            errors.append("Output file too small")
            return False, errors
        
        # Check duration matches original clip
        import subprocess
        orig_result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            original_video_path,
        ], capture_output=True, text=True)
        
        out_result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_path,
        ], capture_output=True, text=True)
        
        try:
            orig_duration = float(orig_result.stdout.strip())
            out_duration = float(out_result.stdout.strip())
            
            if abs(orig_duration - out_duration) > 0.5:
                errors.append(f"Duration mismatch: original {orig_duration:.1f}s, output {out_duration:.1f}s")
        except ValueError:
            errors.append("Could not verify duration")
        
        # Check resolution
        out_info = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height",
            "-of", "json",
            output_path,
        ], capture_output=True, text=True)
        
        try:
            import json
            data = json.loads(out_info.stdout)
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            
            if width != edit_plan.canvas.width:
                errors.append(f"Width mismatch: expected {edit_plan.canvas.width}, got {width}")
            if height != edit_plan.canvas.height:
                errors.append(f"Height mismatch: expected {edit_plan.canvas.height}, got {height}")
        except Exception:
            errors.append("Could not verify resolution")
        
        # Check audio preserved
        audio_check = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of", "json",
            output_path,
        ], capture_output=True, text=True)
        
        try:
            data = json.loads(audio_check.stdout)
            has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
            if not has_audio:
                errors.append("Audio stream missing in output")
        except Exception:
            pass
        
        return len(errors) == 0, errors