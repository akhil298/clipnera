"""Timeline v1 → the reel renderer's compiled timeline (edit_engine.render), the inverse of editor.reel_adapter.

Used for the verify render (360p, Phase 12) and for "Render on server" (Phase 17). What the
reel renderer draws, in the Timeline's own shape: the main video track's clips back to back at
their speed (zoom = scale, crop centre = x, both moving through their keyframes), their speech,
one music track ducked under it (looping to the end), every library sound effect, the overlay tracks' footage and
images (filling the frame, or picture-in-picture under scale 1; their opacity held at its middle),
the graphic tracks' flashes and shelf graphics (tracks later in the list draw on top), titles and
burned captions. What it doesn't (the verifier checks on the Timeline instead): rotation, and the
main track's fades and slides.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from brain import library
from clients.services.s3 import S3
from core.config import get_settings
from editor.timeline import ClipItem, GraphicItem, Keyframe, SfxItem, TextItem, Timeline
from understanding.mud import MUD

# The verify render's long side; the short side follows the Timeline's shape.
PREVIEW_LONG_SIDE = 640
# A library sound whose name holds the word plays as this renderer sound (edit_engine.render.SFX).
RENDER_SOUNDS = (
    ("whoosh", "whoosh"), ("swoosh", "whoosh"), ("slide", "whoosh"), ("pop", "pop"), ("click", "pop"),
    ("ding", "ding"), ("chime", "ding"), ("success", "ding"), ("boom", "hit"), ("punch", "hit"), ("thud", "hit"),
)


def main_track(timeline: Timeline):
    track = next((t for t in timeline.tracks if t.kind == "video" and t.extra.get("role") == "main"), None)
    return track or next((t for t in timeline.tracks if t.kind == "video"), None)


def main_clips(timeline: Timeline) -> list[ClipItem]:
    track = main_track(timeline)
    return sorted((i for i in (track.items if track else []) if isinstance(i, ClipItem)), key=lambda c: c.at)


def preview_size(timeline: Timeline) -> tuple[int, int]:
    """The verify render's size: the Timeline's shape, its long side PREVIEW_LONG_SIDE."""
    k = PREVIEW_LONG_SIDE / max(timeline.width, timeline.height)
    return round(timeline.width * k / 2) * 2, round(timeline.height * k / 2) * 2


def _points(keys: list[Keyframe] | None, fps: int) -> list[tuple[float, float, str]] | None:
    return [(k.f / fps, k.v, k.ease) for k in keys] if keys else None


def _mean(keys: list[Keyframe] | None, held: float) -> float:
    return sum(k.v for k in keys) / len(keys) if keys else held


def _framing(clip: ClipItem, fps: int) -> dict[str, Any]:
    """A clip's speed and framing as the renderer takes them: held values, and the keyframes they move through."""
    framing = {"speed": clip.speed, "zoom": max(1.0, _mean(clip.keyframes.get("scale"), clip.transform.scale)),
               "crop_x": _mean(clip.keyframes.get("x"), clip.transform.x)}
    motion = {name: points for name, prop in (("zoom", "scale"), ("x", "x"))
              if (points := _points(clip.keyframes.get(prop), fps))}
    return {**framing, "motion": motion} if motion else framing


def music_clip(timeline: Timeline, muds: Mapping[str, MUD]) -> ClipItem | None:
    for track in timeline.tracks:
        if track.kind != "audio" or track.muted:
            continue
        for item in sorted(track.items, key=lambda i: i.at):
            if isinstance(item, ClipItem) and (timeline.assets[item.asset].kind == "audio"
                                               or (muds.get(item.asset) and muds[item.asset].music)):
                return item
    return None


def to_reel(timeline: Timeline, muds: Mapping[str, MUD], *, size: tuple[int, int] | None = None) -> tuple[dict[str, Any], list[str]]:
    """The compiled timeline, and the asset ids its ``src`` indices refer to (in order)."""
    fps = timeline.fps
    order: list[str] = []

    def src(asset: str) -> int:
        if asset not in order:
            order.append(asset)
        return order.index(asset)

    picture, voice, words = [], [], []
    cursor = 0.0
    for clip in main_clips(timeline):
        at = clip.at / fps
        if at - cursor > 0.04:
            # A gap on the main track renders as a blank card, as the studio shows it.
            picture.append({"kind": "card", "text": " ", "at": round(cursor, 3), "dur": round(at - cursor, 3)})
        asset = timeline.assets[clip.asset]
        start, end = clip.src_in / fps, clip.src_out / fps
        if asset.kind == "image":
            picture.append({"kind": "image", "src": src(clip.asset), "at": round(at, 3), "dur": round(clip.frames / fps, 3)})
        else:
            picture.append({"kind": "video", "src": src(clip.asset), "in": round(start, 3), "out": round(end, 3),
                            "at": round(at, 3), **_framing(clip, fps)})
            if asset.has_audio and clip.volume > 0:
                voice.append({"src": src(clip.asset), "in": round(start, 3), "out": round(end, 3), "at": round(at, 3),
                              "speed": clip.speed})
            if timeline.captions and timeline.captions.enabled and (mud := muds.get(clip.asset)):
                words += [{"word": w.text, "start": round(at + (w.t0 - start) / clip.speed, 3),
                           "end": round(at + (w.t1 - start) / clip.speed, 3)}
                          for w in mud.words if w.t0 >= start - 0.01 and w.t1 <= end + 0.01]
        cursor = at + clip.frames / fps

    texts = []
    for track in timeline.tracks:
        for item in track.items:
            if isinstance(item, TextItem) and not track.hidden:
                kind = "hook" if item.at == 0 and item.transform.y < 0.45 else "line" if item.transform.y > 0.6 else "pop"
                texts.append({"kind": kind, "text": item.text, "at": round(item.at / fps, 3), "dur": round(item.dur / fps, 3)})

    music = music_clip(timeline, muds)
    width, height = size or (timeline.width, timeline.height)
    compiled = {
        "duration": round(cursor, 3), "width": width, "height": height, "look": timeline.look,
        "picture": picture, "voice": voice, "texts": sorted(texts, key=lambda t: t["at"]), "sfx": _sfx(timeline),
        "layers": _layers(timeline, src),
        "words": sorted(words, key=lambda w: w["start"]),
        "caption_style": timeline.captions.style if timeline.captions else None,
        "music": None if music is None else {
            "offset": round(music.src_in / fps, 3), "gain_db": round(20 * math.log10(max(music.volume, 1e-3)), 2),
            "duck": True, "asset": music.asset, "loop": True,
        },
    }
    if music is not None:
        src(music.asset)
    return compiled, order


