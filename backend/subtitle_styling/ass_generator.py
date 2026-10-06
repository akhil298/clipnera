from __future__ import annotations

import itertools
import math
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import ImageFont

from core.logging_config import get_logger
from hook_transitions.graph import Timeline
from subtitle_styling.emoji_annotator import annotate_caption_words
from subtitle_styling.emoji_art import EMOJI, GHOST, colourize
from subtitle_styling.templates import DEFAULT_STYLE, get_template
from transcription.language import script_of

log = get_logger(__name__)

CAPTION_SAFE_WIDTH = 0.90
# libass sizes a face by its (usWinAscent + usWinDescent) / unitsPerEm span
# while CSS sizes it by its em, so a template's px size, which the editor
# previews as an em, burns at the em times its face's span. One shared ratio
# drew a short-span face like Roboto half as large again as its preview.
FONT_WIN_SPAN: dict[str, float] = {
    "Anton": 1.733, "Archivo Black": 1.347, "Montserrat ExtraBold": 1.562, "Montserrat": 1.562, "Bangers": 1.757, "Bebas Neue": 1.3,
    "Courier Prime": 1.318, "DM Serif Display": 1.371, "DejaVu Sans": 1.164,
    "DejaVu Sans Mono": 1.164, "DejaVu Serif": 1.175, "Luckiest Guy": 1.226,
    "Permanent Marker": 1.427, "Poppins Black": 1.762, "Roboto": 1.2,
    "Noto Naskh Arabic": 2.039, "Noto Sans Bengali": 1.403, "Noto Sans Devanagari": 1.906,
    "Noto Sans Gujarati": 1.484, "Noto Sans Gurmukhi": 1.304, "Noto Sans Kannada": 1.645,
    "Noto Sans Malayalam": 1.247, "Noto Sans Tamil": 1.24, "Noto Sans Telugu": 1.478,
}
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
    "Montserrat ExtraBold": (0.666, 0.551),
    "Montserrat": (0.660, 0.540),
    "Permanent Marker": (0.611, 0.508),
    "Poppins Black": (0.596, 0.527),
    "Courier Prime": (0.600, 0.600),
    "Roboto": (0.565, 0.455),
}
# An unlisted face is assumed as wide as the widest listed one, so it errs
# toward shorter lines rather than off the frame.
DEFAULT_CHAR_EM = (0.712, 0.602)
# Room for the active word's pop scale, outlines and wide letters (M, W).
CAPTION_WIDTH_MARGIN = 1.15
# A caption line ends where the speaker does: after a word closing a clause, or
# before a pause this long, so no line carries one thought into the next.
PHRASE_PAUSE_SECONDS = 0.35
CLAUSE_ENDINGS = (".", ",", "?", "!", ";", ":", "…")
# Trimmed from both ends of a displayed word; apostrophes, %, $ and inner
# punctuation (U.S., 3.5) stay.
DISPLAY_TRIM = ".,?!;:…\"“”—–"
# Bundled caption faces (SIL OFL / Apache 2.0), so styles render identically on
# any host instead of depending on what fontconfig happens to have installed.
FONTS_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "fonts"
# The headline is a hook: dark semibold text on a white rounded card for the
# opening seconds, then it clears off the speaker. Mirrored by the title card in
# the frontend preview (StudioCanvas).
TITLE_FAMILY, TITLE_FONT_FILE = "Montserrat", "Montserrat-Bold.ttf"
TITLE_TEXT_COLOUR = "&H00141414"
TITLE_CARD_COLOUR = "&H00FFFFFF"
TITLE_SECONDS = 5.0
TITLE_FADE_IN_MS, TITLE_FADE_OUT_MS = 150, 250
# Card padding around the text and its corner radius, in ems of the title.
TITLE_PAD_X, TITLE_PAD_Y, TITLE_RADIUS = 1.0, 0.42, 0.22
# Baseline to baseline between title lines, and room kept under the last
# baseline for descenders (g, y), in ems. libass would space lines by the
# face's whole ascent-to-descent span, which in Montserrat leaves a gap.
TITLE_LINE_PITCH, TITLE_DESCENT_ROOM = 1.22, 0.24
# An emoji in the title is drawn this share of the ASS font size: about the
# letters' height, where the full size would tower over them.
TITLE_EMOJI_SCALE = 0.62
# The card spans at most this much of the frame width.
TITLE_MAX_WIDTH = 0.8
# A headline reads as one or two lines; a longer one gets smaller, down to this
# share of its set size, before it may take a third line.
TITLE_MAX_LINES = 2
TITLE_MIN_SCALE = 0.7
TITLE_SHRINK_STEP = 0.94
# Control-point offset that makes a cubic Bezier a quarter circle.
KAPPA = 0.5523
# Display faces carry Latin glyphs only; captions in these scripts switch to a
# bundled Noto face instead of rendering as empty boxes. Covers every script the
# transcriber can emit (see transcription.language._LANGUAGE_CODES).
SCRIPT_FONT_FILES = {
    "devanagari": ("Noto Sans Devanagari", "NotoSansDevanagari-Bold.ttf"),
    "telugu": ("Noto Sans Telugu", "NotoSansTelugu-Bold.ttf"),
    "tamil": ("Noto Sans Tamil", "NotoSansTamil-Bold.ttf"),
    "kannada": ("Noto Sans Kannada", "NotoSansKannada-Bold.ttf"),
    "malayalam": ("Noto Sans Malayalam", "NotoSansMalayalam-Bold.ttf"),
    "bengali": ("Noto Sans Bengali", "NotoSansBengali-Bold.ttf"),
    "gujarati": ("Noto Sans Gujarati", "NotoSansGujarati-Bold.ttf"),
    "gurmukhi": ("Noto Sans Gurmukhi", "NotoSansGurmukhi-Bold.ttf"),
    "arabic": ("Noto Naskh Arabic", "NotoNaskhArabic-Bold.ttf"),
}


