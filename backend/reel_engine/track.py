"""Tracking for framing: every face (and whether it is talking) and, where nobody is on screen, what matters.

Frames are decoded four times a second at 640 px (every frame, not only keyframes: keyframes are seconds apart in
web video, so a keyframe track lagged and repeated itself). For each frame:

- faces: every face found, as a row [t, centre x, centre y, width, height, mouth motion]. Mouth motion is how much
  the lower part of that face changed since the last frame (the same face, matched by position): a talking face
  moves there, a listening one does not. It is what lets the camera follow the speaker in a two-person shot.
- focus: twice a second, the centre of the 9:16 window holding the most detail and movement (edges plus change),
  so a shot with nobody in it is framed on the hands, the food or the screen instead of blindly on the middle.
"""

from __future__ import annotations

import asyncio

import numpy as np

from core.logging_config import get_logger
from reel_engine.plan import Source

log = get_logger(__name__)

TRACK_FPS = 4
TRACK_WIDTH = 640
FOCUS_EVERY = 2          # frames between focus samples (twice a second at 4 fps)
FOCUS_WIDTH = 160
MATCH_DISTANCE = 0.12    # how far (share of the frame) a face may move between frames and stay the same face


def _patch(grey: np.ndarray, box: tuple[float, float, float, float], low: float, high: float) -> np.ndarray | None:
    """The face's band from ``low`` to ``high`` (shares of the box height from its centre), small and grey."""
    import cv2

    h, w = grey.shape
    cx, cy, bw, bh = box
    x0, x1 = int((cx - bw * 0.3) * w), int((cx + bw * 0.3) * w)
    y0, y1 = int((cy + bh * low) * h), int((cy + bh * high) * h)
    if x1 - x0 < 4 or y1 - y0 < 3 or x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    return cv2.resize(grey[y0:y1, x0:x1], (24, 12), interpolation=cv2.INTER_AREA).astype(np.float32)


def _mouth(grey: np.ndarray, box: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray] | None:
    """The mouth band and the eyes band: talking moves the first; moving the head moves both."""
    mouth, eyes = _patch(grey, box, 0.05, 0.45), _patch(grey, box, -0.35, -0.05)
    return (mouth, eyes) if mouth is not None and eyes is not None else None


def _focus(small: np.ndarray, before: np.ndarray | None, aspect: float) -> float:
    """Centre (share of the width) of the 9:16 window with the most edges and movement."""
    import cv2

    edges = np.hypot(cv2.Sobel(small, cv2.CV_32F, 1, 0), cv2.Sobel(small, cv2.CV_32F, 0, 1))
    energy = edges / (edges.mean() + 1e-3)
    if before is not None:
        change = np.abs(small - before)
        energy += 2.0 * change / (change.mean() + 1e-3)
    columns = energy.sum(axis=0)
    width = small.shape[1]
    window = max(1, min(width, int(round(width * (9 / 16) / aspect))))
    if window >= width:
        return 0.5
    sums = np.convolve(columns, np.ones(window), mode="valid")
    best = int(np.argmax(sums))
    return (best + window / 2) / width


async def track(source: Source) -> tuple[list[list[float]], list[list[float]]]:
    """(face rows, focus rows [t, centre x]) for a video source; ([], []) when it cannot be read."""
    import cv2

    from video_processor.face_detection import FaceDetector

    if source.kind != "video" or not source.width:
        return [], []
    width = TRACK_WIDTH if source.width >= source.height else int(TRACK_WIDTH * source.width / source.height) // 2 * 2
    height = int(round(width * source.height / source.width / 2) * 2)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", source.path,
        "-vf", f"fps={TRACK_FPS},scale={width}:{height}", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    detector = FaceDetector()
    aspect = source.width / source.height
    size = width * height * 3
    faces: list[list[float]] = []
    focus: list[list[float]] = []
    previous: list[tuple[tuple[float, float, float, float], tuple[np.ndarray, np.ndarray] | None]] = []
    before_small = None
    n = 0
    while True:
        try:
            raw = await proc.stdout.readexactly(size)
        except asyncio.IncompleteReadError:
            break
        t = round(n / TRACK_FPS, 3)
        image = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        found = await asyncio.to_thread(detector.detect, image)
        current = []
        for face in found:
            b = face.box
            box = (b.x + b.width / 2, b.y + b.height / 2, b.width, b.height)
            mouth = _mouth(grey, box)
            match = min(previous, key=lambda p: abs(p[0][0] - box[0]) + abs(p[0][1] - box[1]), default=None)
            motion = 0.0
            if match and mouth is not None and match[1] is not None and abs(match[0][0] - box[0]) + abs(match[0][1] - box[1]) < MATCH_DISTANCE:
                # Mouth change beyond what the head's own movement explains (the eyes band moves with the head).
                lips = float(np.abs(mouth[0] - match[1][0]).mean() / 255)
                head = float(np.abs(mouth[1] - match[1][1]).mean() / 255)
                motion = max(0.0, lips - 0.8 * head)
            faces.append([t, round(box[0], 4), round(box[1], 4), round(box[2], 4), round(box[3], 4), round(motion, 4)])
            current.append((box, mouth))
        previous = current
        if n % FOCUS_EVERY == 0:
            small = cv2.resize(grey, (FOCUS_WIDTH, max(1, int(FOCUS_WIDTH * height / width))), interpolation=cv2.INTER_AREA).astype(np.float32)
            focus.append([t, round(_focus(small, before_small, aspect), 4)])
            before_small = small
        n += 1
    await proc.wait()
    log.info("Track: src%d %d frames, %d face sightings, %d focus points", source.index, n, len(faces), len(focus))
    return faces, focus
