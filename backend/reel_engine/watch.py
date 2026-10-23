"""Watch: every second of the picture, as shots, faces, sharpness and light, plus contact sheets for the director.

Frames come one a second from each video (keyframe decode, 256 px). Shots are cut on colour changes;
faces are found on several frames of every shot and kept as a per-second track, which the camera uses
to frame 9:16 on the person. The director sees the same frames, stamped with source and time, packed
into sheets that fit one vision request.
"""

from __future__ import annotations

import asyncio

import numpy as np

from core.logging_config import get_logger
from edit_engine.perception import BLUR_THRESHOLD, DARK_THRESHOLD, MediaInfo, detect_shots, sample_frames
from reel_engine.media import MAX_IMAGES, sheets
from reel_engine.plan import Box, Shot, Source

log = get_logger(__name__)

FACE_SAMPLES_PER_SHOT = 4
SHAKY_MOTION = 25.0
# Mean pixel change (0-255) under which a face has not moved at all between samples a second apart.
STILL_FACE_CHANGE = 1.5


def _faces(detector, frame: np.ndarray) -> list[Box]:
    return [Box(x=round(f.box.x, 4), y=round(f.box.y, 4), w=round(f.box.width, 4), h=round(f.box.height, 4))
            for f in detector.detect(frame)]


def _still(box: Box, image: np.ndarray, before: np.ndarray | None) -> bool:
    """A face whose pixels did not change since the last sample: a photo on a slide or a poster, not a person."""
    if before is None or before.shape != image.shape:
        return False
    h, w = image.shape[:2]
    x0, y0 = max(0, int(box.x * w)), max(0, int(box.y * h))
    x1, y1 = min(w, int((box.x + box.w) * w) + 1), min(h, int((box.y + box.h) * h) + 1)
    if x1 <= x0 or y1 <= y0:
        return False
    change = np.abs(image[y0:y1, x0:x1].astype(np.int16) - before[y0:y1, x0:x1].astype(np.int16)).mean()
    return float(change) < STILL_FACE_CHANGE


def _track(detector, frames: list[tuple[float, np.ndarray]]) -> list[list[float]]:
    """Per sampled second: [t, centre x, centre y, width] of the largest living face, or nothing when there is none."""
    track = []
    before = None
    for t, image in frames:
        faces = [f for f in _faces(detector, image) if not _still(f, image, before)]
        before = image
        if faces:
            big = max(faces, key=lambda b: b.w * b.h)
            track.append([round(t, 2), round(big.x + big.w / 2, 4), round(big.y + big.h / 2, 4), round(big.w, 4)])
    return track


async def watch_source(source: Source) -> tuple[list[Shot], list[list[float]], list[tuple[float, np.ndarray]]]:
    from video_processor.face_detection import FaceDetector

    if source.kind == "image":
        from reel_engine.media import frame

        image = frame(source.path, 0.0, 256)
        frames = [(0.0, image)] if image is not None else []
        detector = FaceDetector()
        faces = _faces(detector, image) if image is not None else []
        return [Shot(id=f"s{source.index}.0", src=source.index, t0=0.0, t1=source.duration, faces=faces)], _track(detector, frames), frames
    info = MediaInfo(duration=source.duration, width=source.width, height=source.height, has_audio=source.has_audio, has_video=True)
    frames = await sample_frames(source.path, info)
    found = await asyncio.to_thread(detect_shots, frames, source.duration)
    detector = FaceDetector()
    track = await asyncio.to_thread(_track, detector, frames)
    shots = []
    for n, shot in enumerate(found):
        inside = [f for f in frames if shot.start <= f[0] < shot.end] or frames[:1]
        picks = inside[:: max(1, len(inside) // FACE_SAMPLES_PER_SHOT)][:FACE_SAMPLES_PER_SHOT]
        faces = max((_faces(detector, image) for _, image in picks), key=len, default=[])
        shots.append(Shot(id=f"s{source.index}.{n}", src=source.index, t0=round(shot.start, 2), t1=round(shot.end, 2), faces=faces,
                          motion=round(shot.motion, 1), sharp=shot.blur >= BLUR_THRESHOLD, dark=shot.brightness < DARK_THRESHOLD))
    return shots, track, frames


def director_sheets(frames: dict[int, list[tuple[float, np.ndarray]]]) -> tuple[list[bytes], str]:
    """Frames from every source, stamped 'source:seconds', packed to fit one request; and how to read them."""
    items = [(f"{src}:{t:.0f}", image) for src, found in sorted(frames.items()) for t, image in found]
    if not items:
        return [], "no frames"
    per = 4 if len(items) <= MAX_IMAGES * 4 else 9
    keep = MAX_IMAGES * per
    if len(items) > keep:
        step = len(items) / keep
        items = [items[int(k * step)] for k in range(keep)]
    columns = 2 if per == 4 else 3
    return sheets(items, columns, columns, 320 if per == 4 else 240), \
        f"{len(items)} frames packed {columns}x{columns} per sheet, read left-right then top-bottom; each is stamped source:second"


async def watch(sources: list[Source]) -> tuple[list[Shot], dict[str, list[list[float]]], list[bytes], str]:
    visual = [s for s in sources if s.kind in ("video", "image")]
    results = await asyncio.gather(*(watch_source(s) for s in visual))
    shots: list[Shot] = []
    tracks: dict[str, list[list[float]]] = {}
    frames: dict[int, list[tuple[float, np.ndarray]]] = {}
    for source, (found, track, sampled) in zip(visual, results):
        shots += found
        tracks[str(source.index)] = track
        frames[source.index] = sampled
    jpegs, how = await asyncio.to_thread(director_sheets, frames)
    log.info("Watch: %d shots across %d sources, %d sheets", len(shots), len(visual), len(jpegs))
    return shots, tracks, jpegs, how


def shaky(shot: Shot) -> bool:
    return shot.motion >= SHAKY_MOTION and not shot.faces