# The server's static FFmpeg has no fontconfig, so libass sees only FONTS_DIR. A
# family missing from it fell through to an arbitrary bundled face, often a
# Noto Indic one without Latin letters, and English captions burned as boxes.
BUNDLED_FAMILIES = frozenset({
    "Anton", "Archivo Black", "Bangers", "Bebas Neue", "DM Serif Display", "Luckiest Guy",
    "Montserrat ExtraBold", "Montserrat", "Permanent Marker", "Poppins Black", "Courier Prime", "Roboto",
    "DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif",
})
# Faces bundled only as a heavy regular cut. Asking libass for bold on these
# would smear an already black face with synthetic emboldening, so they render
# at their own weight; every other bundled face ships a real bold cut.
UNBOLDED_FAMILIES = frozenset({
    "Anton", "Archivo Black", "Bangers", "Bebas Neue", "DM Serif Display", "Luckiest Guy",
    "Montserrat ExtraBold", "Permanent Marker", "Poppins Black",
})
# Closest bundled face for common families that cannot ship (Impact is proprietary).
FONT_SUBSTITUTES = {"Impact": "Anton", "Poppins": "Poppins Black", "Arial": "DejaVu Sans", "Helvetica": "DejaVu Sans", "Inter": "DejaVu Sans",
                    "Georgia": "DejaVu Serif", "Times New Roman": "DejaVu Serif", "Courier New": "DejaVu Sans Mono"}
DEFAULT_FAMILY = "DejaVu Sans"


def bundled_family(family: str) -> str:
    """``family`` if FONTS_DIR ships it, else its closest bundled substitute."""
    if family in BUNDLED_FAMILIES:
        return family
    return FONT_SUBSTITUTES.get(family, DEFAULT_FAMILY)


def font_weight(family: str) -> int:
    """CSS weight a bundled face renders at; the ASS bold flag follows it."""
    return 400 if family in UNBOLDED_FAMILIES else 700


def script_font(text: str) -> tuple[str, str] | None:
    """(family, bundled file) for text in a non-Latin script; None keeps the style's face."""
    return SCRIPT_FONT_FILES.get(script_of(text))


def escape_filter_value(value: str) -> str:
    return value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ass_filter(ass_path: str) -> str:
    """FFmpeg ``ass`` filter for a file in the working directory, with the
    bundled fonts available to libass."""
    return f"ass={escape_filter_value(Path(ass_path).name)}:fontsdir={escape_filter_value(str(FONTS_DIR))}"


def burn_filter_args(
    video_filters: list[str],
    timeline: Timeline | None = None,
) -> list[str]:
    """FFmpeg args applying ``video_filters`` to input 0.

    Place them after the source video's ``-i``. ``timeline`` is from
    ``hook_transitions.graph.timeline_graph``: when given, the filters apply to
    its re-laid output instead of the raw input, and its rebuilt audio is
    mapped; the source must then be given ``timeline.inputs`` times. The watermark is not burned here: ``branding.service`` adds it,
    with the intro and end card, to the finished file.
    """
    chain = ",".join(video_filters)
    if timeline is None:
        return ["-vf", chain]
    return [
        "-filter_complex", ";".join([*timeline.chains, f"[{timeline.video}]{chain}[v]"]),
        "-map", "[v]", "-map", f"[{timeline.audio}]",
    ]


# Caption animations the burner renders; the editor offers the same names.
CAPTION_ANIMATIONS = frozenset({
    "pop", "wave", "karaoke", "glow", "fade", "none",
    "land", "bounce", "grow", "blur", "shake", "breathe", "glitch",
})
# Glow templates soften their outline into a halo by this much.
GLOW_BLUR = 3


