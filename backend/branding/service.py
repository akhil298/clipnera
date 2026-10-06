"""The branding pass every branded export goes through, whatever rendered it.

The finished video becomes ``[clip + Listening Spark][end card]``: after the
opening headline the watermark rolls into the clip's top-left corner and follows
its voice, and the end card blurs the clip's last frame behind it.
The files are rendered by ``branding/motion/source/render.mjs``;
``static/motion/branding/manifest.json`` lists them.
"""

from __future__ import annotations

import asyncio
import json
import math
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from broll.renditions import run
from branding.watermark import SparkOverlay, loudness
from core.logging_config import get_logger
from hook_transitions.graph import MediaInfo
from video_processor.ffmpeg_service import FFmpegService

log = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "branding"
# The end card's blur is about this share of the frame's short side.
BLUR_RATIO = 1 / 40


@dataclass(frozen=True)
class Assets:
    outro: dict[str, str]
    outro_s: float
    blur_in_s: float
    layout: Path
    # The card's own fade-in over the clip, applied here since the files are opaque.
    fade_in_s: float = 0.0

    @classmethod
    def load(cls, root: Path = STATIC_DIR) -> "Assets | None":
        path = root / "manifest.json"
        if not path.exists():
            return None
        spec = json.loads(path.read_text())
        return cls(
            outro={k: str(root / v) for k, v in spec["outro"]["files"].items()}, outro_s=spec["outro"]["duration"],
            blur_in_s=spec["outro"]["blur_in_s"], layout=root / spec["watermark"]["layout"],
            fade_in_s=spec["outro"].get("fade_in_s", 0.0),
        )


@lru_cache(maxsize=1)
def assets() -> Assets | None:
    found = Assets.load()
    if found is None:
        log.warning("Branding assets missing at %s; exports render unbranded", STATIC_DIR)
    return found


def added_seconds() -> float:
    """How much longer a branded export runs than its clip."""
    found = assets()
    return found.outro_s if found else 0.0


def nearest(files: dict[str, str], width: int, height: int) -> str:
    """The rendition ("9x16", "16x9", "1x1") closest in shape to the frame."""
    def shape(name: str) -> float:
        w, h = name.split("x")
        return int(w) / int(h)
    return files[min(files, key=lambda name: abs(math.log(shape(name) * height / width)))]


def branding_cmd(video: Path, out: Path, media: MediaInfo, found: Assets, overlay: Path,
                 overlay_xy: tuple[int, int], last_frame: Path) -> list[str]:
    """One FFmpeg run: the clip under the watermark, then the end card."""
    w, h, fps = media.width, media.height, f"{media.fps:.6f}"
    fill = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    blur = max(2, round(min(w, h) * BLUR_RATIO))
    fade = f",format=yuva420p,fade=t=in:st=0:d={found.fade_in_s:.3f}:alpha=1" if found.fade_in_s > 0 else ""
    silence = "anullsrc=r=48000:cl=stereo,atrim=duration={:.3f}"
    main_audio = "[0:a]asetpts=PTS-STARTPTS[ma]" if media.has_audio else f"{silence.format(media.duration)}[ma]"
    graph = [
        f"[0:v][1:v]overlay=x={overlay_xy[0]}:y={overlay_xy[1]}:eof_action=pass,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[main]",
        main_audio,
        # The end card sits over the clip's last frame, which blurs in behind it.
        f"[3:v]scale={w}:{h},setsar=1,format=yuv420p,split[sharp][soft]",
        f"[soft]boxblur=luma_radius={blur}:luma_power=2[blurred]",
        f"[sharp][blurred]blend=all_expr='A+(B-A)*min(T/{found.blur_in_s},1)'[still]",
        f"[2:v]{fill}{fade}[card]",
        # The looped still never ends on its own inside concat, so cut it to length.
        f"[still][card]overlay=0:0,fps={fps},format=yuv420p,trim=duration={found.outro_s:.3f},setpts=PTS-STARTPTS[outro]",
        f"{silence.format(found.outro_s)}[oa]",
        # concat expects every piece to start at zero, hence the setpts above.
        "[main][ma][outro][oa]concat=n=2:v=1:a=1[v][a]",
    ]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(video),
        "-i", str(overlay),
        "-i", nearest(found.outro, w, h),
        "-loop", "1", "-framerate", fps, "-t", f"{found.outro_s:.3f}", "-i", str(last_frame),
        "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ]


async def apply_branding(video: Path, out: Path) -> Path:
    """``video`` with the watermark and end card, written to ``out``.

    Without rendered assets the video comes back unbranded instead of failing
    the export, as a missing watermark image did before.
    """
    found = assets()
    if found is None:
        return video
    media = MediaInfo.from_probe(await FFmpegService().get_video_info(str(video)))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        last_frame, overlay_file = work / "last.png", work / "watermark.mov"
        # Every decoded frame overwrites the image, so the clip's final frame remains.
        await run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-sseof", "-0.5", "-i", str(video), "-update", "1", str(last_frame)])
        overlay = SparkOverlay(found.layout, min(media.width, media.height))
        frames = max(1, math.floor(media.duration * media.fps))
        levels = await asyncio.to_thread(loudness, video, media.fps, frames, media.has_audio)
        await asyncio.to_thread(overlay.write, levels, media.fps, overlay_file)
        await run(branding_cmd(video, out, media, found, overlay_file, overlay.position(media.width), last_frame))
    return out
