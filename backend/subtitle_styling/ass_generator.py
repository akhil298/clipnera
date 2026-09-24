from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Any

from core.logging_config import get_logger
from subtitle_styling.emoji_annotator import annotate_caption_words
from subtitle_styling.templates import get_template

log = get_logger(__name__)

CAPTION_SAFE_WIDTH = 0.90
DEFAULT_WIN_SPAN_RATIO = 1.75
# Bundled caption faces (SIL OFL / Apache 2.0), so styles render identically on
# any host instead of depending on what fontconfig happens to have installed.
FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"
WATERMARK_PATH = Path(__file__).resolve().parent.parent / "static" / "watermark.png"


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ass_filter(ass_path: str) -> str:
    """FFmpeg ``ass`` filter for a file in the working directory, with the
    bundled fonts available to libass."""
    return f"ass={_escape_filter_value(Path(ass_path).name)}:fontsdir={_escape_filter_value(str(FONTS_DIR))}"


def burn_filter_args(video_filters: list[str], enable_watermark: bool) -> list[str]:
    """FFmpeg args applying ``video_filters`` to input 0, plus the watermark.

    Place them after the source video's ``-i``. The graph is labelled
    explicitly: chaining ``...,[1:v]overlay`` bound the watermark as the base
    layer, so the burned clip came out at the watermark's 300x60 size.
    """
    chain = ",".join(video_filters)
    if not enable_watermark:
        return ["-vf", chain]
    if not WATERMARK_PATH.exists():
        log.warning("Watermark requested but file not found: %s", WATERMARK_PATH)
        return ["-vf", chain]
    graph = f"[0:v]{chain}[base];[base][1:v]overlay=x=W-w-10:y=10[v]"
    return [
        "-i", str(WATERMARK_PATH),
        "-filter_complex", graph,
        "-map", "[v]", "-map", "0:a?",
    ]


