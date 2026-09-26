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
# Mean advance per character, in em, as (all caps, sentence case), measured over
# English text with its spaces. Captions are drawn unwrapped (\q2), so a line's
# width must be known before it is laid out: a character count alone let a
# three-word line in a wide face run hundreds of pixels past the frame.
FONT_CHAR_EM: dict[str, tuple[float, float]] = {
    "Anton": (0.417, 0.406),
    "Archivo Black": (0.678, 0.551),
    "Bangers": (0.372, 0.372),
    "Bebas Neue": (0.341, 0.341),
    "DejaVu Sans": (0.672, 0.575),
    "DejaVu Sans Mono": (0.602, 0.602),
    "DejaVu Serif": (0.712, 0.570),
    "DM Serif Display": (0.534, 0.447),
    "Impact": (0.443, 0.407),
    "Luckiest Guy": (0.509, 0.513),
    "Permanent Marker": (0.611, 0.508),
}
# An unlisted face is assumed as wide as the widest listed one, so it errs
# toward shorter lines rather than off the frame.
DEFAULT_CHAR_EM = (0.712, 0.602)
# Room for the active word's pop scale, outlines and wide letters (M, W).
CAPTION_WIDTH_MARGIN = 1.15
# Bundled caption faces (SIL OFL / Apache 2.0), so styles render identically on
# any host instead of depending on what fontconfig happens to have installed.
FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts"
WATERMARK_PATH = Path(__file__).resolve().parent.parent / "static" / "watermark.png"
# Watermark width and corner inset as fractions of the frame's shorter side, so
# it reads the same on every export size. A fixed 300px mark was easy to miss
# on a 1080px-wide reel.
WATERMARK_WIDTH_RATIO = 0.26
WATERMARK_MARGIN_RATIO = 0.035


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ass_filter(ass_path: str) -> str:
    """FFmpeg ``ass`` filter for a file in the working directory, with the
    bundled fonts available to libass."""
    return f"ass={_escape_filter_value(Path(ass_path).name)}:fontsdir={_escape_filter_value(str(FONTS_DIR))}"


def burn_filter_args(
    video_filters: list[str],
    enable_watermark: bool,
    timeline: tuple[list[str], str, str] | None = None,
    frame_size: tuple[int, int] | None = None,
) -> list[str]:
    """FFmpeg args applying ``video_filters`` to input 0, plus the watermark.

    Place them after the source video's ``-i``. ``timeline`` is
    ``(chains, video_label, audio_label)`` from
    ``hook_transitions.graph.timeline_graph``: when given, the filters and
    watermark apply to its re-laid output instead of the raw input. The graph
    is labelled explicitly: chaining ``...,[1:v]overlay`` bound the watermark
    as the base layer, so the burned clip came out at the watermark's 300x60 size.
    ``frame_size`` is the output ``(width, height)``; the watermark scales to it.
    """
    chain = ",".join(video_filters)
    if enable_watermark and not WATERMARK_PATH.exists():
        log.warning("Watermark requested but file not found: %s", WATERMARK_PATH)
        enable_watermark = False
    if timeline is None and not enable_watermark:
        return ["-vf", chain]

    chains, video_in, audio_out = timeline if timeline else ([], "0:v", None)
    graph = [*chains, f"[{video_in}]{chain}[base]"]
    inputs: list[str] = []
    if enable_watermark:
        inputs = ["-i", str(WATERMARK_PATH)]
        short_side = min(frame_size) if frame_size else 1080
        width = round(short_side * WATERMARK_WIDTH_RATIO)
        margin = round(short_side * WATERMARK_MARGIN_RATIO)
        graph.append(f"[1:v]scale={width}:-2[wm]")
        graph.append(f"[base][wm]overlay=x=W-w-{margin}:y={margin}[v]")
    else:
        graph.append("[base]null[v]")
    return [
        *inputs,
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", f"[{audio_out}]" if audio_out else "0:a?",
    ]


# Caption animations the burner renders; the editor offers the same names.
CAPTION_ANIMATIONS = frozenset({"pop", "wave", "karaoke", "glow", "fade", "none"})


def _box_colour(css_hex: str, default_opacity: float = 0.75) -> str:
    """'#RRGGBB' or '#RRGGBBAA' -> ASS '&HAABBGGRR' for a caption plate.

    ASS alpha counts transparency, CSS alpha opacity, so the byte is inverted.
    """
    clean = css_hex.strip().lstrip("#")
    if len(clean) >= 8:
        opacity = int(clean[6:8], 16) / 255.0
    else:
        opacity = default_opacity
    r, g, b = (clean[0:2], clean[2:4], clean[4:6]) if len(clean) >= 6 else ("00", "00", "00")
    return f"&H{round((1.0 - opacity) * 255):02X}{b}{g}{r}".upper()


