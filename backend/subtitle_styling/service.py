from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from core.logging_config import get_logger
from core.exceptions import CustomException
from video_processor.ffmpeg_service import FFmpegService
from subtitle_styling.ass_generator import AssGenerator, build_ass_file
from subtitle_styling.templates import get_template, get_template_info, get_template_names
from subtitle_styling.phrase_segmenter import segment_phrases, segment_for_captions

log = get_logger(__name__)

class SubtitleStylingService:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()
        self._ass_generator = AssGenerator()

    async def burn_subtitles(
        self,
        video_path: str,
        clip_start: float,
        clip_end: float,
        style_type: str = "bold_captions",
        custom_config: Optional[dict] = None,
        subtitles: Optional[list[dict]] = None,
        title_text: Optional[str] = None,
        enable_watermark: bool = True,
        transcript_segments: Optional[list[dict]] = None,
        ai_cues: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        # Extract animation_speed and emoji_collection from custom_config if provided
        animation_speed = 1.0
        emoji_collection = None
        if custom_config and isinstance(custom_config, dict):
            if "animation_speed" in custom_config:
                try:
                    animation_speed = float(custom_config["animation_speed"])
                except (ValueError, TypeError):
                    animation_speed = 1.0
            emoji_collection = custom_config.get("emoji_collection")
        
        if self._is_template_style(style_type) and transcript_segments is not None:
            return await self._burn_with_ass(
                video_path, clip_start, clip_end, style_type, title_text,
                enable_watermark, transcript_segments, ai_cues,
                animation_speed, emoji_collection,
            )
        return await self._burn_with_srt(
            video_path, clip_start, clip_end, style_type, custom_config,
            subtitles, title_text, enable_watermark,
        )

    @staticmethod
    def _is_template_style(style_type: str) -> bool:
        from subtitle_styling.model import SubtitleStyleType
        return SubtitleStyleType.is_template(style_type)

    async def _burn_with_ass(
        self,
        video_path: str,
        clip_start: float,
        clip_end: float,
        style_type: str,
        title_text: Optional[str],
        enable_watermark: bool,
        transcript_segments: list[dict],
        ai_cues: Optional[list[dict[str, Any]]] = None,
        animation_speed: float = 1.0,
        emoji_collection: Optional[str] = None,
    ) -> str:
        template_name = style_type
        if not get_template_names().__contains__(style_type):
            from subtitle_styling.model import SubtitleStyleType
            template_name = SubtitleStyleType.to_template(style_type)

        video_info = await self._ffmpeg.get_video_info(video_path)
        streams = video_info.get("streams") or []
        stream = next(
            (s for s in streams if s.get("codec_type") == "video"),
            streams[0] if streams else {},
        )
        width = int(stream.get("width", 1080))
        height = int(stream.get("height", 1920))

        # video_path is the already-cut clip, whose timeline starts at zero,
        # while clip_start/clip_end are absolute positions in the source video.
        # The offset belongs in the ASS timings only; applying it to FFmpeg as
        # well seeks past the end of the clip and loses subtitle sync entirely.
        duration = max(0.0, clip_end - clip_start)
        if duration <= 0:
            raise CustomException(
                message="Cannot burn subtitles into a zero-length clip",
                code="INVALID_CLIP_RANGE", status_code=400,
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, f"burned_{Path(video_path).stem}.mp4")
            # The subtitles filter receives the bare filename and runs with cwd
            # set here, to dodge Windows drive-letter escaping in the filter
            # string, so the .ass file has to be written into this directory.
            ass_path = build_ass_file(
                transcript_words=self._extract_words_for_ass(transcript_segments),
                clip_start=clip_start,
                clip_end=clip_end,
                style_id=template_name,
                width=width,
                height=height,
                title=title_text,
                ai_cues=ai_cues,
                animation_speed=animation_speed,
                emoji_collection=emoji_collection,
                output_path=os.path.join(tmpdir, "captions.ass"),
            )

            async def _burn() -> None:
                cmd = self._build_ass_cmd(
                    video_path, output_path, ass_path, duration, enable_watermark, tmpdir,
                )
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=tmpdir
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    err = stderr.decode("utf-8", errors="ignore")[-500:]
                    raise CustomException(
                        message=f"FFmpeg ASS burn-in failed: {err}",
                        code="BURN_IN_FAILED", status_code=500,
                    )

            await _burn()

            if not os.path.exists(output_path):
                raise CustomException(message="Burned video not created", code="BURN_IN_FAILED", status_code=500)

            final_path = os.path.join(tempfile.gettempdir(), f"burned_{Path(video_path).name}")
            shutil.copy2(output_path, final_path)
            return final_path

    @staticmethod
    def _extract_words_for_ass(segments: list[dict]) -> list[dict[str, Any]]:
        words: list[dict[str, Any]] = []
        for seg in segments:
            if seg.get("words"):
                for w in seg["words"]:
                    words.append({
                        "start": float(w.get("start", w.get("s", 0.0))),
                        "end": float(w.get("end", w.get("e", 0.0))),
                        "text": str(w.get("word", w.get("text", ""))),
                    })
            else:
                words.append({
                    "start": float(seg.get("start", 0.0)),
                    "end": float(seg.get("end", 0.0)),
                    "text": str(seg.get("text", "")),
                })
        words.sort(key=lambda w: w["start"])
        return words

    def _build_ass_cmd(
        self,
        video_path: str,
        output_path: str,
        ass_path: str,
        duration: float,
        enable_watermark: bool,
        work_dir: str,
    ) -> list[str]:
        static_dir = Path(__file__).resolve().parent.parent / "static"
        watermark_path = static_dir / "watermark.png"
        has_watermark = enable_watermark and watermark_path.exists()

        # No -ss: the input is already the trimmed clip.
        inputs = ["-i", video_path]
        if has_watermark:
            inputs.extend(["-i", str(watermark_path)])

        ass_file = Path(ass_path).name
        ass_escaped = ass_file.replace(":", "\\:")

        vf_parts = [f"ass={ass_escaped}"]
        if has_watermark:
            vf_parts.append("[1:v]overlay=x=W-w-10:y=10")
        vf = ",".join(vf_parts)

        if has_watermark:
            return [
                "ffmpeg", "-y",
                *inputs, "-t", str(duration),
                "-filter_complex", vf,
                "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ]
        return [
            "ffmpeg", "-y",
            *inputs, "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

    async def _burn_with_srt(
        self,
        video_path: str,
        clip_start: float,
        clip_end: float,
        style_type: str,
        custom_config: Optional[dict],
        subtitles: Optional[list[dict]],
        title_text: Optional[str],
        enable_watermark: bool,
    ) -> str:
        """Burn SRT subtitles using a force_style preset.

        As with the ASS path, ``video_path`` is the already-cut clip, so the
        clip offset is applied to the subtitle timings only and never as an
        FFmpeg seek.
        """
        config = self._srt_config_from_template(style_type)
        if custom_config:
            config.update(custom_config)

        duration = clip_end - clip_start
        if duration <= 0:
            raise ValueError("Invalid clip duration")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, f"burned_{Path(video_path).stem}.mp4")
            filter_str = self._build_ass_filter(config)
            srt_path = self._generate_srt(subtitles or [], clip_start, output_dir=tmpdir)
            escaped_srt = os.path.basename(srt_path).replace(":", r"\:").replace("'", r"\'")

            watermark_path = Path(__file__).resolve().parent.parent / "static" / "watermark.png"
            has_watermark = enable_watermark and watermark_path.exists()
            if enable_watermark and not has_watermark:
                log.warning("Watermark requested but file not found: %s", watermark_path)

            filters = [f"subtitles={escaped_srt}:force_style='{filter_str}'"]
            if title_text:
                safe_title = title_text.replace("'", r"\'").replace(":", r"\:")
                filters.append(
                    f"drawtext=text='{safe_title}':fontcolor=white:fontsize=36:"
                    "box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=20"
                )

            # No -ss: the input is already the trimmed clip.
            inputs = ["-i", video_path]
            if has_watermark:
                inputs.extend(["-i", str(watermark_path)])
                filters.insert(0, "[0:v]")
                filters.append("[1:v]overlay=x=W-w-10:y=10")

            filter_arg = "-filter_complex" if has_watermark else "-vf"
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-t", str(duration),
                filter_arg, ",".join(filters),
                *(["-map", "0:a?"] if has_watermark else []),
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

            final_path = os.path.join(tempfile.gettempdir(), f"burned_srt_{Path(video_path).name}")
            shutil.copy2(output_path, final_path)
            return final_path

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

    @staticmethod
    def _srt_config_from_template(style_type: str) -> dict:
        """Map a caption template onto SRT force_style fields.

        The SRT path is the fallback used when no word timings are available;
        deriving it from the same template keeps a style recognisable instead of
        silently becoming a different one.
        """
        from subtitle_styling.model import SubtitleStyleType

        template = get_template(SubtitleStyleType.to_template(style_type))
        return {
            "font": template["font_family"],
            "font_size": template["font_size"],
            "font_color": template["font_color"],
            "stroke_color": template["stroke_color"],
            "stroke_width": template["stroke_width"],
            "box": bool(template["background"]),
            "box_color": template["background_color"],
            "shadow": bool(template["shadow"]),
            "alignment": 2,
            "margin_v": max(10, int((1.0 - template["position_y"]) * 400)),
        }

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
        """Every caption style, as the picker should show them."""
        return [
            {
                "style_type": item["id"],
                "name": item["name"],
                "description": item["description"],
                "config": get_template(item["id"]),
                "uses_ass": True,
            }
            for item in get_template_info()
        ]

    async def get_caption_templates(self) -> list[dict[str, Any]]:
        return get_template_info()

    async def generate_phrase_segments(
        self,
        transcript_segments: list[dict[str, Any]],
        min_duration: float = 5.0,
        max_duration: float = 15.0,
        max_gap: float = 1.5,
        pad: float = 0.08,
    ) -> list[dict[str, Any]]:
        return segment_phrases(
            transcript_segments,
            min_duration=min_duration,
            max_duration=max_duration,
            max_gap=max_gap,
            pad=pad,
        )

    async def generate_caption_segments(
        self,
        transcript_segments: list[dict[str, Any]],
        max_chars: int = 42,
        max_words_per_line: int = 7,
    ) -> list[dict[str, Any]]:
        return segment_for_captions(
            transcript_segments,
            max_chars=max_chars,
            max_words_per_line=max_words_per_line,
        )
