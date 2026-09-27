from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from clip_generation.hook import Hook, Span, body_duration, on_output_timeline
from hook_transitions.graph import BridgePlan, MediaInfo, timeline_graph
from hook_transitions.resolver import TransitionSpec
from hook_transitions.text import write_bridge_ass
from core.database import AsyncSessionLocal
from core.logging_config import get_logger
from core.exceptions import CustomException
from video_processor.ffmpeg_service import FFmpegService
from subtitle_styling.ass_generator import (
    CAPTION_ANIMATIONS, DEFAULT_FONT_FILE, FONTS_DIR, AssGenerator, ass_filter, build_ass_file, bundled_family, burn_filter_args,
    escape_filter_value, script_font,
)
from subtitle_styling.templates import get_template, get_template_info, get_template_names
from subtitle_styling.phrase_segmenter import segment_phrases, segment_for_captions
from subtitle_styling.schema import SubtitleBurnRequest
from subscription.service import SubscriptionService, require_caption_style, require_hook_transition

log = get_logger(__name__)

# Editor custom_config key -> (template key, min, max, scale). Ranges mirror the
# editor's sliders; positions arrive as a percentage of frame height.
_STYLE_OVERRIDE_FIELDS: dict[str, tuple[str, float, float, float]] = {
    "font_size": ("font_size", 8, 72, 1.0),
    "position_y": ("position_y", 20, 90, 0.01),
    "title_font_size": ("title_font_size", 24, 96, 1.0),
    "title_position_y": ("title_position_y", 2, 40, 0.01),
}


# Editor custom_config key -> template key. The inverse of the mapping in
# export_styles.py, so an unedited preset burns exactly as its template.
_STYLE_COLOR_FIELDS: dict[str, str] = {
    "font_color": "font_color",
    "highlight_color": "highlight_color",
    "secondary_highlight_color": "emphasis_color",
    "bg_box_color": "background_color",
}
_STYLE_FLAG_FIELDS: dict[str, str] = {
    "has_bg_box": "background",
    "uppercase": "uppercase",
    "emojis_enabled": "emoji",
}
_GENERIC_FONT_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}


def _css_color_to_hex(value: Any) -> Optional[str]:
    """'#RGB', '#RRGGBB[AA]' or 'rgb[a](r,g,b[,a])' -> '#RRGGBB'; None if unparseable.

    The ASS colour helpers slice hex digits blindly, so the editor's default
    ``rgba(0,0,0,0.85)`` box colour would otherwise burn as garbage.
    """
    text = str(value or "").strip().lower()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits[:3])
        digits = digits[:6]
        if len(digits) == 6 and all(c in "0123456789abcdef" for c in digits):
            return f"#{digits.upper()}"
        return None
    if text.startswith("rgb") and "(" in text and text.endswith(")"):
        try:
            channels = [int(float(p)) for p in text[text.index("(") + 1:-1].split(",")[:3]]
        except ValueError:
            return None
        if len(channels) == 3:
            return "#" + "".join(f"{min(255, max(0, c)):02X}" for c in channels)
    return None


def _style_overrides(custom_config: Optional[dict]) -> dict[str, Any]:
    """Template overrides for everything the editor lets users set.

    Without these the burner used the template's own values whatever the
    editor said, so the export never matched the preview.
    """
    config = custom_config or {}
    overrides: dict[str, Any] = {}
    for key, (template_key, low, high, scale) in _STYLE_OVERRIDE_FIELDS.items():
        try:
            value = float(config[key])
        except (KeyError, TypeError, ValueError):
            continue
        overrides[template_key] = min(high, max(low, value)) * scale

    for key, template_key in _STYLE_COLOR_FIELDS.items():
        color = _css_color_to_hex(config.get(key))
        if color:
            overrides[template_key] = color

    for key, template_key in _STYLE_FLAG_FIELDS.items():
        if isinstance(config.get(key), bool):
            overrides[template_key] = config[key]

    try:
        overrides["max_words_per_line"] = min(8, max(1, int(config["max_words_per_line"])))
    except (KeyError, TypeError, ValueError):
        pass

    # The animation picked in the editor; without this every export used the
    # preset's own animation whatever the user chose.
    if config.get("animation") in CAPTION_ANIMATIONS:
        overrides["animation"] = config["animation"]

    try:
        overrides["shadow"] = float(config["shadow_intensity"]) > 0
    except (KeyError, TypeError, ValueError):
        pass

    # The editor holds a CSS font stack; libass wants one family name.
    family = str(config.get("font_family") or "").split(",")[0].strip().strip("'\"")
    if family and family.lower() not in _GENERIC_FONT_FAMILIES:
        overrides["font_family"] = family
    return overrides