@dataclass(frozen=True)
class _Look:
    """A template resolved into the ASS values every caption word is drawn from."""

    animation: str
    speed: float
    primary: str
    highlight: str
    emphasis: str | None
    upcoming: str | None
    second_line: str | None
    second_scale: int
    hide_upcoming: bool
    # Pill behind the spoken word on a plate, or box behind it off one.
    pill: str | None
    word_box: str | None
    outline_width: int
    shadow_width: int
    active_scale: float
    word_pop: bool
    glow: bool
    uppercase: bool


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
    rise = round(height * 0.02)
    if animation in ("pop", "wave"):
        return f"{{\\an5\\q2\\move({x},{y + rise},{x},{y},0,{round(170 / speed)})\\fad({round(120 / speed)},0)}}"
    if animation == "land":
        # Settles down onto its spot from above.
        return f"{{\\an5\\q2\\move({x},{y - rise * 2},{x},{y},0,{round(260 / speed)})\\fad({round(200 / speed)},0)}}"
    if animation in ("fade", "glow", "blur"):
        return f"{{\\an5\\q2\\pos({x},{y})\\fad({round(200 / speed)},0)}}"
    if animation in ("bounce", "grow", "shake", "breathe", "glitch"):
        return f"{{\\an5\\q2\\pos({x},{y})\\fad({round(100 / speed)},0)}}"
    return None


def _word_entrance(animation: str, speed: float, scale: int, rest_blur: int) -> str:
    """Per-word tags for a line's entrance that a single anchor block cannot
    carry: every word ends in a reset, so a scale or blur must be set on each."""
    speed = max(0.25, speed)
    if animation == "bounce":
        ms = round(160 / speed)
        return (f"\\fscx{round(scale * 0.7)}\\fscy{round(scale * 0.7)}"
                f"\\t(0,{ms},\\fscx{round(scale * 1.08)}\\fscy{round(scale * 1.08)})"
                f"\\t({ms},{round(ms * 1.6)},\\fscx{scale}\\fscy{scale})")
    if animation == "grow":
        ms = round(140 / speed)
        return f"\\fscx{round(scale * 0.85)}\\fscy{round(scale * 0.85)}\\t(0,{ms},\\fscx{scale}\\fscy{scale})"
    if animation == "blur":
        return f"\\blur10\\t(0,{round(220 / speed)},\\blur{rest_blur})"
    return ""


def _contrast_on(ass_colour: str) -> str:
    """Black or white, whichever reads on an ASS '&HAABBGGRR' colour."""
    bgr = ass_colour.lstrip("&H").rstrip("&")[-6:]
    b, g, r = (int(bgr[i:i + 2], 16) for i in (0, 2, 4))
    return "&H00000000" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "&H00FFFFFF"


def _active_motion(look: _Look, scale: int) -> str:
    """Motion tags for the word being spoken, around its resting ``scale`` (%)."""
    speed = max(0.25, look.speed)
    grown = round(scale * look.active_scale)
    rest = f"\\fscx{scale}\\fscy{scale}"
    animation = look.animation
    if animation == "pop" and look.word_pop:
        ms = max(10, round(70 / speed))
        return f"{rest}\\t(0,{ms},\\fscx{grown}\\fscy{grown})"
    if animation == "wave":
        ms = max(10, round(90 / speed))
        return (f"{rest}\\t(0,{ms},\\fscx{round(scale * 1.06)}\\fscy{round(scale * 1.18)})"
                f"\\t({ms},{ms * 2},{rest})")
    if animation == "grow":
        ms = max(10, round(150 / speed))
        return f"{rest}\\t(0,{ms},0.5,\\fscx{grown}\\fscy{grown})"
    if animation == "breathe":
        ms = max(10, round(180 / speed))
        settle = round(scale * (1 + (look.active_scale - 1) / 2))
        return f"{rest}\\t(0,{ms},\\fscx{grown}\\fscy{grown})\\t({ms},{ms * 3},\\fscx{settle}\\fscy{settle})"
    if animation == "bounce":
        ms = max(10, round(70 / speed))
        return (f"{rest}\\t(0,{ms},\\fscx{round(scale * 0.92)}\\fscy{round(scale * 1.18)})"
                f"\\t({ms},{ms * 2},\\fscx{round(scale * 1.05)}\\fscy{round(scale * 0.95)})"
                f"\\t({ms * 2},{ms * 3},{rest})")
    if animation == "shake":
        ms = max(10, round(35 / speed))
        return "".join(f"\\t({i * ms},{(i + 1) * ms},\\frz{angle})" for i, angle in enumerate((4, -4, 3, -2, 0)))
    if animation == "glitch":
        # Skews and throws a cyan ghost sideways, then settles back.
        ms = max(10, round(45 / speed))
        steps = ((0.3, -6), (-0.25, 5), (0.12, -3), (0, look.shadow_width))
        return "\\4c&HFFFF00&\\4a&H00&" + "".join(
            f"\\t({i * ms},{(i + 1) * ms},\\fax{fax}\\xshad{x})" for i, (fax, x) in enumerate(steps)
        )
    if animation == "blur":
        ms = max(10, round(180 / speed))
        fade_in = f"\\alpha&HFF&\\t(0,{ms},\\alpha&H00&)" if look.hide_upcoming else ""
        return f"{fade_in}\\blur6\\t(0,{ms},\\blur{GLOW_BLUR if look.glow else 0})"
    return ""