def ass_time(sec: float) -> str:
    clamped = max(0.0, sec)
    h = math.floor(clamped / 3600)
    m = math.floor((clamped % 3600) / 60)
    s = math.floor(clamped % 60)
    cs = math.floor((clamped - math.floor(clamped)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass(hex_color: str) -> str:
    """'#RRGGBB' -> ASS '&HBBGGRR&'."""
    clean = hex_color.lstrip("#")
    if len(clean) >= 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    return f"&H{b}{g}{r}&".upper()


def _hex_to_ass_style(hex_color: str) -> str:
    """'#RRGGBB' -> ASS '&H00BBGGRR' (style color with zero alpha)."""
    clean = hex_color.lstrip("#")
    if len(clean) >= 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    return f"&H00{b}{g}{r}".upper()


def _hex_to_ass_alpha_style(hex_color: str, alpha_hex: str) -> str:
    clean = hex_color.lstrip("#")
    if len(clean) >= 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    return f"&H{alpha_hex}{b}{g}{r}".upper()


def ass_font_size(em_px: float, win_span_ratio: float | None = None) -> int:
    ratio = win_span_ratio if win_span_ratio is not None else DEFAULT_WIN_SPAN_RATIO
    return max(4, round(em_px * ratio))


def escape_ass(text: str) -> str:
    return (
        text.replace("\\", "")
        .replace("{", "")
        .replace("}", "")
        .replace("\n", " ")
    )


def caption_layout_budget(max_words_per_line: int, width: int, height: int) -> int:
    safe_width = int(width * CAPTION_SAFE_WIDTH)
    approx_char_width = max(1, round(width / (max_words_per_line * 6 + 10)))
    return max(8, min(40, safe_width // approx_char_width))


def group_words(
    words: list[dict[str, Any]],
    max_chars: int,
    max_words: int,
) -> list[list[dict[str, Any]]]:
    """Group flat word list into display lines based on character budget."""
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0

    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        word_len = len(text)

        if current and (current_chars + 1 + word_len > max_chars or len(current) >= max_words):
            groups.append(current)
            current = []
            current_chars = 0

        if current:
            current_chars += 1
        current_chars += word_len
        current.append(word)

    if current:
        groups.append(current)
    return groups


class AssGenerator:
    """Generates ASS subtitle files with word-level karaoke highlighting.

    Ported from ClipForge's captions.ts approach: one ASS Dialogue event per
    word, showing the whole group with the active word emphasised. libass
    renders this as "Opus Clip" style animated captions when burned in.
    """

    def __init__(self) -> None:
        pass

    def build_ass(
        self,
        transcript_words: list[dict[str, Any]],
        clip_start: float,
        clip_end: float,
        style_id: str = "default",
        width: int = 1080,
        height: int = 1920,
        title: str | None = None,
        ai_cues: list[dict[str, Any]] | None = None,
        animation_speed: float = 1.0,
        emoji_collection: str | None = None,
        style_overrides: dict[str, Any] | None = None,
    ) -> str:
        template = {**get_template(style_id), **(style_overrides or {})}

        # Templates are authored against a 1080-wide vertical frame. Scaling by
        # height made the same template 1.78x larger on 9:16 (h=1920) than on
        # 16:9 (h=1080); width is the stable axis across 9:16, 1:1 and 4:5.
        font_size_em = template["font_size"] * width / 1080.0
        font_size = ass_font_size(font_size_em)

        caption_x = round(width / 2)
        caption_y = round(template["position_y"] * height)
        margin_h = round(width * (1 - CAPTION_SAFE_WIDTH) / 2)

        primary_color = _hex_to_ass_style(template["font_color"])
        outline_color = (
            _hex_to_ass_style(template["stroke_color"])
            if template.get("stroke_color")
            else primary_color
        )
        back_color = "&H80000000"

        if template.get("background") and template.get("background_color"):
            bg = _hex_to_ass_alpha_style(template["background_color"], "40")
            if len(bg) == 10:
                back_color = bg

        highlight_color = _hex_to_ass_style(template["highlight_color"])
        emphasis_color = (
            _hex_to_ass_style(template["emphasis_color"])
            if template.get("emphasis_color")
            else None
        )

        outline_width = max(1, round(template.get("stroke_width", 3) * 0.8))
        shadow_width = round(template.get("stroke_width", 3)) if template.get("shadow", True) else 0

        # --- Build header ---
        header_lines = [
            "[Script Info]",
            "Title: ClipForge captions",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            (
                f"Style: Caption,{template['font_family']},{font_size},"
                f"{primary_color},{primary_color},{outline_color},{back_color},"
                f"{1 if template.get('bold', True) else 0},0,0,0,100,100,0,0,1,"
                f"{outline_width},{shadow_width},5,{margin_h},{margin_h},0,1"
            ),
        ]

        if template.get("glow", False):
            glow_outline = 2
            header_lines.append(
                f"Style: Glow,{template['font_family']},{font_size + 2},"
                f"{highlight_color},{highlight_color},{outline_color},"
                f"&H00000000,0,0,0,0,100,100,0,0,1,{glow_outline},0,5,{margin_h},{margin_h},0,1"
            )

        # Same width-based scale as the captions, so the editor preview can
        # size both from one rule.
        hook_font_size = ass_font_size(template["title_font_size"] * width / 1080.0)
        title_margin_v = round(template["title_position_y"] * height)
        title_margin_h = round(width * 0.1)
        title_box_pad = max(6, round(height * 0.009))
        title_shadow = max(2, round(height * 0.0032))

        header_lines.extend([
            "",
            f"Style: Title,{template['font_family']},{hook_font_size},"
            f"&H00FFFFFF,&H00FFFFFF,&H40000000,&H40000000,-1,0,0,0,100,100,0,0,3,"
            f"{title_box_pad},{title_shadow},8,{title_margin_h},{title_margin_h},{title_margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

        lines: list[str] = []
        clip_duration = clip_end - clip_start

        if title and title.strip():
            from subtitle_styling.emoji_annotator import inject_collection_emojis
            styled_title = inject_collection_emojis(title.strip(), emoji_collection)
            # The title is the clip's static headline, so it holds for the whole
            # clip; only the word captions below it move. It used to vanish after
            # four seconds, which read as a glitch rather than a headline.
            lines.append(
                f"Dialogue: 1,{ass_time(0)},{ass_time(max(0.0, clip_duration))},Title,,0,0,0,,"
                f"{{\\fad(200,0)}}{escape_ass(styled_title)}"
            )

        if not transcript_words:
            return "\n".join(header_lines) + "\n"

        words_in_clip = []
        for word in transcript_words:
            w_start = float(word.get("start", 0))
            w_end = float(word.get("end", 0))
            if w_end <= clip_start or w_start >= clip_end:
                continue
            words_in_clip.append({
                "text": str(word.get("text", "")).strip(),
                "start": w_start,
                "end": w_end,
            })

        if not words_in_clip:
            return "\n".join(header_lines) + "\n"

        max_chars = caption_layout_budget(template["max_words_per_line"], width, height)
        groups = group_words(words_in_clip, max_chars, template["max_words_per_line"])

        emoji_by_index, emphasis_indices = annotate_caption_words(
            words_in_clip, ai_cues,
            enable_emoji=template.get("emoji", False),
            enable_emphasis=True,
        )

        cap_idx = 0
        for gi, group in enumerate(groups):
            group_start = max(0.0, group[0]["start"] - clip_start)
            last_word_end = max(0.0, group[-1]["end"] - clip_start)
            if gi + 1 < len(groups):
                next_word_start = max(0.0, groups[gi + 1][0]["start"] - clip_start)
                group_end = max(last_word_end, min(next_word_start, last_word_end + 0.5))
            else:
                group_end = clip_duration

            anchor = f"{{\\an5\\q2\\pos({caption_x},{caption_y})}}"

            for wi, word in enumerate(group):
                w_start_clip = max(0.0, word["start"] - clip_start)
                if wi < len(group) - 1:
                    w_end_clip = max(0.0, group[wi + 1]["start"] - clip_start)
                else:
                    w_end_clip = group_end

                if w_end_clip <= w_start_clip:
                    w_end_clip = max(w_start_clip + 0.01, w_end_clip)

                rendered = self._render_group(
                    group=group,
                    active_index=wi,
                    cap_index=cap_idx,
                    emphasis_indices=emphasis_indices,
                    emoji_by_index=emoji_by_index,
                    template=template,
                    highlight_color=highlight_color,
                    emphasis_color=emphasis_color,
                    box_color=_hex_to_ass_style(template["word_box_color"])
                    if template.get("word_box") and template.get("word_box_color")
                    else None,
                    primary_color=primary_color,
                    outline_width=max(1, round(template.get("stroke_width", 3))),
                    animation_speed=animation_speed,
                )

                lines.append(
                    f"Dialogue: 0,{ass_time(w_start_clip)},{ass_time(w_end_clip)}"
                    f",Caption,,0,0,0,,{anchor}{rendered}"
                )
                cap_idx += 1

        return "\n".join(header_lines) + "\n" + "\n".join(lines) + "\n"

    def _render_group(
        self,
        group: list[dict[str, Any]],
        active_index: int,
        cap_index: int,
        emphasis_indices: set[int],
        emoji_by_index: dict[int, str],
        template: dict[str, Any],
        highlight_color: str,
        emphasis_color: str | None,
        box_color: str | None,
        primary_color: str,
        outline_width: int,
        animation_speed: float = 1.0,
    ) -> str:
        parts: list[str] = []
        for i, word in enumerate(group):
            is_active = i == active_index
            is_emphasized = cap_index + i in emphasis_indices and not is_active
            raw = escape_ass(word.get("text", ""))
            text = raw.upper() if template.get("uppercase", False) else raw
            if not text:
                parts.append("{\\r}")
                continue

            if is_active:
                # Scale pop animation duration by animation_speed (default 70ms at 1.0x)
                pop_duration = max(10, round(70 / animation_speed))
                pop = f"\\t(0,{pop_duration},\\fscx109\\fscy109)"
                if box_color:
                    parts.append(
                        f"{{\\c{highlight_color}\\bord{outline_width}\\3c{box_color}"
                        f"\\fscx100\\fscy100{pop}}}{text}{{\\r}}"
                    )
                else:
                    parts.append(
                        f"{{\\c{highlight_color}\\fscx100\\fscy100{pop}}}{text}{{\\r}}"
                    )
            elif is_emphasized and emphasis_color:
                parts.append(f"{{\\c{emphasis_color}}}{text}{{\\r}}")
            else:
                parts.append(f"{{\\c{primary_color}}}{text}{{\\r}}")

        return " ".join(parts)

    def burn_subtitles_ass(
        self,
        video_path: str,
        output_path: str,
        ass_path: str,
        clip_start: float = 0.0,
        duration: float | None = None,
        enable_watermark: bool = True,
    ) -> str:
        ffmpeg = _FFmpegHelper()
        return ffmpeg.burn_ass(
            video_path=video_path,
            output_path=output_path,
            ass_path=ass_path,
            clip_start=clip_start,
            duration=duration,
            enable_watermark=enable_watermark,
        )


class _FFmpegHelper:
    """Wraps FFmpeg ASS-based burn-in with the standard encoding params used
    elsewhere in the codebase."""

    def burn_ass(
        self,
        video_path: str,
        output_path: str,
        ass_path: str,
        clip_start: float = 0.0,
        duration: float | None = None,
        enable_watermark: bool = True,
    ) -> str:
        import asyncio
        from pathlib import Path

        cmd = self._build_cmd(video_path, output_path, ass_path, clip_start, duration, enable_watermark)

        async def _run() -> None:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="ignore")[-500:]
                log.error(f"FFmpeg ASS burn-in failed: {err}")
                raise RuntimeError(f"FFmpeg ASS burn-in failed: {err}")

        asyncio.run(_run())
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Burned output not created: {output_path}")
        return output_path

    def _build_cmd(
        self,
        video_path: str,
        output_path: str,
        ass_path: str,
        clip_start: float,
        duration: float | None,
        enable_watermark: bool,
    ) -> list[str]:
        time_args: list[str] = ["-t", str(duration)] if duration else []
        return [
            "ffmpeg", "-y",
            "-ss", str(clip_start), "-i", video_path,
            *burn_filter_args([ass_filter(ass_path)], enable_watermark),
            *time_args,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]


def build_ass_file(
    transcript_words: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    style_id: str = "default",
    width: int = 1080,
    height: int = 1920,
    title: str | None = None,
    ai_cues: list[dict[str, Any]] | None = None,
    output_path: str | None = None,
    animation_speed: float = 1.0,
    emoji_collection: str | None = None,
    style_overrides: dict[str, Any] | None = None,
) -> str:
    """Generate an ASS subtitle file and return its path."""
    generator = AssGenerator()
    ass_content = generator.build_ass(
        transcript_words=transcript_words,
        clip_start=clip_start,
        clip_end=clip_end,
        style_id=style_id,
        width=width,
        height=height,
        title=title,
        ai_cues=ai_cues,
        animation_speed=animation_speed,
        emoji_collection=emoji_collection,
        style_overrides=style_overrides,
    )

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        return output_path

    fd, tmp = tempfile.mkstemp(suffix=".ass", prefix="captions_")
    os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return tmp