async def prepare_burn_payload(user_id: str, data: SubtitleBurnRequest) -> dict:
    """The burn request clamped to the caller's plan, counted as one export.

    Shared by every route that burns captions, since each is reachable
    directly and the editor only hides locked options.
    """
    payload = data.model_dump()
    # The model itself, not its dump: a dump marks every unset field as sent,
    # which would override the preset's parts with blanks.
    payload["hook_transition"] = data.hook_transition

    async with AsyncSessionLocal() as session:
        subscription_service = SubscriptionService.for_session(session)
        entitlements = await subscription_service.get_entitlements(user_id)

        require_caption_style(entitlements, payload.get("style_type"))
        if data.hook_transition:
            require_hook_transition(entitlements, data.hook_transition.mode)
        await subscription_service.consume_daily_quota(user_id, "exports")

    if entitlements.watermark_forced:
        payload["enable_watermark"] = True
    return payload


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
        hook: Optional[Hook] = None,
        transition: Optional[TransitionSpec] = None,
        spans: Optional[list[Span]] = None,
    ) -> str:
        """Burn captions (and the watermark) into a cut clip.

        ``transition`` re-lays the clip as ``[hook][bridge][clip]`` in the same
        pass; it only applies when the clip has a ``hook`` to bridge from.
        ``spans`` are the source ranges a stitched body was cut from.
        """
        # FFmpeg runs with cwd set to a scratch dir (for the bare caption
        # filename), so a relative clip path like generated_clips/... would not
        # resolve there.
        video_path = str(Path(video_path).resolve())
        await self._ffmpeg.require_caption_support()
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
                animation_speed, emoji_collection, _style_overrides(custom_config), hook, transition, spans,
            )
        return await self._burn_with_srt(
            video_path, clip_start, clip_end, style_type, custom_config,
            subtitles, title_text, enable_watermark, hook, transition, spans,
        )

    async def render_uncaptioned(
        self,
        video_path: str,
        clip_start: float,
        clip_end: float,
        enable_watermark: bool,
        hook: Optional[Hook] = None,
        transition: Optional[TransitionSpec] = None,
        spans: Optional[list[Span]] = None,
    ) -> str:
        """Re-encode a cut clip without captions: watermark and transition only.

        Returns a new file the caller owns; ``video_path`` is left untouched.
        """
        video_path = str(Path(video_path).resolve())
        clip_end = clip_start + body_duration(clip_start, clip_end, spans)
        with tempfile.TemporaryDirectory() as tmpdir:
            media = await self._media(video_path)
            timeline, gap = self._bridge(media, hook, transition, tmpdir)
            origin, _ = on_output_timeline([], clip_start, clip_end, hook, gap)
            return await self._encode(
                video_path, ["null"], enable_watermark, clip_end - origin, tmpdir, timeline,
                label="plain", media=media, error_code="EXPORT_FAILED",
            )

    async def _media(self, video_path: str) -> MediaInfo:
        return MediaInfo.from_probe(await self._ffmpeg.get_video_info(video_path))

    @staticmethod
    def _bridge(
        media: MediaInfo,
        hook: Optional[Hook],
        transition: Optional[TransitionSpec],
        work_dir: str,
    ) -> tuple[Optional[tuple[list[str], str, str]], float]:
        """The hook transition's filter timeline and its length; (None, 0) if none applies."""
        plan = BridgePlan.make(transition, hook.duration if hook else None, media)
        if plan is None:
            return None, 0.0
        text_filter = None
        if plan.spec.text:
            name = write_bridge_ass(plan.spec.text, plan.spec.text_style, media.width, media.height, plan.gap, work_dir)
            text_filter = ass_filter(name)
        return timeline_graph(plan, text_filter), plan.gap

    async def _encode(
        self,
        video_path: str,
        video_filters: list[str],
        enable_watermark: bool,
        duration: float,
        work_dir: str,
        timeline: Optional[tuple[list[str], str, str]],
        label: str,
        media: MediaInfo,
        error_code: str = "BURN_IN_FAILED",
    ) -> str:
        """Run one render in ``work_dir`` and return a copy the caller owns."""
        output_path = os.path.join(work_dir, f"{label}_{Path(video_path).stem}.mp4")
        cmd = self._encode_cmd(
            video_path, output_path, video_filters, duration, enable_watermark, timeline,
            frame_size=(media.width, media.height),
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=work_dir
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(output_path):
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise CustomException(message=f"FFmpeg {label} render failed: {err}", code=error_code, status_code=500)

        final_path = os.path.join(tempfile.gettempdir(), f"{label}_{Path(video_path).name}")
        shutil.copy2(output_path, final_path)
        return final_path

    @staticmethod
    def _encode_cmd(
        video_path: str,
        output_path: str,
        video_filters: list[str],
        duration: float,
        enable_watermark: bool,
        timeline: Optional[tuple[list[str], str, str]] = None,
        frame_size: Optional[tuple[int, int]] = None,
    ) -> list[str]:
        # No -ss: the input is already the trimmed clip. veryfast renders about
        # twice as fast as fast at the same quality. This is the last encode
        # the viewer sees, so CRF 18 keeps it visually lossless against the cut.
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            *burn_filter_args(video_filters, enable_watermark, timeline, frame_size),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

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
        style_overrides: Optional[dict[str, Any]] = None,
        hook: Optional[Hook] = None,
        transition: Optional[TransitionSpec] = None,
        spans: Optional[list[Span]] = None,
    ) -> str:
        template_name = style_type
        if not get_template_names().__contains__(style_type):
            from subtitle_styling.model import SubtitleStyleType
            template_name = SubtitleStyleType.to_template(style_type)

        media = await self._media(video_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            timeline, gap = self._bridge(media, hook, transition, tmpdir)
            # video_path is the already-cut clip, whose timeline starts at zero,
            # while clip_start/clip_end are absolute positions in the source video.
            # The offset belongs in the ASS timings only; applying it to FFmpeg as
            # well seeks past the end of the clip and loses subtitle sync entirely.
            # A teaser (and any bridge) ahead of the clip moves where the output
            # starts in source time; rebasing against that origin keeps every
            # word in sync.
            body_start = clip_start
            clip_start, words = on_output_timeline(
                self._extract_words_for_ass(transcript_segments), clip_start, clip_end, hook, gap, spans,
            )
            clip_end = body_start + body_duration(body_start, clip_end, spans)
            duration = max(0.0, clip_end - clip_start)
            if duration <= 0:
                raise CustomException(
                    message="Cannot burn subtitles into a zero-length clip",
                    code="INVALID_CLIP_RANGE", status_code=400,
                )

            # The ass filter receives the bare filename and runs with cwd set
            # here, to dodge Windows drive-letter escaping in the filter string,
            # so the .ass file has to be written into this directory.
            ass_path = build_ass_file(
                transcript_words=words,
                clip_start=clip_start,
                clip_end=clip_end,
                style_id=template_name,
                width=media.width,
                height=media.height,
                title=title_text,
                ai_cues=ai_cues,
                animation_speed=animation_speed,
                emoji_collection=emoji_collection,
                style_overrides=style_overrides,
                # Where the hook teaser ends: no caption line may run across it.
                segment_breaks=_segment_breaks(clip_start, body_start, hook, spans),
                output_path=os.path.join(tmpdir, "captions.ass"),
            )
            return await self._encode(
                video_path, [ass_filter(ass_path)], enable_watermark, duration, tmpdir, timeline,
                label="burned", media=media,
            )

    @staticmethod
    def _extract_words_for_ass(segments: list[dict]) -> list[dict[str, Any]]:
        words: list[dict[str, Any]] = []
        for seg in segments:
            if seg.get("words"):
                for w in seg["words"]:
                    word = {
                        "start": float(w.get("start", w.get("s", 0.0))),
                        "end": float(w.get("end", w.get("e", 0.0))),
                        "text": str(w.get("word", w.get("text", ""))),
                    }
                    # Set by Transcript-tab edits; the burner emphasises these.
                    if "highlighted" in w:
                        word["highlighted"] = bool(w["highlighted"])
                    words.append(word)
            else:
                words.append({
                    "start": float(seg.get("start", 0.0)),
                    "end": float(seg.get("end", 0.0)),
                    "text": str(seg.get("text", "")),
                })
        words.sort(key=lambda w: w["start"])
        return words

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
        hook: Optional[Hook] = None,
        transition: Optional[TransitionSpec] = None,
        spans: Optional[list[Span]] = None,
    ) -> str:
        """Burn SRT subtitles using a force_style preset.

        As with the ASS path, ``video_path`` is the already-cut clip, so the
        clip offset is applied to the subtitle timings only and never as an
        FFmpeg seek.
        """
        config = self._srt_config_from_template(style_type)
        if custom_config:
            config.update(custom_config)
        spoken = " ".join(str(sub.get("text") or "") for sub in subtitles or [])
        caption_font = script_font(f"{spoken} {title_text or ''}")
        config["font"] = caption_font[0] if caption_font else bundled_family(str(config.get("font") or ""))

        media = await self._media(video_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline, gap = self._bridge(media, hook, transition, tmpdir)
            body_start = clip_start
            clip_start, subtitles = on_output_timeline(subtitles or [], clip_start, clip_end, hook, gap, spans)
            clip_end = body_start + body_duration(body_start, clip_end, spans)
            duration = clip_end - clip_start
            if duration <= 0:
                raise ValueError("Invalid clip duration")

            filter_str = self._build_ass_filter(config)
            srt_path = self._generate_srt(subtitles, clip_start, output_dir=tmpdir)
            escaped_srt = os.path.basename(srt_path).replace(":", r"\:").replace("'", r"\'")

            fonts_dir = escape_filter_value(str(FONTS_DIR))
            filters = [f"subtitles={escaped_srt}:fontsdir={fonts_dir}:force_style='{filter_str}'"]
            if title_text:
                safe_title = title_text.replace("'", r"\'").replace(":", r"\:")
                title_font = script_font(title_text)
                title_file = title_font[1] if title_font else DEFAULT_FONT_FILE
                filters.append(
                    f"drawtext=fontfile={fonts_dir}/{title_file}:text='{safe_title}':fontcolor=white:fontsize=36:"
                    "box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=20"
                )
            return await self._encode(
                video_path, filters, enable_watermark, duration, tmpdir, timeline,
                label="burned_srt", media=media,
            )

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
        """'#RRGGBB[AA]' -> ASS 'AABBGGRR'. ASS alpha counts transparency, so
        opaque is 00; writing FF here made every SRT caption invisible."""
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
            a = "00"
        elif len(c) == 8:
            r, g, b = c[0:2], c[2:4], c[4:6]
            a = f"{255 - int(c[6:8], 16):02X}"
        else:
            return "00FFFFFF"
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


def _segment_breaks(
    origin: float, body_start: float, hook: Optional[Hook], spans: Optional[list[Span]],
) -> Optional[list[float]]:
    """Times on the words' timeline no caption line may run across.

    The teaser's end and every join between stitched spans are picture cuts;
    a caption spanning one would show words from both sides of the cut.
    """
    breaks: list[float] = []
    if hook:
        breaks.append(origin + hook.duration)
    if spans:
        cursor = body_start
        for start, end in spans[:-1]:
            cursor += end - start
            breaks.append(cursor)
    return breaks or None
