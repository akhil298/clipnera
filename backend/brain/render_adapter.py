"""Timeline v1 → the reel renderer's compiled timeline (edit_engine.render), the inverse of editor.reel_adapter.

Used for the verify render (360p, Phase 12) and for "Render on server" (Phase 17). What the
reel renderer draws: the main video track's clips back to back (zoom = scale, crop centre =
x), their speech, one music track ducked under it, titles and burned captions. What it
doesn't (and the verifier checks on the Timeline instead): overlay tracks, flash solids,
speed changes, graphics; and it always crops to 9:16.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from clients.services.s3 import S3
from core.config import get_settings
from editor.timeline import ClipItem, TextItem, Timeline
from understanding.mud import MUD

PREVIEW_SIZE = (360, 640)


def main_clips(timeline: Timeline) -> list[ClipItem]:
    track = next((t for t in timeline.tracks if t.kind == "video" and t.extra.get("role") == "main"), None)
    track = track or next((t for t in timeline.tracks if t.kind == "video"), None)
    return sorted((i for i in (track.items if track else []) if isinstance(i, ClipItem)), key=lambda c: c.at)


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
        x = clip.keyframes.get("x")
        crop_x = sum(k.v for k in x) / len(x) if x else clip.transform.x
        if asset.kind == "image":
            picture.append({"kind": "image", "src": src(clip.asset), "at": round(at, 3), "dur": round(clip.frames / fps, 3)})
        else:
            picture.append({"kind": "video", "src": src(clip.asset), "in": round(start, 3), "out": round(end, 3),
                            "at": round(at, 3), "zoom": max(1.0, clip.transform.scale), "crop_x": crop_x})
            if asset.has_audio and clip.volume > 0:
                voice.append({"src": src(clip.asset), "in": round(start, 3), "out": round(end, 3), "at": round(at, 3)})
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
        "picture": picture, "voice": voice, "texts": sorted(texts, key=lambda t: t["at"]), "sfx": [],
        "words": sorted(words, key=lambda w: w["start"]),
        "caption_style": timeline.captions.style if timeline.captions else None,
        "music": None if music is None else {
            "offset": round(music.src_in / fps, 3), "gain_db": round(20 * math.log10(max(music.volume, 1e-3)), 2),
            "duck": True, "asset": music.asset,
        },
    }
    if music is not None:
        src(music.asset)
    return compiled, order


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

    compiled, order = to_reel(timeline, muds, size=PREVIEW_SIZE if preview else None)
    local = paths or await download(timeline, order, work)
    sources = {index: local[asset_id] for index, asset_id in enumerate(order)}
    music_path = local[compiled["music"]["asset"]] if compiled["music"] else None
    return await render(compiled, sources, music_path, watermark=False, work=work)
