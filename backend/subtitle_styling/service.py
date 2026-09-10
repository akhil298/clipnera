from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from core.logging_config import get_logger
from core.exceptions import CustomException
from video_processor.ffmpeg_service import FFmpegService

log = get_logger(__name__)

STYLE_PRESETS = {
    "bold_captions": {
        "font": "Arial",
        "font_size": 24,
        "font_color": "white",
        "stroke_color": "black",
        "stroke_width": 2,
        "box": True,
        "box_color": "black@0.5",
        "box_border_width": 8,
        "alignment": 2,
        "margin_v": 40,
    },
    "karaoke": {
        "font": "Arial",
        "font_size": 28,
        "font_color": "yellow",
        "stroke_color": "black",
        "stroke_width": 3,
        "box": False,
        "alignment": 2,
        "margin_v": 50,
    },
    "minimal": {
        "font": "Arial",
        "font_size": 20,
        "font_color": "white",
        "stroke_color": "black",
        "stroke_width": 1,
        "box": False,
        "alignment": 2,
        "margin_v": 30,
    },
    "boxed": {
        "font": "Arial",
        "font_size": 22,
        "font_color": "white",
        "stroke_color": "white",
        "stroke_width": 0,
        "box": True,
        "box_color": "black@0.8",
        "box_border_width": 10,
        "alignment": 2,
        "margin_v": 45,
    },
    "neon": {
        "font": "Arial",
        "font_size": 26,
        "font_color": "#00ffcc",
        "stroke_color": "#00ffcc",
        "stroke_width": 2,
        "box": False,
        "alignment": 2,
        "margin_v": 40,
        "shadow": True,
    },
    "typewriter": {
        "font": "Courier New",
        "font_size": 20,
        "font_color": "#e0e0e0",
        "stroke_color": "black",
        "stroke_width": 1,
        "box": False,
        "alignment": 2,
        "margin_v": 30,
    },
}


class SubtitleStylingService:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def burn_subtitles(self, video_path: str, clip_start: float, clip_end: float, style_type: str = "bold_captions", custom_config: Optional[dict] = None, subtitles: Optional[list[dict]] = None, title_text: Optional[str] = None, enable_watermark: bool = True) -> str:
        config = {**STYLE_PRESETS.get(style_type, STYLE_PRESETS["bold_captions"])}
        if custom_config:
            config.update(custom_config)

        duration = clip_end - clip_start
        if duration <= 0:
            raise ValueError("Invalid clip duration")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, f"burned_{Path(video_path).stem}.mp4")
            filter_str = self._build_ass_filter(config)
            srt_path = self._generate_srt(subtitles or [], clip_start, output_dir=tmpdir)
            srt_file = os.path.basename(srt_path)
            escaped_srt = srt_file.replace(":", "\\:").replace("'", "\\'")

            if enable_watermark:
                watermark_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "watermark.png")
                if os.path.exists(watermark_path):
                    inputs = ["-ss", str(clip_start), "-i", video_path, "-i", watermark_path]
                    filter_parts = [f"[0:v]subtitles={escaped_srt}:force_style='{filter_str}'"]
                    if title_text:
                        safe_title = title_text.replace("'", "\\'").replace(":", "\\:")
                        filter_parts.append(f"drawtext=text='{safe_title}':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=20")
                    filter_parts.append("[1:v]overlay=x=W-w-10:y=10")
                    vf = ",".join(filter_parts)
                    cmd = [
                        "ffmpeg", "-y",
                        *inputs,
                        "-t", str(duration),
                        "-filter_complex", vf,
                        "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart",
                        output_path,
                    ]
                else:
                    log.warning(f"Watermark file not found: {watermark_path}")
                    inputs = ["-ss", str(clip_start), "-i", video_path]
                    filters = [f"subtitles={escaped_srt}:force_style='{filter_str}'"]
                    if title_text:
                        safe_title = title_text.replace("'", "\\'").replace(":", "\\:")
                        filters.append(f"drawtext=text='{safe_title}':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=20")
                    vf = ",".join(filters)
                    cmd = [
                        "ffmpeg", "-y",
                        *inputs,
                        "-t", str(duration),
                        "-vf", vf,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart",
                        output_path,
                    ]
            else:
                inputs = ["-ss", str(clip_start), "-i", video_path]
                filters = [f"subtitles={escaped_srt}:force_style='{filter_str}'"]
                if title_text:
                    safe_title = title_text.replace("'", "\\'").replace(":", "\\:")
                    filters.append(f"drawtext=text='{safe_title}':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=20")
                vf = ",".join(filters)
                cmd = [
                    "ffmpeg", "-y",
                    *inputs,
                    "-t", str(duration),
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    output_path,
                ]

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=tmpdir
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="ignore")[-500:]
                raise CustomException(message=f"FFmpeg burn-in failed: {err}", code="BURN_IN_FAILED", status_code=500)

            if not os.path.exists(output_path):
                raise CustomException(message="Burned video not created", code="BURN_IN_FAILED", status_code=500)

            return output_path

    def _generate_srt(self, subtitles: list[dict], clip_start: float, output_dir: str | None = None) -> str:
        import tempfile
        lines = []
        for i, sub in enumerate(subtitles, 1):
            start = max(0.0, sub.get("start", 0) - clip_start)
            end = max(start, sub.get("end", 0) - clip_start)
            text = sub.get("text", "").strip()
            speaker = sub.get("speaker")
            if speaker:
                text = f"<b>{speaker}:</b> {text}"
            lines.append(f"{i}")
            lines.append(f"{self._srt_time(start)} --> {self._srt_time(end)}")
            lines.append(text)
            lines.append("")

        target_dir = output_dir or tempfile.gettempdir()
        srt_path = os.path.join(target_dir, f"subs_{os.getpid()}_{id(lines)}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return srt_path

    def _srt_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _build_ass_filter(self, config: dict) -> str:
        parts = []
        if config.get("font"):
            parts.append(f"FontName={config['font']}")
        if config.get("font_size"):
            parts.append(f"FontSize={config['font_size']}")
        if config.get("font_color"):
            parts.append(f"PrimaryColour=&H{self._color_to_ass(config['font_color'])}")
        if config.get("stroke_color"):
            parts.append(f"OutlineColour=&H{self._color_to_ass(config['stroke_color'])}")
        if config.get("stroke_width"):
            parts.append(f"Outline={config['stroke_width']}")
        if config.get("shadow") is False:
            parts.append("Shadow=0")
        elif config.get("shadow") is True:
            parts.append("Shadow=2")
        if config.get("box"):
            parts.append("Bold=1")
            parts.append("BackColour=&H00000000")
            parts.append(f"MarginV={config.get('margin_v', 40)}")
        if config.get("alignment"):
            parts.append(f"Alignment={config['alignment']}")
        return ",".join(parts)

    def _color_to_ass(self, color: str) -> str:
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            a = "FF"
        elif len(c) == 8:
            r, g, b, a = c[0:2], c[2:4], c[4:6], c[6:8]
        else:
            return "FFFFFF"
        return f"{a}{b}{g}{r}".upper()

    async def get_style_presets(self) -> list[dict]:
        presets = []
        for style_type, config in STYLE_PRESETS.items():
            presets.append({
                "style_type": style_type,
                "name": style_type.replace("_", " ").title(),
                "config": config,
            })
        return presets