def _entrance(animation: str, speed: float, x: int, y: int, height: int) -> str | None:
    """Override block that animates a caption line onto the screen, or None."""
    speed = max(0.25, speed)
    if animation in ("pop", "wave"):
        rise = round(height * 0.02)
        ms = round(170 / speed)
        return f"{{\\an5\\q2\\move({x},{y + rise},{x},{y},0,{ms})\\fad({round(120 / speed)},0)}}"
    if animation in ("fade", "glow"):
        return f"{{\\an5\\q2\\pos({x},{y})\\fad({round(200 / speed)},0)}}"
    return None


def _active_word_tags(
    template: dict[str, Any],
    animation: str,
    speed: float,
    highlight: str,
    pill: str | None,
    word_box: str | None,
    outline_width: int,
    primary: str,
) -> str:
    """Override tags for the word being spoken, per animation style."""
    speed = max(0.25, speed)
    if pill:
        # On a plate: light the word with a pill. Text that would vanish into
        # a same-coloured pill keeps the base colour instead.
        colour = primary if pill == highlight else highlight
        tags = f"\\c{colour}\\3c{pill}\\3a&H00&"
    elif word_box:
        tags = f"\\c{highlight}\\bord{outline_width}\\3c{word_box}"
    else:
        tags = f"\\c{highlight}"

    if animation == "pop" and template.get("word_pop", True):
        ms = max(10, round(70 / speed))
        tags += f"\\fscx100\\fscy100\\t(0,{ms},\\fscx109\\fscy109)"
    elif animation == "wave":
        ms = max(10, round(90 / speed))
        tags += f"\\fscx100\\fscy100\\t(0,{ms},\\fscx106\\fscy118)\\t({ms},{ms * 2},\\fscx100\\fscy100)"
    elif animation == "glow" and not pill:
        tags += f"\\3c{highlight}\\bord{outline_width + 2}\\blur4"
    return tags


def _split_at_breaks(groups: list[list[dict[str, Any]]], breaks: list[float]) -> list[list[dict[str, Any]]]:
    """Split any caption line whose words straddle a segment break."""
    if not breaks:
        return groups
    split: list[list[dict[str, Any]]] = []
    for group in groups:
        current: list[dict[str, Any]] = []
        for word in group:
            if current and any(current[-1]["start"] < b <= word["start"] for b in breaks):
                split.append(current)
                current = []
            current.append(word)
        split.append(current)
    return split


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


def char_width_px(font_family: str, font_size: int, uppercase: bool) -> float:
    """Typical on-screen width of one character, margin included."""
    upper, mixed = FONT_CHAR_EM.get(font_family, DEFAULT_CHAR_EM)
    return font_size * (upper if uppercase else mixed) * CAPTION_WIDTH_MARGIN


def caption_layout_budget(char_px: float, width: int) -> int:
    """Most characters a caption line holds inside the safe width."""
    return max(4, int(width * CAPTION_SAFE_WIDTH / char_px))


