from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from depth_captions.schema import (
    CaptionSegment,
    EditPlan,
    CanvasConfig,
    StyleConfig,
    BoundingBox,
)

log = get_logger(__name__)


class TypographyEngine:
    def __init__(self, font_dir: str = "./fonts") -> None:
        self.font_dir = Path(font_dir)
        self.font_dir.mkdir(parents=True, exist_ok=True)

    async def render_text_layer(
        self,
        segment: CaptionSegment,
        style: StyleConfig,
        canvas: CanvasConfig,
        output_dir: Path,
        segment_index: int,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"text_{segment_index:06d}.mov"
        
        font_path = self._resolve_font(style.font_family)
        font_size = int(120 * segment.scale)
        
        x = int(segment.position.x * canvas.width)
        y = int(segment.position.y * canvas.height)
        w = int(segment.position.width * canvas.width)
        h = int(segment.position.height * canvas.height)
        
        # Build drawtext filter
        font_color = self._parse_color(style.font_color, segment.opacity)
        stroke_color = self._parse_color(style.stroke_color, 1.0)
        
        filter_parts = [
            f"drawtext="
            f"text='{segment.text}':"
            f"fontfile={font_path}:"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"bordercolor={stroke_color}:"
            f"borderw={style.stroke_width}:"
            f"x={x - w//2}:"
            f"y={y - h//2}:"
            f"enable='between(t,{segment.start},{segment.end})'",
        ]
        
        if style.shadow:
            filter_parts.append("shadowcolor=black@0.5:shadowx=2:shadowy=2")
        
        if style.glow:
            filter_parts.append("box=1:boxcolor=white@0.3:boxborderw=10")
        
        vf = ",".join(filter_parts)
        
        # Use transparent background
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=transparent:s={canvas.width}x{canvas.height}:d={segment.end - segment.start}:r=30",
            "-vf", vf,
            "-c:v", "qtrle",
            "-pix_fmt", "argb",
            str(output_path),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            log.warning(f"Text layer render failed: {err}")
            # Fallback: render without alpha
            await self._render_fallback(segment, style, canvas, output_path)
        
        return output_path

    async def _render_fallback(
        self,
        segment: CaptionSegment,
        style: StyleConfig,
        canvas: CanvasConfig,
        output_path: Path,
    ) -> None:
        font_path = self._resolve_font(style.font_family)
        font_size = int(120 * segment.scale)
        
        x = int(segment.position.x * canvas.width)
        y = int(segment.position.y * canvas.height)
        w = int(segment.position.width * canvas.width)
        h = int(segment.position.height * canvas.height)
        
        font_color = self._parse_color(style.font_color, segment.opacity)
        stroke_color = self._parse_color(style.stroke_color, 1.0)
        
        vf = (
            f"drawtext="
            f"text='{segment.text}':"
            f"fontfile={font_path}:"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"bordercolor={stroke_color}:"
            f"borderw={style.stroke_width}:"
            f"x={x - w//2}:"
            f"y={y - h//2}:"
            f"enable='between(t,{segment.start},{segment.end})'"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={canvas.width}x{canvas.height}:d={segment.end - segment.start}:r=30",
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path.with_suffix(".mp4")),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

    def _resolve_font(self, font_family: str) -> str:
        font_map = {
            "Inter": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "Arial": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "Georgia": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "Impact": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "Courier New": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        }
        return font_map.get(font_family, font_map["Inter"])

    def _parse_color(self, color: str, opacity: float) -> str:
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
        elif len(c) == 8:
            r, g, b, a = c[0:2], c[2:4], c[4:6], c[6:8]
            opacity = int(a, 16) / 255
        else:
            r, g, b = "FF", "FF", "FF"
        
        a = int(opacity * 255)
        return f"0x{a:02X}{r}{g}{b}"

    async def render_all_segments(
        self,
        edit_plan: EditPlan,
        output_dir: Path,
    ) -> list[Path]:
        text_layers = []
        for i, segment in enumerate(edit_plan.segments):
            layer_path = await self.render_text_layer(
                segment, edit_plan.style, edit_plan.canvas, output_dir, i
            )
            text_layers.append(layer_path)
        return text_layers


class ASSGenerator:
    """Generate ASS subtitle files for complex text layouts"""
    
    def __init__(self) -> None:
        pass

    def generate_ass(
        self,
        edit_plan: EditPlan,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
            
            # Add position override
            text = f"{{\\pos({x},{y})\\fs{int(120 * segment.scale)}\\frz{segment.rotation}\\alpha{int((1-segment.opacity)*255):02X}}}{segment.text}"
            
            layer = 0 if segment.depth.value == "behind" else 10
            
            lines.append(f"Dialogue: {layer},{start},{end},Default,,0,0,0,,{text}")
        
        with open(output_path, "w", encoding="utf-8") as f:
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


class TextLayoutEngine:
    @staticmethod
    def calculate_text_bbox(
        text: str,
        font_size: int,
        font_family: str,
        canvas: CanvasConfig,
    ) -> BoundingBox:
        # Approximate text bounding box
        char_width = font_size * 0.6
        text_width = len(text) * char_width
        text_height = font_size * 1.2
        
        return BoundingBox(
            x=0.5 - (text_width / canvas.width) / 2,
            y=0.5 - (text_height / canvas.height) / 2,
            width=text_width / canvas.width,
            height=text_height / canvas.height,
        )

    @staticmethod
    def fit_text_to_region(
        text: str,
        region: BoundingBox,
        canvas: CanvasConfig,
        max_font_size: int = 200,
        min_font_size: int = 24,
    ) -> tuple[int, BoundingBox]:
        # Binary search for best font size
        low, high = min_font_size, max_font_size
        best_size = min_font_size
        best_bbox = None
        
        while low <= high:
            mid = (low + high) // 2
            bbox = TextLayoutEngine.calculate_text_bbox(text, mid, "Inter", canvas)
            
            if (bbox.width <= region.width * 0.9 and 
                bbox.height <= region.height * 0.9):
                best_size = mid
                best_bbox = bbox
                low = mid + 1
            else:
                high = mid - 1
        
        if best_bbox is None:
            best_bbox = TextLayoutEngine.calculate_text_bbox(text, min_font_size, "Inter", canvas)
        
        return best_size, best_bbox