def _layers(timeline: Timeline, src) -> list[dict[str, Any]]:
    """The overlay tracks' clips and the graphic tracks' graphics, bottom track first."""
    fps, main, layers = timeline.fps, main_track(timeline), []
    shelf = library.graphics()
    for track in timeline.tracks:
        if track.hidden or track is main or track.kind not in ("video", "overlay", "graphic"):
            continue
        for item in sorted(track.items, key=lambda i: i.at):
            timing = {"at": round(item.at / fps, 3), "dur": round(item.frames / fps, 3)}
            if isinstance(item, ClipItem):
                kind = timeline.assets[item.asset].kind
                if kind == "audio":
                    continue
                fade = item.transition_in.frames / fps if item.transition_in and item.transition_in.type == "fade" else 0.0
                layers.append({"kind": kind, "src": src(item.asset), "in": round(item.src_in / fps, 3), **timing,
                               **_framing(item, fps), "scale": _mean(item.keyframes.get("scale"), item.transform.scale),
                               "x": item.transform.x, "y": item.transform.y,
                               "opacity": max(0.0, min(1.0, _mean(item.keyframes.get("opacity"), 1.0))), "fade_in": fade})
            elif isinstance(item, GraphicItem) and isinstance(item.extra.get("solid"), str):
                layers.append({"kind": "solid", "colour": item.extra["solid"], **timing})
            elif isinstance(item, GraphicItem) and (graphic := shelf.get(str(item.extra.get("graphic")))):
                layers.append({"kind": "graphic", "path": str(graphic.video), **timing})
    return layers


def _sfx(timeline: Timeline) -> list[dict[str, Any]]:
    """The Timeline's sound effects: library sounds as their files, anything else as the nearest built-in sound."""
    cues = []
    for track in timeline.tracks:
        if track.kind != "audio" or track.muted:
            continue
        for item in track.items:
            if not isinstance(item, SfxItem):
                continue
            if known := library.sounds().get(item.name):
                cues.append({"name": item.name, "path": str(library.SFX_DIR / known.file),
                             "at": round(item.at / timeline.fps, 3), "gain_db": item.gain_db})
                continue
            sound = next((name for word, name in RENDER_SOUNDS if word in item.name), None)
            if sound:
                cues.append({"name": item.name, "sound": sound, "at": round(item.at / timeline.fps, 3), "gain_db": item.gain_db})
    return sorted(cues, key=lambda cue: cue["at"])


async def download(timeline: Timeline, asset_ids: list[str], work: Path, s3: S3 | None = None) -> dict[str, Path]:
    """Local copies of the assets, by id."""
    s3 = s3 or S3()
    bucket = get_settings().S3_BUCKET_NAME

    async def fetch(asset_id: str) -> tuple[str, Path]:
        asset = timeline.assets[asset_id]
        local = work / f"{asset_id}{Path(asset.key).suffix}"
        if not local.exists():
            await asyncio.to_thread(s3.download_file, bucket, asset.proxy or asset.key, str(local))
        return asset_id, local

    return dict(await asyncio.gather(*(fetch(a) for a in asset_ids)))


async def render_timeline(timeline: Timeline, muds: Mapping[str, MUD], work: Path, *, preview: bool,
                          paths: dict[str, Path] | None = None) -> Path:
    """Render the Timeline to ``work/reel.mp4`` (360p for a verify pass)."""
    from edit_engine.render import render  # Heavy imports (FFmpeg helpers, caption styles) only when rendering.

    compiled, order = to_reel(timeline, muds, size=preview_size(timeline) if preview else None)
    local = paths or await download(timeline, order, work)
    sources = {index: local[asset_id] for index, asset_id in enumerate(order)}
    music_path = local[compiled["music"]["asset"]] if compiled["music"] else None
    return await render(compiled, sources, music_path, watermark=False, work=work)
