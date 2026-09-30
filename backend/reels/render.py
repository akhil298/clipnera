"""Scenes -> a finished 1080x1920 reel.

Each scene is encoded to the same format (H.264, 30 fps, no audio) so the
scenes join by stream copy; the voiceover is then laid under the joined
picture, captions are burned in one last pass, and branding (intro, watermark,
end card) is added on top.
"""

from __future__ import annotations

import asyncio
import subprocess
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from branding.service import apply_branding
from broll.renditions import run
from core.logging_config import get_logger
from subtitle_styling.ass_generator import FONTS_DIR, ass_filter, burn_filter_args, script_font
from transcription.language import script_of

log = get_logger(__name__)

WIDTH, HEIGHT, FPS = 1080, 1920, 30
KEN_BURNS_ZOOM = 0.08
# Every scene is tagged identically: parts that differ in pixel format, range
# or colour space make ffmpeg rebuild the filter graph mid-join, which dropped
# the watermark after the first scene.
ENCODE = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-an",
]


@dataclass(frozen=True)
class Style:
    background: str
    text: str
    accent: str
    font_file: str


STYLES: dict[str, Style] = {
    "clean": Style("#F5F5F2", "#111111", "#FF5A36", "Anton-Regular.ttf"),
    "bold": Style("#0B0B0B", "#FFD400", "#FFFFFF", "Anton-Regular.ttf"),
    "neon": Style("#0A0F2C", "#39F3FF", "#FF3CAC", "BebasNeue-Regular.ttf"),
    "warm": Style("#2B1B12", "#FFE9D2", "#FF9F43", "ArchivoBlack-Regular.ttf"),
}


def style_for(name: str) -> Style:
    return STYLES.get(name, STYLES["clean"])


def _font(text: str, style: Style, size: int) -> ImageFont.FreeTypeFont:
    fallback = script_font(text)
    return ImageFont.truetype(str(FONTS_DIR / (fallback[1] if fallback else style.font_file)), size)


def text_card(headline: str, style: Style, out: Path, size: tuple[int, int] = (WIDTH, HEIGHT)) -> Path:
    """A full-frame card: the headline centred and as large as fits, with an accent rule."""
    width, height = size
    image = Image.new("RGB", size, style.background)
    draw = ImageDraw.Draw(image)
    text = headline.upper() if script_of(headline) == "latin" else headline
    for font_size in range(round(190 * width / WIDTH), 30, -10):
        font = _font(text, style, font_size)
        lines = textwrap.wrap(text, width=max(4, int(width * 0.84 / (font_size * 0.52))))
        widths = [draw.textlength(line, font=font) for line in lines]
        if max(widths, default=0) <= width * 0.86 and len(lines) * font_size * 1.15 <= height * 0.5:
            break
    total = len(lines) * font_size * 1.15
    y = (height - total) / 2
    for line, line_width in zip(lines, widths):
        draw.text(((width - line_width) / 2, y), line, font=font, fill=style.text)
        y += font_size * 1.15
    rule = 160 * width / WIDTH
    draw.rectangle(((width - rule) / 2, y + 30, (width + rule) / 2, y + 44), fill=style.accent)
    image.save(out, "PNG")
    return out


def still_cmd(image: Path, seconds: float, out: Path, blur_fill: bool, size: tuple[int, int] = (WIDTH, HEIGHT)) -> list[str]:
    """A slow push-in on a still; photos that are not 9:16 sit on a blurred copy of themselves."""
    width, height = size
    frames = max(1, round(seconds * FPS))
    zoom = (
        f"zoompan=z='1+{KEN_BURNS_ZOOM}*on/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
        # JPEG stills decode full-range BT.601; convert to the shared tagging.
        f":d=1:s={width}x{height}:fps={FPS},setsar=1,scale=out_range=tv:out_color_matrix=bt709,format=yuv420p"
    )
    if blur_fill:
        graph = (
            f"[0]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"boxblur=30:2,eq=brightness=-0.12[bg];"
            f"[0]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{zoom}"
        )
    else:
        graph = f"[0]scale={width}:{height},{zoom}"
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(image),
        "-filter_complex", graph, "-frames:v", str(frames), *ENCODE, str(out),
    ]


def footage_cmd(video: Path, seconds: float, out: Path) -> list[str]:
    """A library shot trimmed (or looped, if short) to the scene's length."""
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-stream_loop", "-1", "-i", str(video),
        "-t", f"{seconds:.3f}", "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1,scale=out_range=tv:out_color_matrix=bt709,format=yuv420p",
        *ENCODE, str(out),
    ]


async def join(parts: list[Path], audio: Path | None, out: Path) -> None:
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        # A silent track keeps every player and social upload happy.
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest"]
    await run(cmd + ["-movflags", "+faststart", str(out)])


@lru_cache(maxsize=1)
def has_libass() -> bool:
    listing = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return any(line.split()[1:2] == ["ass"] for line in listing.splitlines() if len(line.split()) > 1)


async def finish(video: Path, ass_file: Path | None, watermark: bool, out: Path, preset: str = "medium") -> Path:
    """Burn captions, then add Clipnera branding; returns ``video`` itself when there is nothing to do."""
    filters: list[str] = []
    if ass_file and has_libass():
        filters.append(ass_filter(str(ass_file)))
    elif ass_file:
        log.warning("This ffmpeg has no libass; the reel renders without burned captions")
    if not filters:
        return await apply_branding(video, out) if watermark else video
    captioned = out.with_name(f"captioned_{out.name}") if watermark else out
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(video), *burn_filter_args(filters),
        "-c:v", "libx264", "-preset", preset, "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart", str(captioned), cwd=str(ass_file.parent), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Final burn failed: {stderr.decode('utf-8', 'ignore')[-300:]}")
    return await apply_branding(captioned, out) if watermark else captioned
