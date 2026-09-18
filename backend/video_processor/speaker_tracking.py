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

# Faces closer than this across consecutive samples are the same person.
TRACK_MATCH_IOU = 0.3
# A track must appear in at least this fraction of the frames it could have
# appeared in before it is trusted as a real participant.
MIN_TRACK_PRESENCE = 0.2
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
    kept = [t for t in tracks if len(t.samples) / expected >= MIN_TRACK_PRESENCE]
    log.info(
        "Speaker tracks built: %d candidate(s), %d kept (from %d sampled frame(s))",
        len(tracks), len(kept), len(frames),
    )
    return kept


def _best_track(tracks: list[SpeakerTrack], box: Box, claimed: set[int]) -> SpeakerTrack | None:
    best: SpeakerTrack | None = None
    best_iou = TRACK_MATCH_IOU
    for track in tracks:
        if track.track_id in claimed or not track.samples:
            continue
        iou = track.samples[-1].face.box.intersection_over_union(box)
        if iou > best_iou:
            best = track
            best_iou = iou
    return best


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