def _row_split(group: list[dict[str, Any]], rows: int) -> int:
    """Index of the first word on the second row; ``len(group)`` for one row.

    The first row takes as many words as fit in half the line's characters and
    the second always keeps at least one, so a lone word lands on the second
    row, which is the larger or coloured one in stacked styles.
    """
    if rows < 2 or len(group) < 2:
        return 0 if rows >= 2 else len(group)
    half = (sum(len(w["text"]) for w in group) + len(group) - 1) / 2
    split, chars = 0, -1
    for word in group[:-1]:
        chars += len(word["text"]) + 1
        if split and chars > half:
            break
        split += 1
    return split


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


def ass_font_size(em_px: float, font_family: str) -> int:
    """The ASS Fontsize that draws ``font_family`` at an em of ``em_px``."""
    return max(4, round(em_px * FONT_WIN_SPAN.get(font_family, DEFAULT_WIN_SPAN_RATIO)))


def escape_ass(text: str) -> str:
    return (
        text.replace("\\", "")
        .replace("{", "")
        .replace("}", "")
        .replace("\n", " ")
    )


def char_width_px(font_family: str, em_px: float, uppercase: bool) -> float:
    """Typical on-screen width of one character at an em of ``em_px``, margin included."""
    upper, mixed = FONT_CHAR_EM.get(font_family, DEFAULT_CHAR_EM)
    return em_px * (upper if uppercase else mixed) * CAPTION_WIDTH_MARGIN


def caption_layout_budget(char_px: float, width: int) -> int:
    """Most characters a caption line holds inside the safe width."""
    return max(4, int(width * CAPTION_SAFE_WIDTH / char_px))


def fit_font_size(font_size: int, chars: int, char_px: float, max_width: float) -> int:
    """``font_size`` shrunk just enough for ``chars`` characters to fit ``max_width``.

    For text that cannot be broken further, such as one long word.
    """
    needed = chars * char_px
    return font_size if needed <= max_width else max(4, int(font_size * max_width / needed))


@lru_cache(maxsize=16)
def face_metrics(font_file: str) -> tuple[float, float]:
    """(descent libass sets below the baseline, cap height) of a bundled face, in ems."""
    from fontTools.ttLib import TTFont

    font = TTFont(FONTS_DIR / font_file, lazy=True)
    units, os2 = font["head"].unitsPerEm, font["OS/2"]
    return os2.usWinDescent / units, (getattr(os2, "sCapHeight", 0) or 0.7 * units) / units


@lru_cache(maxsize=64)
def _face(font_file: str, em_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / font_file), em_px)


def text_width(text: str, font_file: str, em_px: float, emoji_px: float) -> float:
    """Drawn width of ``text`` in a bundled face; an emoji is a square ``emoji_px`` wide."""
    emoji = EMOJI.findall(text)
    return _face(font_file, max(1, round(em_px))).getlength(EMOJI.sub("", text)) + emoji_px * len(emoji)


def title_words(title: str) -> list[str]:
    """``title``'s words, each emoji kept with the word beside it so it never
    ends up alone on a line."""
    words: list[str] = []
    for word in title.split():
        if words and not EMOJI.sub("", word).strip():
            words[-1] = f"{words[-1]} {word}"
        elif words and not EMOJI.sub("", words[-1]).strip():
            words[-1] = f"{words[-1]} {word}"
        else:
            words.append(word)
    return words


def wrap_title(title: str, measure: Any, max_width: float) -> list[str]:
    """``title`` broken between words into as few lines as fit ``max_width``,
    balanced so no line is left holding a lone word."""
    words = title_words(title)
    count = 0
    line = ""
    for word in words:
        candidate = f"{line} {word}" if line else word
        if line and measure(candidate) > max_width:
            count, line = count + 1, word
        else:
            line = candidate
    count += 1
    if count == 1:
        return [title.strip()]

    def split(breaks: tuple[int, ...]) -> list[str]:
        bounds = (0, *breaks, len(words))
        return [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]

    return min(
        (split(breaks) for breaks in itertools.combinations(range(1, len(words)), count - 1)),
        key=lambda lines: max(measure(line) for line in lines),
    )