def fit_font_size(font_size: int, chars: int, char_px: float, max_width: float) -> int:
    """``font_size`` shrunk just enough for ``chars`` characters to fit ``max_width``.

    For text that cannot be broken further, such as one long word.
    """
    needed = chars * char_px
    return font_size if needed <= max_width else max(4, int(font_size * max_width / needed))


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
        segment_breaks: list[float] | None = None,
    ) -> str:
        """``segment_breaks`` are times (on the words' timeline) where the picture
        cuts to a different segment, e.g. the end of the hook teaser; no caption
        line spans one, or it would carry the hook's words over into the clip."""
        template = {**get_template(style_id), **(style_overrides or {})}
        breaks = sorted(segment_breaks or [])

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

        highlight_color = _hex_to_ass_style(template["highlight_color"])
        emphasis_color = (
            _hex_to_ass_style(template["emphasis_color"])
            if template.get("emphasis_color")
            else None
        )

        outline_width = max(1, round(template.get("stroke_width", 3) * 0.8))
        shadow_width = round(template.get("stroke_width", 3)) if template.get("shadow", True) else 0
        border_style = 1

        # A boxed template sits on a solid plate, as the editor preview draws
        # it. BorderStyle 3 makes libass paint the outline as an opaque box,
        # with the outline width as its padding. This used to only tint the
        # drop shadow, so "background" templates burned with no plate at all.
        boxed = bool(template.get("background") and template.get("background_color"))
        pill_color: str | None = None
        if boxed:
            border_style = 3
            outline_color = back_color = _box_colour(template["background_color"])
            outline_width = max(4, round(font_size * 0.18))
            shadow_width = 0
            # The preview lights the active word with a pill in the secondary
            # highlight colour (emphasis, else highlight); the burn does the same.
            pill_color = emphasis_color or highlight_color

        animation = template.get("animation")
        if animation not in CAPTION_ANIMATIONS:
            animation = "karaoke"

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
                f"{1 if template.get('bold', True) else 0},0,0,0,100,100,0,0,{border_style},"
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
        if title and title.strip():
            # The title wraps between words, but a word longer than the line
            # would run off both edges, so the size gives way instead.
            longest = max(len(word) for word in title.split())
            title_char_px = char_width_px(template["font_family"], hook_font_size, title.isupper())
            hook_font_size = fit_font_size(hook_font_size, longest, title_char_px, width - 2 * title_margin_h)
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
            entry = {
                "text": str(word.get("text", "")).strip(),
                "start": w_start,
                "end": w_end,
            }
            if "highlighted" in word:
                entry["highlighted"] = bool(word["highlighted"])
            words_in_clip.append(entry)

        if not words_in_clip:
            return "\n".join(header_lines) + "\n"

        caption_char_px = char_width_px(template["font_family"], font_size, bool(template.get("uppercase")))
        max_chars = caption_layout_budget(caption_char_px, width)
        groups = _split_at_breaks(group_words(words_in_clip, max_chars, template["max_words_per_line"]), breaks)

        emoji_by_index, emphasis_indices = annotate_caption_words(
            words_in_clip, ai_cues,
            enable_emoji=template.get("emoji", False),
            enable_emphasis=True,
        )
        # Words highlighted in the editor's Transcript tab replace the automatic
        # picks, so the export emphasises exactly what the user saw.
        if any("highlighted" in w for w in words_in_clip):
            emphasis_indices = {i for i, w in enumerate(words_in_clip) if w.get("highlighted")}

        cap_idx = 0
        for gi, group in enumerate(groups):
            group_start = max(0.0, group[0]["start"] - clip_start)
            last_word_end = max(0.0, group[-1]["end"] - clip_start)
            if gi + 1 < len(groups):
                next_word_start = max(0.0, groups[gi + 1][0]["start"] - clip_start)
                group_end = max(last_word_end, min(next_word_start, last_word_end + 0.5))
            else:
                group_end = clip_duration
            # A line never outlives its segment (the hook must not hang over
            # the bridge that follows it).
            cut = next((b - clip_start for b in breaks if b > group[0]["start"]), None)
            if cut is not None:
                group_end = max(last_word_end, min(group_end, cut))

            # A line of one word too long for the frame is shrunk to fit.
            line_chars = sum(len(w["text"]) for w in group) + len(group) - 1
            line_size = fit_font_size(font_size, line_chars, caption_char_px, width * CAPTION_SAFE_WIDTH)
            size_tag = f"\\fs{line_size}" if line_size < font_size else ""
            size_block = f"{{{size_tag}}}" if size_tag else ""
            still = f"{{\\an5\\q2\\pos({caption_x},{caption_y})}}"
            # Each caption line animates in once, on its first word's event;
            # the events for its later words hold it in place.
            entering = _entrance(animation, animation_speed, caption_x, caption_y, height) or still

            for wi, word in enumerate(group):
                anchor = entering if wi == 0 else still
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
                    animation=animation,
                    pill_color=pill_color,
                    reset=f"\\r{size_tag}",
                )

                lines.append(
                    f"Dialogue: 0,{ass_time(w_start_clip)},{ass_time(w_end_clip)}"
                    f",Caption,,0,0,0,,{anchor}{size_block}{rendered}"
                )
            # cap_idx is the index of each group's first word. Advancing it per
            # word event moved emphasis and emoji one word further along on
            # every line after a group's first.
            cap_idx += len(group)

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
        animation: str = "pop",
        pill_color: str | None = None,
        reset: str = "\\r",
    ) -> str:
        """``reset`` ends each word's styling; it carries any line-level size."""
        parts: list[str] = []
        for i, word in enumerate(group):
            is_active = i == active_index
            is_emphasized = cap_index + i in emphasis_indices and not is_active
            raw = escape_ass(word.get("text", ""))
            text = raw.upper() if template.get("uppercase", False) else raw
            if not text:
                parts.append(f"{{{reset}}}")
                continue

            if is_active and animation != "none":
                parts.append(
                    f"{{{_active_word_tags(template, animation, animation_speed, highlight_color, pill_color, box_color, outline_width, primary_color)}}}"
                    f"{text}{{{reset}}}"
                )
            elif is_emphasized and emphasis_color and not pill_color:
                # On a plate the emphasis colour is the active word's pill, so
                # it is not also used for text.
                parts.append(f"{{\\c{emphasis_color}}}{text}{{{reset}}}")
            else:
                parts.append(f"{{\\c{primary_color}}}{text}{{{reset}}}")

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
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
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
    segment_breaks: list[float] | None = None,
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
        segment_breaks=segment_breaks,
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
