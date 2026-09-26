"""Editorial decisions on top of face tracking: layout, shot cuts and beats.

The cutter frames whoever is talking; this module decides how the frame is
built. The frame is decided shot by shot, from the people actually in each
shot: for vertical output it can stack two regions (facecam over gameplay, one
speaker over the other, a screen over its presenter), a shot with nobody in it
is shown whole, and within a followed shot it places the director's beats: a
punch-in zoom where a point lands, a cut to the listener's face for a reaction. Everything here is
geometry and timing; FFmpeg work stays in :mod:`video_processor.ffmpeg_service`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from video_processor.geometry import Box
from video_processor.speaker_tracking import SpeakerTrack

# Composite layouts are built for this shape only; other shapes follow a speaker.
VERTICAL = "9:16"
# Correlation between consecutive sampled frames' colour histograms below which
# the picture is treated as a new shot.
SHOT_CUT_CORRELATION = 0.55
PUNCH_IN_ZOOM = 1.2
PUNCH_IN_SECONDS = 2.0
REACT_SECONDS = 1.2
MIN_BEAT_GAP_SECONDS = 3.0
MIN_PART_SECONDS = 0.4
# A facecam is a small face that stays put.
FACECAM_MAX_AREA = 0.06
FACECAM_MAX_DRIFT = 0.05
# A shot shorter than this joins its neighbour; re-laying the frame for a flash
# of footage reads as a glitch.
MIN_SHOT_SECONDS = 1.0
# A person is in a shot when seen in at least this share of its sampled frames.
MIN_SHOT_PRESENCE = 0.4
# A stacked speaker's cell is centred this many face heights below the face, so
# the face sits in the upper part of the cell with room for the shoulders.
SPEAKER_HEADROOM = 0.5
# A faceless shot is shown whole only when cropping would lose this much more
# width than the output shape keeps; a near match is simply cropped.
FIT_MIN_ASPECT_GAP = 1.15


@dataclass(frozen=True)
class Cell:
    """One stacked region: a source box shown at ``height`` pixels of the output."""

    box: Box
    height: int


@dataclass
class Layout:
    kind: str  # follow | fit | split_gameplay | two_speaker_stack | screen_with_speaker
    cells: list[Cell] = field(default_factory=list)

    @property
    def composite(self) -> bool:
        return bool(self.cells)


@dataclass(frozen=True)
class Part:
    """A stretch of source to render with one framing treatment."""

    start: float
    end: float
    zoom: float = 1.0
    # Normalised centre to hold the crop on (a reaction shot); None follows the tracking.
    hold: tuple[float, float] | None = None


def shot_cuts(frames: Iterable[tuple[float, np.ndarray]]) -> list[float]:
    """Timestamps where the picture changes shot, from sampled frames."""
    cuts: list[float] = []
    previous = None
    for timestamp, frame in frames:
        if frame is None or frame.size < 3:
            continue
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if previous is not None and cv2.compareHist(previous, hist, cv2.HISTCMP_CORREL) < SHOT_CUT_CORRELATION:
            cuts.append(round(timestamp, 3))
        previous = hist
    return cuts


def shot_windows(start: float, end: float, cuts: list[float]) -> list[tuple[float, float]]:
    """``start``..``end`` divided at the camera cuts inside it.

    A sliver shorter than ``MIN_SHOT_SECONDS`` joins the shot before it, or
    the one after when it opens the span.
    """
    bounds = [start, *(c for c in sorted(cuts) if start < c < end), end]
    windows: list[list[float]] = []
    for low, high in zip(bounds, bounds[1:]):
        if windows and (high - low < MIN_SHOT_SECONDS or windows[-1][1] - windows[-1][0] < MIN_SHOT_SECONDS):
            windows[-1][1] = high
        else:
            windows.append([low, high])
    return [(low, high) for low, high in windows]


def tracks_in_shot(
    tracks: list[SpeakerTrack], start: float, end: float, sample_interval: float
) -> list[SpeakerTrack]:
    """The people in ``start``..``end``, each cut down to their samples there.

    A track can span camera angles, and a close-up and a wide shot put the same
    person in different places; averaged over both, the box frames neither.
    """
    expected = max(1.0, (end - start) / sample_interval)
    present = []
    for track in tracks:
        samples = [s for s in track.samples if start <= s.timestamp < end]
        if len(samples) >= expected * MIN_SHOT_PRESENCE:
            present.append(SpeakerTrack(track_id=track.track_id, samples=samples))
    return present


def choose_layout(
    hint: str,
    detected: str,
    tracks: list[SpeakerTrack],
    aspect_ratio: str,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
) -> Layout:
    """How to build the frame, from the director's hint and what was actually detected.

    ``tracks`` are the people in the stretch being framed (see
    :func:`tracks_in_shot`). With nobody there the whole picture is shown, since
    a crop would cut an arbitrary slice out of it. A composite layout is used
    only when the faces it needs were found; any other doubt falls back to
    following the speaker, which is always safe.
    """
    if not tracks and source_width / max(1, source_height) > output_width / output_height * FIT_MIN_ASPECT_GAP:
        return Layout("fit")
    if aspect_ratio != VERTICAL or source_width / max(1, source_height) < 1.2:
        return Layout("follow")
    wants_split = hint == "split_gameplay" or detected == "gaming_with_facecam"
    wants_screen = hint == "screen_with_speaker" or detected == "speaker_plus_screen"

    if wants_split:
        facecam = _facecam(tracks)
        if facecam is not None:
            top = round(output_height * 0.4) // 2 * 2
            return Layout("split_gameplay", [
                Cell(region_around(facecam, 2.6, output_width / top, source_width, source_height), top),
                Cell(_centre_region(output_width / (output_height - top), source_width, source_height), output_height - top),
            ])
    if hint == "two_speaker_stack":
        pair = sorted(_most_present(tracks, 2), key=lambda t: _typical_box(t).center[0])
        if len(pair) == 2:
            half = output_height // 2 // 2 * 2
            heights = (half, output_height - half)
            return Layout("two_speaker_stack", [
                Cell(region_around(_with_headroom(_typical_box(track)), 3.2, output_width / h,
                                   source_width, source_height), h)
                for track, h in zip(pair, heights)
            ])
    if wants_screen:
        speaker = _most_present(tracks, 1)
        if speaker:
            top = round(output_width * source_height / source_width) // 2 * 2
            return Layout("screen_with_speaker", [
                Cell(Box(0.0, 0.0, 1.0, 1.0), top),
                Cell(region_around(_with_headroom(_typical_box(speaker[0])), 3.5, output_width / (output_height - top),
                                   source_width, source_height), output_height - top),
            ])
    return Layout("follow")


def plan_parts(
    start: float,
    end: float,
    beats: list[dict[str, Any]],
    listener_at: Any,
) -> list[Part]:
    """Split one span of a followed shot into parts around its beats.

    ``listener_at(t)`` returns the normalised centre of someone other than the
    speaker at ``t``, or None; a reaction beat without a listener is skipped.
    """
    marks: list[Part] = []
    last = -1e9
    for beat in sorted(beats, key=lambda b: float(b.get("t", 0.0))):
        t = float(beat.get("t", 0.0))
        if not (start <= t < end) or t - last < MIN_BEAT_GAP_SECONDS:
            continue
        if beat.get("fx") == "punch_in":
            marks.append(Part(t, min(end, t + PUNCH_IN_SECONDS), zoom=PUNCH_IN_ZOOM))
        elif beat.get("fx") == "react_cut":
            centre = listener_at(t)
            if centre is None:
                continue
            marks.append(Part(t, min(end, t + REACT_SECONDS), hold=centre))
        else:
            continue
        last = t

    parts: list[Part] = []
    cursor = start
    for mark in marks:
        if mark.end - cursor < MIN_PART_SECONDS:
            continue
        mark_start = mark.start
        if mark_start - cursor >= MIN_PART_SECONDS:
            parts.append(Part(cursor, mark_start))
        elif parts:
            parts[-1] = Part(parts[-1].start, mark_start, parts[-1].zoom, parts[-1].hold)
        else:
            # A sliver before the first beat joins the beat, so nothing is lost.
            mark_start = cursor
        parts.append(Part(mark_start, mark.end, mark.zoom, mark.hold))
        cursor = mark.end
    if end - cursor >= MIN_PART_SECONDS or not parts:
        parts.append(Part(cursor, end))
    elif parts:
        last_part = parts[-1]
        parts[-1] = Part(last_part.start, end, last_part.zoom, last_part.hold)
    return parts


def region_around(box: Box, expand: float, cell_aspect: float, source_width: int, source_height: int) -> Box:
    """A window of ``cell_aspect`` (width / height) around ``box``, grown ``expand`` times, inside the frame."""
    cx, cy = box.center
    width_px = max(box.width * source_width * expand, box.height * source_height * expand * cell_aspect)
    height_px = width_px / cell_aspect
    scale = min(1.0, source_width / width_px, source_height / height_px)
    width_px, height_px = width_px * scale, height_px * scale
    left = min(max(0.0, cx * source_width - width_px / 2), source_width - width_px)
    top = min(max(0.0, cy * source_height - height_px / 2), source_height - height_px)
    return Box(left / source_width, top / source_height, width_px / source_width, height_px / source_height)


def _centre_region(cell_aspect: float, source_width: int, source_height: int) -> Box:
    return region_around(Box(0.5, 0.5, 0.0, 1.0), 1.0, cell_aspect, source_width, source_height)


def _typical_box(track: SpeakerTrack) -> Box:
    """Per-coordinate median of the track's boxes; one stray detection cannot drag it."""
    boxes = [s.face.box for s in track.samples] or [Box()]
    return Box(*(float(np.median([getattr(b, key) for b in boxes])) for key in ("x", "y", "width", "height")))


def _with_headroom(face: Box) -> Box:
    return Box(face.x, face.y + face.height * SPEAKER_HEADROOM, face.width, face.height)


def _most_present(tracks: list[SpeakerTrack], count: int) -> list[SpeakerTrack]:
    return sorted(tracks, key=lambda t: len(t.samples), reverse=True)[:count]


def _facecam(tracks: list[SpeakerTrack]) -> Box | None:
    """The mean box of a small, stationary face, or None."""
    for track in _most_present(tracks, 3):
        mean = _typical_box(track)
        drift = max(
            (abs(s.face.box.center[0] - mean.center[0]) + abs(s.face.box.center[1] - mean.center[1]))
            for s in track.samples
        ) if track.samples else 1.0
        if mean.area <= FACECAM_MAX_AREA and drift <= FACECAM_MAX_DRIFT:
            return mean
    return None
