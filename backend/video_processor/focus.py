"""Where to look when there is no face to frame, measured from sampled frames.

A talking head is framed on the speaker's face. Some formats have nobody to
follow: a screen share is read where its pixels change (typing, the cursor, a
scroll, a new slide), and voice-over footage is watched where it stands out
(spectral-residual saliency) and where it moves. A green screen needs the
actual colour of the screen, since studio greens range from lime to teal and a
fixed key colour leaves a fringe on half of them.

Everything here works on the cutter's downscaled samples and returns
normalised boxes or colours; :mod:`video_processor.editing` decides what to do
with them and :mod:`video_processor.clip_cutter` smooths them into a camera path.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterable

import cv2
import numpy as np

from video_processor.geometry import Box

# Frames are compared at this width: enough to see a typed character move,
# small enough that a clip's worth of samples costs milliseconds.
ACTIVITY_WIDTH = 320
# A pixel has changed when its grey level moves this much; compression noise
# on a still screen stays well below it.
ACTIVITY_LEVEL = 18
# Fewer changed pixels than this share of the frame is noise (a blinking caret
# alone still counts: it is around 0.05% at this width, so the floor is lower).
ACTIVITY_MIN_SHARE = 0.0003
# The changed area is the central span of the changed pixels, so one stray
# change across the screen does not stretch it to the whole frame.
ACTIVITY_PERCENTILES = (2.0, 98.0)
# A face moves constantly; it is masked this much wider than its box so its
# hair and shoulders are not read as screen activity.
FACE_MASK_GROWTH = 1.6
# Saliency is computed on a copy this wide, the size the spectral-residual
# method is designed for.
SALIENCY_WIDTH = 128
# Motion counts for this share of the combined map, saliency for the rest.
MOTION_WEIGHT = 0.5
# Pixels above mean + this many standard deviations of the combined map are the
# salient region.
SALIENT_SIGMA = 1.5
SALIENT_PERCENTILES = (10.0, 90.0)
# Studio green in OpenCV's HSV (hue 0-180): hues, and the saturation and value a
# lit screen keeps.
GREEN_HUE = (35, 90)
GREEN_MIN_SATURATION = 80
GREEN_MIN_VALUE = 50
# A frame is a green screen sample when this share of it is green.
GREEN_MIN_SHARE = 0.1
# Every Nth sample is enough to read a colour that does not change.
GREEN_SAMPLE_EVERY = 6

FocusSamples = list[tuple[float, Box | None]]


def _same_shot(cuts: list[float], earlier: float, later: float) -> bool:
    return bisect_right(cuts, earlier) == bisect_right(cuts, later)


def _grey(frame: np.ndarray, width: int) -> np.ndarray:
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height = max(2, round(grey.shape[0] * width / max(1, grey.shape[1])))
    return cv2.resize(grey, (width, height), interpolation=cv2.INTER_AREA)


def _spread(xs: np.ndarray, ys: np.ndarray, width: int, height: int, percentiles: tuple[float, float]) -> Box:
    """Normalised box over the central ``percentiles`` of the points ``xs``, ``ys``."""
    left, right = np.percentile(xs, percentiles)
    top, bottom = np.percentile(ys, percentiles)
    return Box(
        float(left) / width, float(top) / height,
        max(1.0, float(right - left) + 1) / width, max(1.0, float(bottom - top) + 1) / height,
    )


def activity_boxes(
    frames: Iterable[tuple[float, np.ndarray]],
    cuts: list[float],
    masks_at: Callable[[float], list[Box]] = lambda _t: [],
) -> FocusSamples:
    """Per sample, the box around what changed since the previous sample.

    None where nothing changed, at the first sample of each shot (a camera cut
    changes everything, which says nothing about where to look), and for a
    corrupt frame. ``masks_at(t)`` gives regions to ignore at ``t``: the
    presenter's webcam is always moving and is never the part being explained.
    """
    samples: FocusSamples = []
    previous: tuple[float, np.ndarray] | None = None
    for timestamp, frame in frames:
        if frame is None or frame.size < 3:
            samples.append((timestamp, None))
            previous = None
            continue
        grey = _grey(frame, ACTIVITY_WIDTH)
        box = None
        if previous is not None and previous[1].shape == grey.shape and _same_shot(cuts, previous[0], timestamp):
            changed = cv2.absdiff(grey, previous[1]) > ACTIVITY_LEVEL
            for mask in masks_at(timestamp):
                _clear(changed, mask)
            if changed.mean() >= ACTIVITY_MIN_SHARE:
                ys, xs = np.nonzero(changed)
                box = _spread(xs, ys, grey.shape[1], grey.shape[0], ACTIVITY_PERCENTILES)
        samples.append((timestamp, box))
        previous = (timestamp, grey)
    return samples


def _clear(changed: np.ndarray, box: Box) -> None:
    """Zero ``box``, grown by ``FACE_MASK_GROWTH`` about its centre, in ``changed``."""
    height, width = changed.shape
    cx, cy = box.center
    half_w, half_h = box.width * FACE_MASK_GROWTH / 2, box.height * FACE_MASK_GROWTH / 2
    left, right = max(0, int((cx - half_w) * width)), min(width, int(np.ceil((cx + half_w) * width)))
    top, bottom = max(0, int((cy - half_h) * height)), min(height, int(np.ceil((cy + half_h) * height)))
    changed[top:bottom, left:right] = False


def salient_boxes(frames: Iterable[tuple[float, np.ndarray]], cuts: list[float]) -> FocusSamples:
    """Per sample, the region of footage that stands out or moves.

    Spectral-residual saliency finds what differs from the rest of the
    picture; motion since the previous sample of the same shot finds what is
    happening. Either alone misleads: saliency picks a bright sign in a still
    landscape, motion picks leaves in the wind.
    """
    detector = cv2.saliency.StaticSaliencySpectralResidual_create()
    samples: FocusSamples = []
    previous: tuple[float, np.ndarray] | None = None
    for timestamp, frame in frames:
        if frame is None or frame.size < 3:
            samples.append((timestamp, None))
            previous = None
            continue
        small = cv2.resize(frame, (SALIENCY_WIDTH, max(2, round(frame.shape[0] * SALIENCY_WIDTH / frame.shape[1]))),
                           interpolation=cv2.INTER_AREA)
        ok, saliency = detector.computeSaliency(small)
        combined = _normalised(saliency.astype(np.float32)) if ok else np.zeros(small.shape[:2], np.float32)
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if previous is not None and previous[1].shape == grey.shape and _same_shot(cuts, previous[0], timestamp):
            motion = _normalised(cv2.GaussianBlur(np.abs(grey - previous[1]), (5, 5), 0))
            combined = combined * (1 - MOTION_WEIGHT) + motion * MOTION_WEIGHT
        previous = (timestamp, grey)
        combined = cv2.GaussianBlur(combined, (7, 7), 0)
        salient = combined > combined.mean() + SALIENT_SIGMA * combined.std()
        if not salient.any():
            samples.append((timestamp, None))
            continue
        ys, xs = np.nonzero(salient)
        samples.append((timestamp, _spread(xs, ys, combined.shape[1], combined.shape[0], SALIENT_PERCENTILES)))
    return samples


def _normalised(values: np.ndarray) -> np.ndarray:
    peak = float(values.max()) if values.size else 0.0
    return values / peak if peak > 0 else values


def key_colour(frames: Iterable[tuple[float, np.ndarray]]) -> str | None:
    """The green screen's colour as FFmpeg's ``0xRRGGBB``, or None when no frame shows one."""
    greens: list[np.ndarray] = []
    for index, (_, frame) in enumerate(frames):
        if index % GREEN_SAMPLE_EVERY or frame is None or frame.ndim != 3 or frame.size < 3:
            continue
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = (
            (hsv[..., 0] >= GREEN_HUE[0]) & (hsv[..., 0] <= GREEN_HUE[1])
            & (hsv[..., 1] >= GREEN_MIN_SATURATION) & (hsv[..., 2] >= GREEN_MIN_VALUE)
        )
        if mask.mean() >= GREEN_MIN_SHARE:
            greens.append(frame[mask])
    if not greens:
        return None
    blue, green, red = (int(v) for v in np.median(np.concatenate(greens), axis=0))
    return f"0x{red:02X}{green:02X}{blue:02X}"
