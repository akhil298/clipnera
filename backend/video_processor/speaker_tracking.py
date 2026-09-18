"""Active-speaker detection from lip motion, cross-checked with diarization.

Faces are linked into tracks across sampled frames, each track is scored by how
much its mouth region changes between frames, and the winner per timestamp is
the active speaker. Speech-free stretches are ignored, so a person chewing or
laughing off-mic does not steal the frame.

This runs entirely on CPU with OpenCV and no external model, so it costs nothing
to run and works on an EC2 instance with no outbound internet access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.logging_config import get_logger
from video_processor.face_detection import Face
from video_processor.geometry import Box

log = get_logger(__name__)

# Faces overlapping more than this across consecutive samples are the same person.
TRACK_MATCH_IOU = 0.2
# Frames are sampled about twice a second, far enough apart that a person can
# move clear of their previous box, so proximity is also accepted: a detection
# within this multiple of the face width is treated as the same person.
TRACK_MATCH_DISTANCE_RATIO = 1.5
# A track must appear in at least this fraction of the sampled frames to count as
# a participant. Detection flickers, so this is deliberately forgiving.
MIN_TRACK_PRESENCE = 0.08
# ...but a lone detection is noise, not a person, so a track also needs this many
# observations before it can displace or accompany a real speaker.
MIN_TRACK_SAMPLES = 2
# Fragmented tracks whose typical positions sit this close together, relative to
# face width, describe one person and are merged.
TRACK_MERGE_DISTANCE_RATIO = 1.0
# Mouth-motion below this is treated as a closed mouth.
SILENT_MOTION_THRESHOLD = 2.0


@dataclass
class FaceSample:
    """One face observed at one timestamp."""

    timestamp: float
    face: Face
    mouth_motion: float = 0.0


@dataclass
class SpeakerTrack:
    """One person followed across the sampled frames."""

    track_id: int
    samples: list[FaceSample] = field(default_factory=list)

    @property
    def first_seen(self) -> float:
        return self.samples[0].timestamp if self.samples else 0.0

    @property
    def last_seen(self) -> float:
        return self.samples[-1].timestamp if self.samples else 0.0

    @property
    def mean_area(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.face.box.area for s in self.samples) / len(self.samples)

    def box_at(self, timestamp: float) -> Box | None:
        """Position at ``timestamp``, interpolated between observations."""
        if not self.samples:
            return None
        if len(self.samples) == 1 or timestamp <= self.samples[0].timestamp:
            return self.samples[0].face.box
        if timestamp >= self.samples[-1].timestamp:
            return self.samples[-1].face.box
        for earlier, later in zip(self.samples, self.samples[1:]):
            if earlier.timestamp <= timestamp <= later.timestamp:
                span = max(1e-6, later.timestamp - earlier.timestamp)
                ratio = (timestamp - earlier.timestamp) / span
                a, b = earlier.face.box, later.face.box
                return Box(
                    x=a.x + (b.x - a.x) * ratio,
                    y=a.y + (b.y - a.y) * ratio,
                    width=a.width + (b.width - a.width) * ratio,
                    height=a.height + (b.height - a.height) * ratio,
                )
        return self.samples[-1].face.box

    def motion_at(self, timestamp: float) -> float:
        if not self.samples:
            return 0.0
        nearest = min(self.samples, key=lambda s: abs(s.timestamp - timestamp))
        return nearest.mouth_motion


def _crop_mouth(frame: np.ndarray, mouth: Box) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x0 = max(0, int(mouth.x * width))
    y0 = max(0, int(mouth.y * height))
    x1 = min(width, int((mouth.x + mouth.width) * width))
    y1 = min(height, int((mouth.y + mouth.height) * height))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    patch = frame[y0:y1, x0:x1]
    if patch.size == 0:
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    # Fixed size so motion is comparable between near and distant faces.
    return cv2.resize(gray, (32, 16), interpolation=cv2.INTER_AREA)


def build_tracks(
    frames: list[tuple[float, np.ndarray]],
    faces_per_frame: list[list[Face]],
) -> list[SpeakerTrack]:
    """Link per-frame detections into tracks and score their lip motion."""
    tracks: list[SpeakerTrack] = []
    previous_patches: dict[int, np.ndarray] = {}
    next_track_id = 0

    for (timestamp, frame), faces in zip(frames, faces_per_frame):
        claimed: set[int] = set()
        for face in faces:
            match = _best_track(tracks, face.box, claimed)
            if match is None:
                match = SpeakerTrack(track_id=next_track_id)
                tracks.append(match)
                next_track_id += 1
            claimed.add(match.track_id)

            motion = 0.0
            patch = _crop_mouth(frame, face.mouth)
            if patch is not None:
                earlier = previous_patches.get(match.track_id)
                if earlier is not None and earlier.shape == patch.shape:
                    motion = float(np.mean(cv2.absdiff(earlier, patch)))
                previous_patches[match.track_id] = patch

            match.samples.append(FaceSample(timestamp=timestamp, face=face, mouth_motion=motion))

    expected = max(1, len(frames))
    merged = merge_fragmented_tracks(tracks)
    kept = [
        t for t in merged
        if len(t.samples) >= MIN_TRACK_SAMPLES and len(t.samples) / expected >= MIN_TRACK_PRESENCE
    ]
    log.info(
        "Speaker tracks built: %d candidate(s), %d after merge, %d kept (from %d sampled frame(s))",
        len(tracks), len(merged), len(kept), len(frames),
    )
    if merged and not kept:
        log.warning(
            "All %d track(s) fell below the presence threshold; falling back to the longest",
            len(merged),
        )
        kept = [max(merged, key=lambda t: len(t.samples))]
    return kept


def _center_distance(a: Box, b: Box) -> float:
    ax, ay = a.center
    bx, by = b.center
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _best_track(tracks: list[SpeakerTrack], box: Box, claimed: set[int]) -> SpeakerTrack | None:
    """Closest existing track for a detection, by overlap or proximity.

    Overlap alone is too strict at this sample rate: a speaker who shifts
    between samples produces boxes that barely intersect, which split one person
    into many short tracks that are then all discarded as too brief.
    """
    best: SpeakerTrack | None = None
    best_score = 0.0
    for track in tracks:
        if track.track_id in claimed or not track.samples:
            continue
        previous = track.samples[-1].face.box
        iou = previous.intersection_over_union(box)
        reach = max(previous.width, box.width) * TRACK_MATCH_DISTANCE_RATIO
        distance = _center_distance(previous, box)
        if iou >= TRACK_MATCH_IOU:
            score = 1.0 + iou
        elif distance <= reach:
            score = 1.0 - distance / max(1e-6, reach)
        else:
            continue
        if score > best_score:
            best = track
            best_score = score
    return best


def _median_center(track: SpeakerTrack) -> tuple[float, float]:
    xs = sorted(s.face.box.center[0] for s in track.samples)
    ys = sorted(s.face.box.center[1] for s in track.samples)
    mid = len(xs) // 2
    return xs[mid], ys[mid]


def merge_fragmented_tracks(tracks: list[SpeakerTrack]) -> list[SpeakerTrack]:
    """Combine tracks that describe the same person in the same place.

    A detector that flickers produces several partial tracks for one speaker;
    left separate, each falls under the presence threshold and the speaker is
    lost entirely.
    """
    merged: list[SpeakerTrack] = []
    for track in sorted(tracks, key=lambda t: len(t.samples), reverse=True):
        cx, cy = _median_center(track)
        width = max(s.face.box.width for s in track.samples)
        target = None
        for candidate in merged:
            ox, oy = _median_center(candidate)
            reach = max(width, max(s.face.box.width for s in candidate.samples))
            if ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5 <= reach * TRACK_MERGE_DISTANCE_RATIO:
                target = candidate
                break
        if target is None:
            merged.append(track)
            continue
        by_timestamp = {s.timestamp: s for s in target.samples}
        by_timestamp.update({s.timestamp: s for s in track.samples if s.timestamp not in by_timestamp})
        target.samples = sorted(by_timestamp.values(), key=lambda s: s.timestamp)
    return merged


def speech_intervals(transcript_segments: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Merged spans where somebody is talking."""
    spans = sorted(
        (float(s.get("start", 0.0)), float(s.get("end", 0.0)))
        for s in transcript_segments
        if str(s.get("text", "")).strip()
    )
    merged: list[tuple[float, float]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def is_speaking_at(timestamp: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start <= timestamp <= end for start, end in intervals)


def active_speaker_at(
    timestamp: float,
    tracks: list[SpeakerTrack],
    intervals: list[tuple[float, float]],
) -> SpeakerTrack | None:
    """The track most likely talking at ``timestamp``.

    Falls back to the largest visible face when nobody is audibly speaking, so
    the crop stays on the subject during pauses instead of drifting.
    """
    visible = [t for t in tracks if t.first_seen <= timestamp <= t.last_seen]
    if not visible:
        visible = tracks
    if not visible:
        return None
    if len(visible) == 1:
        return visible[0]

    if not is_speaking_at(timestamp, intervals):
        return max(visible, key=lambda t: t.mean_area)

    scored = [(t, t.motion_at(timestamp)) for t in visible]
    best_track, best_motion = max(scored, key=lambda item: item[1])
    if best_motion < SILENT_MOTION_THRESHOLD:
        # No mouth is clearly moving; prefer the most prominent face.
        return max(visible, key=lambda t: t.mean_area)
    return best_track
