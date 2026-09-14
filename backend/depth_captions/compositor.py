from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from video_processor.ffmpeg_service import FFmpegService
from depth_captions.schema import (
    EditPlan,
    CaptionSegment,
    TextDepth,
    CanvasConfig,
)

log = get_logger(__name__)


class Compositor:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def compose(
        self,
        edit_plan: EditPlan,
        video_path: str,
        matte_dir: Path,
        output_path: Path,
        preview: bool = False,
        preview_duration: float = 5.0,
    ) -> str:
        log.info(f"Composing video: {video_path} -> {output_path}")
        
        filter_graph = self._build_filter_graph(edit_plan, matte_dir)
        
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        duration = preview_duration if preview else None
        if duration:
            # Get actual video duration
            import subprocess
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ], capture_output=True, text=True)
            try:
                video_duration = float(result.stdout.strip())
                duration = min(preview_duration, video_duration)
            except ValueError:
                duration = preview_duration
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
        ]
        
        # Add matte inputs
        matte_files = sorted(matte_dir.glob("*.png"))
        for matte_file in matte_files:
            cmd.extend(["-i", str(matte_file)])
        
        cmd.extend([
            "-filter_complex", filter_graph,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
        ])
        
        if duration:
            cmd.extend(["-t", str(duration)])
        
        cmd.append(str(output_path))
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"Composition failed: {err}")
        
        return str(output_path)

    def _build_filter_graph(self, edit_plan: EditPlan, matte_dir: Path) -> str:
        matte_files = sorted(matte_dir.glob("*.png"))
        num_mattes = len(matte_files)
        
        if num_mattes == 0:
            # No mattes, just render text on video
            return self._build_simple_text_graph(edit_plan)
        
        parts = []
        
        # Base video
        parts.append("[0:v]format=rgba[base]")
        
        # Process each segment
        for i, segment in enumerate(edit_plan.segments):
            matte_idx = min(i % num_mattes, num_mattes - 1) if num_mattes > 0 else 0
            matte_input = matte_idx + 1  # 0 is base video
            
            text_label = f"text{i}"
            composite_label = f"comp{i}"
            
            # Build text overlay
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_size = int(120 * segment.scale)
            x = int(segment.position.x * edit_plan.canvas.width)
            y = int(segment.position.y * edit_plan.canvas.height)
            
            font_color = self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)
            stroke_color = self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)
            
            text_filter = (
                f"[0:v]drawtext="
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
            parts.append(text_filter)
            
            if segment.depth == TextDepth.BEHIND:
                # Text behind person: base -> text -> matte -> composite
                if i == 0:
                    prev = "base"
                else:
                    prev = f"comp{i-1}"
                
                # Apply matte to separate foreground
                parts.append(
                    f"[{prev}][{matte_input}:v]alphamerge[fg{i}]"
                )
                parts.append(
                    f"[{prev}][{matte_input}:v]alphamerge[bg{i}]"
                )
                # Composite: background -> text -> foreground
                parts.append(
                    f"[bg{i}][{text_label}][fg{i}]overlay=enable='between(t,{segment.start},{segment.end})'[{composite_label}]"
                )
            else:
                # Text in front: just overlay on previous
                if i == 0:
                    prev = "base"
                else:
                    prev = f"comp{i-1}"
                
                parts.append(
                    f"[{prev}][{text_label}]overlay=enable='between(t,{segment.start},{segment.end})'[{composite_label}]"
                )
        
        # Final output
        final_label = f"comp{len(edit_plan.segments)-1}" if edit_plan.segments else "base"
        parts.append(f"[{final_label}]format=yuv420p[out]")
        
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
                prev = f"text{i-1}"
            
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
                f"[text{i}]"
            )
        
        final = f"text{len(edit_plan.segments)-1}" if edit_plan.segments else "0:v"
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


