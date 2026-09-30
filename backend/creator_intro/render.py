"""The channel intro: its frames, its sound, and joining it to an export.

Six seconds on a plain page in the platform's own style: the avatar pops in,
the channel name and one line about the channel rise under it, then a cursor
clicks Like and the platform's main button (Subscribe, Follow) the way a viewer
would, while the platform-coloured progress bar runs along the bottom. Frames
are drawn with Pillow from pre-rendered pieces and piped to FFmpeg, so the
render needs nothing beyond what reels already use.
"""

from __future__ import annotations

import math
import re
import subprocess
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from creator_intro.platforms import Look
from hook_transitions.graph import MediaInfo
from subtitle_styling.ass_generator import FONTS_DIR, script_font

FPS = 30
DURATION_S = 6.0
# Renditions by the names branding.service.nearest picks between.
SIZES: dict[str, tuple[int, int]] = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}
# Pieces are drawn this many times larger, then shrunk, for smooth edges.
SUPERSAMPLE = 3

# When each beat happens, in seconds.
AVATAR_IN = (0.1, 0.7)
NAME_IN = (0.5, 1.1)
HANDLE_IN = (0.7, 1.3)
TAGLINE_IN = (0.85, 1.45)
BUTTONS_IN = (1.2, 1.8)
CURSOR_ENTERS, CURSOR_LEAVES = 1.9, 4.6
LIKE_CLICK, ACTION_CLICK = 2.7, 3.6
FADE_OUT = (5.3, DURATION_S)


@dataclass(frozen=True)
class Theme:
    background: str
    text: str
    muted: str
    chip: str
    track: str


THEMES: dict[str, Theme] = {
    "light": Theme("#FFFFFF", "#0F0F0F", "#606060", "#F2F2F2", "#E5E5E5"),
    "dark": Theme("#0F0F0F", "#F1F1F1", "#AAAAAA", "#272727", "#3F3F3F"),
}


@dataclass(frozen=True)
class IntroSpec:
    name: str
    tagline: str
    look: Look
    theme: str = "light"
    handle: str | None = None
    avatar: Path | None = None


# ---------- easing ----------

def _progress(t: float, span: tuple[float, float]) -> float:
    return min(1.0, max(0.0, (t - span[0]) / (span[1] - span[0])))


def _ease_out(k: float) -> float:
    return 1 - (1 - k) ** 3


def _ease_in_out(k: float) -> float:
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def _ease_back(k: float) -> float:
    c = 1.7
    return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


def _press(t: float, at: float) -> float:
    """Scale of a button (and the cursor) dipping as it is clicked at ``at``."""
    return 1 - 0.08 * math.sin(_progress(t, (at - 0.05, at + 0.15)) * math.pi)


# ---------- icons (Material icon paths, 24x24) ----------

THUMB = ("M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 "
         "7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23"
         ".14-.47.14-.73v-2z")
HEART = ("M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 "
         "3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z")
_TOKEN = re.compile(r"[MmLlHhVvCcSsZz]|-?(?:\d+\.?\d*|\.\d+)")


def path_polygons(d: str, steps: int = 12) -> list[list[tuple[float, float]]]:
    """Polygons for an SVG path using M/L/H/V/C/S/Z (absolute or relative)."""
    tokens, i = _TOKEN.findall(d), 0
    shapes: list[list[tuple[float, float]]] = []
    x = y = sx = sy = 0.0
    ctrl: tuple[float, float] | None = None
    cmd = ""

    def num() -> float:
        nonlocal i
        i += 1
        return float(tokens[i - 1])

    def cubic(c1, c2, end):
        p0 = (x, y)
        for s in range(1, steps + 1):
            k = s / steps
            a, b, c, e = (1 - k) ** 3, 3 * (1 - k) ** 2 * k, 3 * (1 - k) * k ** 2, k ** 3
            shapes[-1].append((a * p0[0] + b * c1[0] + c * c2[0] + e * end[0],
                               a * p0[1] + b * c1[1] + c * c2[1] + e * end[1]))

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd, i = tokens[i], i + 1
        rel = cmd.islower()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        op = cmd.upper()
        if op == "Z":
            x, y = sx, sy
            ctrl = None
            continue
        if op == "M":
            x, y = ox + num(), oy + num()
            sx, sy = x, y
            shapes.append([(x, y)])
            cmd = "l" if rel else "L"  # further pairs are line-tos
        elif op == "L":
            x, y = ox + num(), oy + num()
            shapes[-1].append((x, y))
        elif op == "H":
            x = ox + num()
            shapes[-1].append((x, y))
        elif op == "V":
            y = oy + num()
            shapes[-1].append((x, y))
        elif op in ("C", "S"):
            if op == "C":
                c1 = (ox + num(), oy + num())
            else:
                c1 = (2 * x - ctrl[0], 2 * y - ctrl[1]) if ctrl else (x, y)
            c2, end = (ox + num(), oy + num()), (ox + num(), oy + num())
            cubic(c1, c2, end)
            x, y = end
            ctrl = c2
            continue
        ctrl = None
    return [shape for shape in shapes if len(shape) > 2]