def rounded_rect(w: float, h: float, r: float) -> str:
    """ASS drawing of a ``w`` x ``h`` rectangle with corners of radius ``r``, from its top-left."""
    r = min(r, w / 2, h / 2)
    k = r * (1 - KAPPA)
    points = [
        ("m", r, 0), ("l", w - r, 0), ("b", w - k, 0, w, k, w, r),
        ("l", w, h - r), ("b", w, h - k, w - k, h, w - r, h),
        ("l", r, h), ("b", k, h, 0, h - k, 0, h - r),
        ("l", 0, r), ("b", 0, k, k, 0, r, 0),
    ]
    return " ".join(f"{cmd} " + " ".join(str(round(v)) for v in values) for cmd, *values in points)


def _phrase_ends(previous: dict[str, Any], word: dict[str, Any]) -> bool:
    """Whether a caption line should end between ``previous`` and ``word``."""
    if str(previous.get("text", "")).strip().endswith(CLAUSE_ENDINGS):
        return True
    return float(word.get("start", 0.0)) - float(previous.get("end", 0.0)) >= PHRASE_PAUSE_SECONDS


def display_text(text: str) -> str:
    """A word as burned: its surrounding punctuation trimmed."""
    return text.strip().strip(DISPLAY_TRIM)


def group_words(
    words: list[dict[str, Any]],
    max_chars: int,
    max_words: int,
) -> list[list[dict[str, Any]]]:
    """Group flat word list into display lines: a character and word budget,
    broken early at clause ends and pauses."""
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0

    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        word_len = len(text)

        if current and (
            current_chars + 1 + word_len > max_chars
            or len(current) >= max_words
            or _phrase_ends(current[-1], word)
        ):
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
    """Generates ASS subtitle files with word-level highlighting.

    One ASS Dialogue event per word, showing the whole group with the active
    word emphasised; libass renders this as animated captions when burned in.
    """

    def __init__(self) -> None:
        pass

    def build_ass(
        self,
        transcript_words: list[dict[str, Any]],
        clip_start: float,
        clip_end: float,
        style_id: str = DEFAULT_STYLE,
        width: int = 1080,
        height: int = 1920,
        title: str | None = None,
        ai_cues: list[dict[str, Any]] | None = None,
        animation_speed: float = 1.0,
        emoji_collection: str | None = None,
        style_overrides: dict[str, Any] | None = None,
        segment_breaks: list[float] | None = None,
        seams: list[tuple[float, float, float]] | None = None,
        quiet: list[tuple[float, float]] | None = None,
    ) -> str:
        """``segment_breaks`` are times (on the words' timeline) where the picture
        cuts to a different segment, e.g. the end of the hook teaser; no caption
        line spans one, or it would carry the hook's words over into the clip.
        ``seams`` are ``(start, end, seam)`` stretches, in seconds from the
        clip's start, where two people are stacked: a line starting in one sits
        on the seam between them, as a share of the height, not over a face.
        ``quiet`` are ``(start, end)`` stretches, in seconds from the clip's
        start, where a motion graphic already shows what is said; caption lines
        overlapping one are left out so text never sits on text."""
        template = {**get_template(style_id), **(style_overrides or {})}
        # A stack starting or ending moves the captions, so no line spans that either.
        seam_edges = [clip_start + edge for low, high, _ in seams or [] for edge in (low, high)]
        breaks = sorted([*(segment_breaks or []), *seam_edges])
        spoken = " ".join(str(w.get("text") or w.get("word") or "") for w in transcript_words)
        fallback = script_font(f"{spoken} {title or ''}")
        template["font_family"] = fallback[0] if fallback else bundled_family(template["font_family"])
        bold = -1 if font_weight(template["font_family"]) >= 700 else 0
        italic = -1 if template.get("italic") else 0

        # Templates are authored against a 1080-wide vertical frame. Scaling by
        # height made the same template 1.78x larger on 9:16 (h=1920) than on
        # 16:9 (h=1080); width is the stable axis across 9:16, 1:1 and 4:5.
        font_size_em = template["font_size"] * width / 1080.0
        font_size = ass_font_size(font_size_em, template["font_family"])

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
        word_box_color = (
            _hex_to_ass_style(template["word_box_color"])
            if template.get("word_box") and template.get("word_box_color")
            else None
        )

        outline_width = max(1, round(template.get("stroke_width", 3) * 0.8))
        shadow_width = round(template.get("stroke_width", 3)) if template.get("shadow", True) else 0
        border_style = 1

        # A boxed template sits on a solid plate, as the editor preview draws
        # it. BorderStyle 3 makes libass paint the outline as an opaque box,
        # with the outline width as its padding.
        boxed = bool(template.get("background") and template.get("background_color"))
        if boxed:
            border_style = 3
            outline_color = back_color = _box_colour(template["background_color"])
            outline_width = max(4, round(font_size * 0.18))
            shadow_width = 0

        animation = template.get("animation")
        if animation not in CAPTION_ANIMATIONS:
            animation = "karaoke"

        look = _Look(
            animation=animation,
            speed=animation_speed,
            primary=primary_color,
            highlight=highlight_color,
            emphasis=emphasis_color,
            upcoming=_hex_to_ass_style(template["upcoming_color"]) if template.get("upcoming_color") else None,
            second_line=_hex_to_ass_style(template["second_line_color"]) if template.get("second_line_color") else None,
            second_scale=round(100 * float(template.get("second_line_scale") or 1.0)),
            hide_upcoming=bool(template.get("hide_upcoming")),
            # On a plate the spoken word's box is a pill in the plate; off one
            # it is drawn on a layer of its own, beneath the outlined text.
            pill=word_box_color if boxed else None,
            word_box=None if boxed else word_box_color,
            outline_width=max(1, round(template.get("stroke_width", 3))),
            shadow_width=shadow_width,
            active_scale=float(template.get("active_scale") or 1.0),
            word_pop=bool(template.get("word_pop", True)),
            glow=bool(template.get("glow")),
            uppercase=bool(template.get("uppercase")),
        )
        rows = max(1, int(template.get("rows") or 1))

        # --- Build header ---
        header_lines = [
            "[Script Info]",
            "Title: Clipnera captions",
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
                f"{bold},{italic},0,0,100,100,0,0,{border_style},"
                f"{outline_width},{shadow_width},5,{margin_h},{margin_h},0,1"
            ),
        ]
        if look.word_box:
            # Same face and size as Caption, so its boxes sit exactly behind
            # the words; box and text are transparent until a word is spoken.
            header_lines.append(
                f"Style: WordBox,{template['font_family']},{font_size},"
                f"&HFF000000,&HFF000000,&HFF000000,&HFF000000,"
                f"{bold},{italic},0,0,100,100,0,0,3,"
                f"{max(4, round(font_size * 0.14))},0,5,{margin_h},{margin_h},0,1"
            )

        lines: list[str] = []
        clip_duration = clip_end - clip_start
        title_margin_v = round(template["title_position_y"] * height)
        # Same width-based scale as the captions, so the editor preview can
        # size both from one rule. A script the title face lacks keeps the
        # captions' fallback face.
        title_family, title_file = fallback or (TITLE_FAMILY, TITLE_FONT_FILE)
        title_em = template["title_font_size"] * width / 1080.0
        if title and title.strip():
            from subtitle_styling.emoji_annotator import inject_collection_emojis
            styled_title = escape_ass(inject_collection_emojis(title.strip(), emoji_collection))
            title_lines, title_em = self._fit_title(styled_title, title_family, title_file, title_em, width)
        title_font_size = ass_font_size(title_em, title_family)

        header_lines.extend([
            "",
            f"Style: Title,{title_family},{title_font_size},"
            f"{TITLE_TEXT_COLOUR},{TITLE_TEXT_COLOUR},&H00000000,&H00000000,"
            f"{-1 if font_weight(title_family) >= 700 else 0},0,0,0,100,100,0,0,1,"
            f"0,0,8,0,0,{title_margin_v},1",
            f"Style: TitleCard,{title_family},{title_font_size},"
            f"{TITLE_CARD_COLOUR},{TITLE_CARD_COLOUR},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,"
            f"0,0,7,0,0,0,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

        if title and title.strip():
            lines.extend(self._title_card(
                title_lines, title_file, title_em, title_font_size, title_margin_v, width, min(TITLE_SECONDS, clip_duration),
            ))

        if not transcript_words:
            return colourize("\n".join(header_lines + lines) + "\n")

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
            return colourize("\n".join(header_lines + lines) + "\n")

        caption_char_px = char_width_px(template["font_family"], font_size_em, look.uppercase)
        # A stacked style spreads a line over its rows, so it holds more text.
        max_chars = caption_layout_budget(caption_char_px, width) * rows
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

            # A line too wide for the frame (one long word, or a stacked row) is
            # shrunk to fit; the second row counts at its own scale.
            row_start = _row_split(group, rows)
            first_row = group[:row_start]
            second_row = group[row_start:]
            # An emoji and its space take about three letters.
            row_chars = [
                (sum(len(w["text"]) + 3 * (cap_idx + start + j in emoji_by_index) for j, w in enumerate(row))
                 + len(row) - 1) * scale
                for row, start, scale in (
                    (first_row, 0, 1.0), (second_row, row_start, look.second_scale / 100 if rows > 1 else 1.0),
                )
                if row
            ]
            line_size = fit_font_size(font_size, math.ceil(max(row_chars)), caption_char_px, width * CAPTION_SAFE_WIDTH)
            size_tag = f"\\fs{line_size}" if line_size < font_size else ""
            size_block = f"{{{size_tag}}}" if size_tag else ""
            if any(group_start < high and low < group_end for low, high in quiet or []):
                cap_idx += len(group)
                continue
            line_y = next(
                (round(seam * height) for low, high, seam in seams or [] if low <= group_start < high), caption_y,
            )
            still = f"{{\\an5\\q2\\pos({caption_x},{line_y})}}"
            # Each caption line animates in once, on its first word's event;
            # the events for its later words hold it in place.
            entering = _entrance(animation, animation_speed, caption_x, line_y, height) or still

            for wi, word in enumerate(group):
                anchor = entering if wi == 0 else still
                w_start_clip = max(0.0, word["start"] - clip_start)
                if wi < len(group) - 1:
                    w_end_clip = max(0.0, group[wi + 1]["start"] - clip_start)
                else:
                    w_end_clip = group_end

                if w_end_clip <= w_start_clip:
                    w_end_clip = max(w_start_clip + 0.01, w_end_clip)

                timing = f"{ass_time(w_start_clip)},{ass_time(w_end_clip)}"
                render = dict(
                    group=group, active_index=wi, cap_index=cap_idx, row_start=row_start if rows > 1 else len(group),
                    emphasis_indices=emphasis_indices, emoji_by_index=emoji_by_index, look=look, entering=wi == 0, reset=f"\\r{size_tag}",
                )
                if look.word_box:
                    lines.append(
                        f"Dialogue: 0,{timing},WordBox,,0,0,0,,{anchor}{size_block}"
                        f"{self._render_group(**render, box_layer=True)}"
                    )
                lines.append(
                    f"Dialogue: 1,{timing},Caption,,0,0,0,,{anchor}{size_block}{self._render_group(**render)}"
                )
            # cap_idx is the index of each group's first word. Advancing it per
            # word event moved emphasis and emoji one word further along on
            # every line after a group's first.
            cap_idx += len(group)

        return colourize("\n".join(header_lines) + "\n" + "\n".join(lines) + "\n")

    @staticmethod
    def _fit_title(title: str, family: str, font_file: str, em: float, width: int) -> tuple[list[str], float]:
        """The title's lines and em: wrapped between words to the card's width,
        made smaller until it fits ``TITLE_MAX_LINES`` lines (or reaches
        ``TITLE_MIN_SCALE``), and smaller still if one word alone is too wide."""
        floor = em * TITLE_MIN_SCALE

        def layout(size: float) -> tuple[list[str], float, float]:
            inner = width * TITLE_MAX_WIDTH - 2 * TITLE_PAD_X * size
            emoji_px = ass_font_size(size, family) * TITLE_EMOJI_SCALE
            measure = lambda text: text_width(text, font_file, size, emoji_px)  # noqa: E731
            widest = max(measure(word) for word in title_words(title))
            return wrap_title(title, measure, inner), inner, widest

        lines, inner, widest = layout(em)
        while len(lines) > TITLE_MAX_LINES and em * TITLE_SHRINK_STEP >= floor:
            em *= TITLE_SHRINK_STEP
            lines, inner, widest = layout(em)
        if widest > inner:
            em *= inner / widest
            lines, _, _ = layout(em)
        return lines, em

    @staticmethod
    def _title_card(
        title_lines: list[str], font_file: str, em: float, font_size: int, top: int, width: int, seconds: float,
    ) -> list[str]:
        """Dialogue lines drawing the title: its white card, then each line of text on it.

        Lines are placed one by one at ``TITLE_LINE_PITCH``, each by its
        baseline so an emoji in it cannot push it down, and the card is sized
        from cap height and baselines, so the padding reads even.
        """
        descent, cap = face_metrics(font_file)
        emoji_size = max(1, round(font_size * TITLE_EMOJI_SCALE))
        text_w = max(text_width(line, font_file, em, emoji_size) for line in title_lines)
        card_w = text_w + 2 * TITLE_PAD_X * em
        first_baseline = top + (TITLE_PAD_Y + cap) * em
        card_h = (2 * TITLE_PAD_Y + cap + (len(title_lines) - 1) * TITLE_LINE_PITCH + TITLE_DESCENT_ROOM) * em
        left = round((width - card_w) / 2)
        timing = f"{ass_time(0)},{ass_time(max(0.0, seconds))}"
        fade = f"\\fad({TITLE_FADE_IN_MS},{TITLE_FADE_OUT_MS})"
        events = [
            f"Dialogue: 0,{timing},TitleCard,,0,0,0,,"
            f"{{\\an7\\pos({left},{top}){fade}\\p1}}{rounded_rect(card_w, card_h, TITLE_RADIUS * em)}{{\\p0}}",
        ]
        for index, line in enumerate(title_lines):
            # \an2 anchors a line's bottom, one descent below its baseline;
            # emoji drawings rest on the baseline, so they never move the line.
            line_bottom = first_baseline + (index * TITLE_LINE_PITCH + descent) * em
            text = EMOJI.sub(lambda m: f"{{\\fs{emoji_size}}}{m.group(0)}{{\\fs{font_size}}}", line)
            events.append(
                f"Dialogue: 2,{timing},Title,,0,0,0,,{{\\an2\\pos({round(width / 2)},{round(line_bottom)}){fade}}}{text}"
            )
        return events

    def _render_group(
        self,
        group: list[dict[str, Any]],
        active_index: int,
        cap_index: int,
        row_start: int,
        emphasis_indices: set[int],
        emoji_by_index: dict[int, str],
        look: _Look,
        entering: bool,
        reset: str = "\\r",
        box_layer: bool = False,
    ) -> str:
        """One caption line with the word at ``active_index`` spoken.

        Words from ``row_start`` on sit on a second row. ``entering`` adds the
        line's entrance to every word; ``reset`` ends each word's styling and
        carries any line-level size. ``box_layer`` renders the same layout with
        only the spoken word's box visible, to sit beneath the text. A word's
        emoji follows it; ``emoji_art.colourize`` later draws it in colour.
        """
        rows: list[list[str]] = [[], []]
        for i, word in enumerate(group):
            raw = escape_ass(display_text(word.get("text", "")))
            text = raw.upper() if look.uppercase else raw
            if not text:
                continue
            second_row = i >= row_start
            scale = look.second_scale if second_row else 100
            is_active = i == active_index and look.animation != "none"
            hidden = i > active_index and look.hide_upcoming
            if cap_index + i in emoji_by_index:
                # A hidden upcoming word's emoji keeps its place but is not drawn yet.
                text = f"{text} {GHOST if hidden else ''}{emoji_by_index[cap_index + i]}"

            tags = f"\\fscx{scale}\\fscy{scale}" if scale != 100 else ""
            if look.glow and not box_layer:
                tags += f"\\3c{look.highlight}\\blur{GLOW_BLUR}" if look.highlight != look.primary else f"\\blur{GLOW_BLUR}"
            if entering:
                tags += _word_entrance(look.animation, look.speed, scale, GLOW_BLUR if look.glow and not box_layer else 0)

            if box_layer:
                # Only the spoken word's box shows; its motion keeps the box
                # sized to the word above it.
                if is_active:
                    tags += f"\\3c{look.word_box}\\3a&H00&{_active_motion(look, scale)}"
            elif hidden:
                tags += "\\alpha&HFF&"
            elif is_active:
                tags += self._active_colour(look, second_row) + _active_motion(look, scale)
            else:
                tags += f"\\c{self._rest_colour(look, i, active_index, second_row, cap_index + i in emphasis_indices)}"
            rows[1 if second_row else 0].append(f"{{{tags}}}{text}{{{reset}}}")

        return "\\N".join(" ".join(row) for row in rows if row)

    @staticmethod
    def _active_colour(look: _Look, second_row: bool) -> str:
        """Colour tags for the spoken word. A coloured second row keeps its colour."""
        if look.pill:
            # On a plate: light the word with a pill. Text that would vanish
            # into a same-coloured pill keeps the base colour, and if that
            # matches too falls back to black or white.
            colour = next((c for c in (look.highlight, look.primary) if c != look.pill), None) or _contrast_on(look.pill)
            return f"\\c{colour}\\3c{look.pill}\\3a&H00&"
        colour = look.second_line if second_row and look.second_line else look.highlight
        if look.animation == "glow":
            return f"\\c{colour}\\3c{colour}\\bord{look.outline_width + 2}\\blur4"
        return f"\\c{colour}"

    @staticmethod
    def _rest_colour(look: _Look, index: int, active_index: int, second_row: bool, emphasised: bool) -> str:
        """Colour of a word that is not being spoken."""
        if second_row and look.second_line:
            return look.second_line
        if index > active_index and look.upcoming:
            return look.upcoming
        # On a plate the emphasis colour would fight the pill, so it is unused.
        if emphasised and look.emphasis and not look.pill:
            return look.emphasis
        return look.primary


def build_ass_file(
    transcript_words: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    style_id: str = DEFAULT_STYLE,
    width: int = 1080,
    height: int = 1920,
    title: str | None = None,
    ai_cues: list[dict[str, Any]] | None = None,
    output_path: str | None = None,
    animation_speed: float = 1.0,
    emoji_collection: str | None = None,
    style_overrides: dict[str, Any] | None = None,
    segment_breaks: list[float] | None = None,
    seams: list[tuple[float, float, float]] | None = None,
    quiet: list[tuple[float, float]] | None = None,
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
        seams=seams,
        quiet=quiet,
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