class FilterGraphBuilder:
    """Build complex FFmpeg filter graphs for depth composition"""
    
    def __init__(self) -> None:
        pass

    def build_depth_composition(
        self,
        edit_plan: EditPlan,
        num_matte_inputs: int,
    ) -> str:
        """Build filter graph for behind/front depth composition"""
        parts = []
        
        # Split base video for parallel processing
        parts.append("[0:v]split=2[base_bg][base_fg]")
        
        # Background path: apply inverse matte to get background
        # Foreground path: apply matte to get person
        
        for i, segment in enumerate(edit_plan.segments):
            matte_idx = min(i % num_matte_inputs, num_matte_inputs - 1) if num_matte_inputs > 0 else 0
            matte_input = matte_idx + 1
            
            if segment.depth == TextDepth.BEHIND:
                # Background layer with text
                parts.append(
                    f"[base_bg][{matte_input}:v]alphamerge,"
                    f"drawtext=text='{segment.text}':fontsize={int(120*segment.scale)}:"
                    f"fontcolor={self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)}:"
                    f"bordercolor={self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)}:"
                    f"borderw={edit_plan.style.stroke_width}:"
                    f"x={int(segment.position.x*edit_plan.canvas.width)}:"
                    f"y={int(segment.position.y*edit_plan.canvas.height)}:"
                    f"enable='between(t,{segment.start},{segment.end})'"
                    f"[bg_text{i}]"
                )
                
                # Foreground (person)
                parts.append(
                    f"[base_fg][{matte_input}:v]alphamerge[fg{i}]"
                )
                
                # Composite: bg_text + fg
                if i == 0:
                    parts.append(f"[bg_text{i}][fg{i}]overlay[{i}_out]")
                else:
                    parts.append(f"[{i-1}_out][bg_text{i}][fg{i}]overlay[{i}_out]")
            else:
                # Front text: composite on top of everything
                if i == 0:
                    prev = "base_bg"
                else:
                    prev = f"{i-1}_out"
                
                parts.append(
                    f"[{prev}]drawtext=text='{segment.text}':fontsize={int(120*segment.scale)}:"
                    f"fontcolor={self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)}:"
                    f"bordercolor={self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)}:"
                    f"borderw={edit_plan.style.stroke_width}:"
                    f"x={int(segment.position.x*edit_plan.canvas.width)}:"
                    f"y={int(segment.position.y*edit_plan.canvas.height)}:"
                    f"enable='between(t,{segment.start},{segment.end})'"
                    f"[{i}_out]"
                )
        
        final = f"{len(edit_plan.segments)-1}_out" if edit_plan.segments else "base_bg"
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


class ASSCompositor:
    """Compose using ASS subtitles for complex text layouts"""
    
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def compose_with_ass(
        self,
        edit_plan: EditPlan,
        video_path: str,
        matte_dir: Path,
        output_path: Path,
        ass_path: Path,
    ) -> str:
        # Generate ASS file from edit plan
        self._generate_ass(edit_plan, ass_path)
        
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        # Build filter graph with ASS and matte
        matte_files = sorted(matte_dir.glob("*.png"))
        
        cmd = ["ffmpeg", "-y", "-i", video_path]
        for mf in matte_files:
            cmd.extend(["-i", str(mf)])
        
        # Simple approach: burn ASS, then composite with matte
        # For production, use more sophisticated graph
        filter_graph = (
            f"[0:v]ass={ass_path.name}[texted];"
            f"[texted]format=yuv420p[out]"
        )
        
        cmd.extend([
            "-filter_complex", filter_graph,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ])
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(ass_path.parent)
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"ASS composition failed: {err}")
        
        return str(output_path)

    def _generate_ass(self, edit_plan: EditPlan, ass_path: Path) -> None:
        ass_path.parent.mkdir(parents=True, exist_ok=True)
        
        lines = [
            "[Script Info]",
            "Title: Depth Captions",
            "ScriptType: v4.00+",
            f"PlayResX: {edit_plan.canvas.width}",
            f"PlayResY: {edit_plan.canvas.height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        ]
        
        style = edit_plan.style
        primary = self._color_to_ass(style.font_color)
        outline = self._color_to_ass(style.stroke_color)
        back = "00000000"
        
        style_line = (
            f"Style: Default,{style.font_family},"
            f"{int(120 * style.default_scale)},"
            f"{primary},{primary},"
            f"{outline},{back},"
            f"{1 if style.font_weight >= 700 else 0},0,0,0,"
            f"100,100,{style.tracking},0,"
            f"1,{style.stroke_width},"
            f"{1 if style.shadow else 0},"
            f"2,10,10,{int(style.line_height * 40)},1"
        )
        lines.append(style_line)
        
        lines.append("")
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
        
        for i, segment in enumerate(edit_plan.segments):
            start = self._format_ass_time(segment.start)
            end = self._format_ass_time(segment.end)
            
            x = int(segment.position.x * edit_plan.canvas.width)
            y = int(segment.position.y * edit_plan.canvas.height)
            
            layer = 0 if segment.depth == TextDepth.BEHIND else 10
            text = f"{{\\pos({x},{y})\\fs{int(120 * segment.scale)}\\frz{segment.rotation}\\alpha{int((1-segment.opacity)*255):02X}}}{segment.text}"
            
            lines.append(f"Dialogue: {layer},{start},{end},Default,,0,0,0,,{text}")
        
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _color_to_ass(self, color: str) -> str:
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            a = "FF"
        elif len(c) == 8:
            r, g, b, a = c[0:2], c[2:4], c[4:6], c[6:8]
        else:
            return "&HFFFFFF"
        return f"&H{a}{b}{g}{r}".upper()

    def _format_ass_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"