def _icon(path: str, size: int, color: str, filled: bool) -> Image.Image:
    big = size * SUPERSAMPLE
    img = Image.new("RGBA", (big, big))
    draw = ImageDraw.Draw(img)
    scale = big / 24
    for shape in path_polygons(path):
        points = [(px * scale, py * scale) for px, py in shape]
        if filled:
            draw.polygon(points, fill=color)
        else:
            draw.line([*points, points[0], points[1]], fill=color, width=round(2 * scale), joint="curve")
    # The outline is centred on the edge, so shrink it inside the box first.
    if not filled:
        pad = round(1.2 * scale)
        img = ImageOps.pad(img.crop((0, 0, big, big)).resize((big - 2 * pad, big - 2 * pad), Image.LANCZOS),
                           (big, big), color=(0, 0, 0, 0))
    return img.resize((size, size), Image.LANCZOS)


# ---------- text ----------

@lru_cache(maxsize=64)
def _font(text_sample: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Roboto for Latin text; the bundled Noto face for any other script."""
    fallback = script_font(text_sample)
    file = fallback[1] if fallback else f"Roboto-{weight}.ttf"
    return ImageFont.truetype(str(FONTS_DIR / file), size)


def _text(text: str, weight: str, size: int, color: str) -> Image.Image:
    font = _font(text, weight, size)
    left, top, right, bottom = font.getbbox(text)
    img = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)))
    ImageDraw.Draw(img).text((-left, -top), text, font=font, fill=color)
    return img


def _fit_size(text: str, weight: str, size: int, max_width: float) -> int:
    while size > 24 and _font(text, weight, size).getlength(text) > max_width:
        size -= 4
    return size


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float, max_lines: int = 2) -> list[str]:
    """Greedy word wrap; text past ``max_lines`` is cut with an ellipsis."""
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(f"{lines[-1]} {word}") <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > max_lines:
        last = " ".join(lines[max_lines - 1:])
        while last and font.getlength(f"{last}…") > max_width:
            last = last[:-1].rstrip()
        lines = [*lines[:max_lines - 1], f"{last}…"]
    return lines


def _text_block(lines: list[str], weight: str, size: int, color: str, line_gap: int) -> Image.Image:
    rendered = [_text(line, weight, size, color) for line in lines]
    width = max(r.width for r in rendered)
    height = sum(r.height for r in rendered) + line_gap * (len(rendered) - 1)
    img, y = Image.new("RGBA", (width, height)), 0
    for r in rendered:
        img.alpha_composite(r, ((width - r.width) // 2, y))
        y += r.height + line_gap
    return img


# ---------- pieces ----------

def _pill(width: int, height: int, color: str) -> Image.Image:
    big = Image.new("RGBA", (width * SUPERSAMPLE, height * SUPERSAMPLE))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=big.height // 2, fill=color)
    return big.resize((width, height), Image.LANCZOS)


def _disc(size: int, color: str) -> Image.Image:
    big = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE))
    ImageDraw.Draw(big).ellipse((0, 0, big.width - 1, big.height - 1), fill=color)
    return big.resize((size, size), Image.LANCZOS)


def _avatar(spec: IntroSpec, size: int) -> Image.Image:
    """The creator's picture in a circle; their initial on the accent colour without one."""
    if spec.avatar and spec.avatar.exists():
        picture = ImageOps.fit(Image.open(spec.avatar).convert("RGBA"), (size, size), Image.LANCZOS)
    else:
        picture = _disc(size, spec.look.accent)
        letter = _text(spec.name.strip()[:1].upper() or "•", "Bold", size // 2, spec.look.accent_text)
        picture.alpha_composite(letter, ((size - letter.width) // 2, (size - letter.height) // 2))
    mask = _disc(size, "#FFFFFF").getchannel("A")
    out = Image.new("RGBA", (size, size))
    out.paste(picture, (0, 0), mask)
    return out


def _cursor(scale: float) -> Image.Image:
    points = [(0, 0), (0, 40), (10, 31), (17, 46), (24, 43), (17, 28), (30, 28)]
    k = scale * SUPERSAMPLE
    big = Image.new("RGBA", (round(34 * k), round(50 * k)))
    draw = ImageDraw.Draw(big)
    shape = [(2 * k + px * k, 2 * k + py * k) for px, py in points]
    draw.polygon(shape, fill="#FFFFFF")
    draw.line([*shape, shape[0], shape[1]], fill="#0F0F0F", width=round(2.5 * k), joint="curve")
    return big.resize((round(34 * scale), round(50 * scale)), Image.LANCZOS)


def _unit(width: int, height: int) -> float:
    """Pixels per design unit; portrait frames draw a little larger, as phones show them small."""
    return min(width, height) / 1080 * (1.15 if height > width else 1.0)


def _contrasting(look: Look, theme: Theme) -> tuple[str, str]:
    """The main button's colours, swapped for the theme's when they vanish into the page."""
    def luma(color: str) -> float:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b
    if abs(luma(look.accent) - luma(theme.background)) < 40:
        return theme.text, theme.background
    return look.accent, look.accent_text


@dataclass
class Layout:
    """Every piece of one rendition, pre-drawn, with where it sits."""

    size: tuple[int, int]
    theme: Theme
    avatar: Image.Image
    avatar_center: tuple[int, int]
    rows: list[tuple[Image.Image, int, tuple[float, float]]]  # piece, top, entrance
    like: dict[bool, Image.Image] | None
    like_icon: dict[bool, Image.Image] | None
    like_center: tuple[int, int]
    like_icon_x: int
    action: dict[bool, Image.Image]
    action_center: tuple[int, int]
    accent: str
    dot: Image.Image
    cursor: Image.Image

    @classmethod
    def build(cls, spec: IntroSpec, width: int, height: int) -> "Layout":
        theme = THEMES.get(spec.theme, THEMES["light"])
        u = _unit(width, height)
        max_text = width * 0.86
        accent, accent_text = _contrasting(spec.look, theme)

        avatar_size = round(300 * u)
        name_size = _fit_size(spec.name, "Bold", round(104 * u), max_text)
        name = _text(spec.name, "Bold", name_size, theme.text)
        pieces: list[tuple[Image.Image, int, tuple[float, float]]] = [(name, round(40 * u), NAME_IN)]
        if spec.handle:
            pieces.append((_text(spec.handle, "Medium", round(34 * u), theme.muted), round(22 * u), HANDLE_IN))
        if spec.tagline:
            size = round(38 * u)
            lines = wrap(spec.tagline, _font(spec.tagline, "Regular", size), max_text)
            gap = round(14 * u)
            pieces.append((_text_block(lines, "Regular", size, theme.muted, gap), round(36 * u), TAGLINE_IN))

        button_h = round(80 * u)
        label = round(32 * u)
        done_text = theme.text
        action_labels = {False: _text(spec.look.action, "Medium", label, accent_text),
                         True: _text(spec.look.done, "Medium", label, done_text)}
        action_w = max(i.width for i in action_labels.values()) + round(96 * u)
        action = {}
        for done, text in action_labels.items():
            pill = _pill(action_w, button_h, theme.chip if done else accent)
            pill.alpha_composite(text, ((action_w - text.width) // 2, (button_h - text.height) // 2))
            action[done] = pill

        like = like_icon = None
        icon_size = round(40 * u)
        like_w = 0
        if spec.look.like_icon:
            path = THUMB if spec.look.like_icon == "thumb" else HEART
            like_icon = {False: _icon(path, icon_size, theme.text, filled=False),
                         True: _icon(path, icon_size, spec.look.liked_color or theme.text, filled=True)}
            text = _text(spec.look.like_label, "Medium", label, theme.text)
            like_w = icon_size + round(14 * u) + text.width + round(72 * u)
            base = _pill(like_w, button_h, theme.chip)
            base.alpha_composite(text, (like_w - round(36 * u) - text.width, (button_h - text.height) // 2))
            like = {False: base, True: base}

        gap_buttons = round(30 * u)
        row_w = action_w + (like_w + gap_buttons if like else 0)
        content_h = avatar_size + sum(gap + piece.height for piece, gap, _ in pieces) + round(64 * u) + button_h
        top = (height - content_h) // 2
        avatar_center = (width // 2, top + avatar_size // 2)
        y = top + avatar_size
        rows = []
        for piece, gap, entrance in pieces:
            y += gap
            rows.append((piece, y, entrance))
            y += piece.height
        buttons_cy = y + round(64 * u) + button_h // 2
        left = (width - row_w) // 2
        like_center = (left + like_w // 2, buttons_cy)
        action_center = (left + (like_w + gap_buttons if like else 0) + action_w // 2, buttons_cy)
        return cls(
            size=(width, height), theme=theme, avatar=_avatar(spec, avatar_size), avatar_center=avatar_center,
            rows=rows, like=like, like_icon=like_icon, like_center=like_center,
            like_icon_x=round(36 * u) + icon_size // 2, action=action, action_center=action_center, accent=accent,
            dot=_disc(round(22 * u), accent), cursor=_cursor(1.4 * u),
        )


# ---------- frames ----------

def _with_alpha(img: Image.Image, alpha: float) -> Image.Image:
    if alpha >= 1:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: round(v * alpha)))
    return out


def _place(frame: Image.Image, piece: Image.Image, center: tuple[float, float], scale: float = 1.0,
           alpha: float = 1.0) -> None:
    """Composite ``piece`` centred at ``center``, clipped to the frame."""
    if alpha <= 0 or scale <= 0:
        return
    if scale != 1:
        piece = piece.resize((max(1, round(piece.width * scale)), max(1, round(piece.height * scale))), Image.LANCZOS)
    _paste(frame, _with_alpha(piece, alpha), round(center[0] - piece.width / 2), round(center[1] - piece.height / 2))


def _paste(frame: Image.Image, piece: Image.Image, x: int, y: int) -> None:
    left, top = max(0, x), max(0, y)
    right, bottom = min(frame.width, x + piece.width), min(frame.height, y + piece.height)
    if right > left and bottom > top:
        frame.alpha_composite(piece.crop((left - x, top - y, right - x, bottom - y)), (left, top))


def _cursor_at(t: float, layout: Layout) -> tuple[float, float] | None:
    w, h = layout.size
    lx, ly = layout.like_center
    ax, ay = layout.action_center
    u = _unit(w, h)
    off = (w * 0.78, h + 70 * u)
    stops = [(CURSOR_ENTERS, off)]
    if layout.like:
        stops += [(LIKE_CLICK - 0.05, (lx - 20 * u, ly + 10 * u)), (LIKE_CLICK + 0.25, (lx - 20 * u, ly + 10 * u))]
    stops += [(ACTION_CLICK - 0.05, (ax + 10 * u, ay + 10 * u)), (ACTION_CLICK + 0.4, (ax + 10 * u, ay + 10 * u)),
              (CURSOR_LEAVES, (w * 0.78, h + 120 * u))]
    if not stops[0][0] <= t <= stops[-1][0]:
        return None
    for (ta, a), (tb, b) in zip(stops, stops[1:]):
        if ta <= t <= tb:
            k = _ease_in_out(_progress(t, (ta, tb)))
            return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
    return None


def draw_frame(t: float, layout: Layout) -> Image.Image:
    w, h = layout.size
    u = _unit(w, h)
    frame = Image.new("RGBA", layout.size, layout.theme.background)

    k = _progress(t, AVATAR_IN)
    _place(frame, layout.avatar, layout.avatar_center, _ease_back(k), min(1.0, 2 * k))

    for piece, top, entrance in layout.rows:
        e = _ease_out(_progress(t, entrance))
        _place(frame, piece, (w / 2, top + piece.height / 2 + 24 * u * (1 - e)), alpha=e)

    e = _ease_out(_progress(t, BUTTONS_IN))
    rise = 30 * u * (1 - e)
    if layout.like:
        liked = t >= LIKE_CLICK
        button = layout.like[liked].copy()
        pop = 1 + 0.3 * math.sin(_progress(t, (LIKE_CLICK, LIKE_CLICK + 0.3)) * math.pi) if liked else 1
        _place(button, layout.like_icon[liked], (layout.like_icon_x, button.height / 2), pop)
        cx, cy = layout.like_center
        _place(frame, button, (cx, cy + rise), _press(t, LIKE_CLICK), e)

    m = _ease_in_out(_progress(t, (ACTION_CLICK, ACTION_CLICK + 0.2)))
    action = layout.action[False] if m <= 0 else layout.action[True] if m >= 1 else Image.blend(
        layout.action[False], layout.action[True], m)
    cx, cy = layout.action_center
    _place(frame, action, (cx, cy + rise), _press(t, ACTION_CLICK), e)

    ripple = _progress(t, (ACTION_CLICK, ACTION_CLICK + 0.6))
    if 0 < ripple < 1:
        overlay = Image.new("RGBA", layout.size)
        grow = ripple * 60 * u
        half_w, half_h = action.width / 2 + grow / 2, action.height / 2 + grow / 2
        r, g, b = (int(layout.accent[i:i + 2], 16) for i in (1, 3, 5))
        ImageDraw.Draw(overlay).rounded_rectangle(
            (cx - half_w, cy - half_h, cx + half_w, cy + half_h), radius=round(half_h),
            outline=(r, g, b, round(255 * (1 - ripple))), width=max(2, round(4 * u)))
        frame.alpha_composite(overlay)

    # The platform-coloured progress bar along the bottom edge.
    bar_h = max(4, round(10 * u))
    done = w * _progress(t, (0.0, FADE_OUT[0]))
    ImageDraw.Draw(frame).rectangle((0, h - bar_h, w, h), fill=layout.theme.track)
    if done > 0:
        ImageDraw.Draw(frame).rectangle((0, h - bar_h, done, h), fill=layout.accent)
        _place(frame, layout.dot, (done, h - bar_h / 2))

    at = _cursor_at(t, layout)
    if at:
        scale = min(_press(t, LIKE_CLICK) if layout.like else 1, _press(t, ACTION_CLICK))
        cursor = layout.cursor
        _place(frame, cursor, (at[0] + cursor.width * scale / 2, at[1] + cursor.height * scale / 2), scale)

    fade = _progress(t, FADE_OUT)
    if fade > 0:
        frame = Image.blend(frame, Image.new("RGBA", layout.size, "#000000"), fade)
    return frame


def frames(spec: IntroSpec, width: int, height: int) -> Iterator[bytes]:
    layout = Layout.build(spec, width, height)
    for i in range(round(DURATION_S * FPS)):
        yield draw_frame(i / FPS, layout).convert("RGB").tobytes()


# ---------- sound ----------

def write_sound(path: Path, has_like: bool, rate: int = 48000) -> None:
    """A soft pop as the avatar lands and a click on each button press."""
    out = np.zeros(round(DURATION_S * rate))
    rng = np.random.default_rng(7)

    def add(signal: np.ndarray, at: float, gain: float) -> None:
        start = round(at * rate)
        out[start:start + len(signal)] += signal[: len(out) - start] * gain

    t = np.arange(round(0.12 * rate)) / rate
    add(np.sin(2 * np.pi * (180 + 500 * np.exp(-t * 40)) * t) * np.minimum(t / 0.002, 1) * np.exp(-t / 0.04),
        AVATAR_IN[0] + 0.02, 0.5)
    c = np.arange(round(0.03 * rate)) / rate
    envelope = np.minimum(c / 0.0005, 1) * np.exp(-c / 0.005)
    click = rng.standard_normal(len(c)) * envelope * 0.5 + np.sin(2 * np.pi * 3000 * c) * envelope
    for at in ([LIKE_CLICK] if has_like else []) + [ACTION_CLICK]:
        add(click, at - 0.02, 0.8)
    pcm = (out / (np.abs(out).max() * 1.3) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(np.repeat(pcm, 2).tobytes())


# ---------- video ----------

def render(spec: IntroSpec, ratio: str, out: Path, work: Path) -> Path:
    """Render one rendition (``"9x16"``, ``"16x9"`` or ``"1x1"``) to ``out``. Blocking."""
    width, height = SIZES[ratio]
    sound = work / "intro.wav"
    if not sound.exists():
        write_sound(sound, spec.look.like_icon is not None)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(FPS), "-i", "pipe:0",
        "-i", str(sound),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames(spec, width, height):
            proc.stdin.write(frame)
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        proc.wait()
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"Intro render failed: {err[-500:]}")
    return out


def prepend_cmd(intro: str, video: Path, out: Path, media: MediaInfo) -> list[str]:
    """One FFmpeg run: the intro fitted to the clip's frame, then the clip."""
    w, h, fps = media.width, media.height, f"{media.fps:.6f}"
    fill = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    audio = "aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS"
    main_audio = (f"[1:a]{audio}[ma]" if media.has_audio
                  else f"anullsrc=r=48000:cl=stereo,atrim=duration={media.duration:.3f}[ma]")
    graph = [
        f"[0:v]{fill},fps={fps},format=yuv420p,setpts=PTS-STARTPTS[iv]",
        f"[0:a]{audio}[ia]",
        f"[1:v]setsar=1,fps={fps},format=yuv420p,setpts=PTS-STARTPTS[mv]",
        main_audio,
        "[iv][ia][mv][ma]concat=n=2:v=1:a=1[v][a]",
    ]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", intro, "-i", str(video),
        "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ]
