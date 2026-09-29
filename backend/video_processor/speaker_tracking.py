"""Active-speaker detection from lip motion, cross-checked with diarization.

Faces are linked into tracks across sampled frames, each track is scored by how
much its mouth region changes between consecutive frames (net of the rest of
the face, so nodding or a camera move is not mistaken for talking), and a
speaker timeline is built with hysteresis so the choice does not flicker.
When the transcript carries diarization labels, each label is matched to the
track whose lips move during that label's speech, and the label then decides
who is talking. Speech-free stretches hold the current speaker, so a person
chewing or laughing off-mic does not steal the frame.

This runs entirely on CPU with OpenCV and no external model, so it costs nothing
to run and works on an EC2 instance with no outbound internet access.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
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
# A person can move clear of their previous box between samples, so proximity
# is also accepted: a detection within this multiple of the face width is
# treated as the same person.
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
# Mouth patches further apart than this are not compared: the difference would
# measure everything that changed in between, not lip movement.
MAX_MOTION_GAP_SECONDS = 0.5
# Lip activity is bursty, so motion is averaged over this window either side.
MOTION_WINDOW_SECONDS = 0.5
# A track counts as on screen at a moment only if it was seen this close to it;
# otherwise a person who left the shot would still be framed.
VISIBLE_GAP_SECONDS = 1.0
# Windowed mouth motion below this is treated as a closed mouth.
SILENT_MOTION_THRESHOLD = 1.5
# A challenger must move its lips this much more than the current speaker...
SWITCH_MOTION_RATIO = 1.4
# ...for this long before the frame cuts to them.
SWITCH_HOLD_SECONDS = 0.6
# A diarization label maps to a track only when that track's lip motion during
# the label's speech beats the runner-up by this factor.
LABEL_MATCH_RATIO = 1.2


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

    def _timestamps(self) -> list[float]:
        return [s.timestamp for s in self.samples]

    def box_at(self, timestamp: float) -> Box | None:
        """Position at ``timestamp``, interpolated between observations."""
        if not self.samples:
            return None
        if len(self.samples) == 1 or timestamp <= self.samples[0].timestamp:
            return self.samples[0].face.box
        if timestamp >= self.samples[-1].timestamp:
            return self.samples[-1].face.box
        index = bisect_left(self._timestamps(), timestamp)
        earlier, later = self.samples[index - 1], self.samples[index]
        span = max(1e-6, later.timestamp - earlier.timestamp)
        ratio = (timestamp - earlier.timestamp) / span
        a, b = earlier.face.box, later.face.box
        return Box(
            x=a.x + (b.x - a.x) * ratio,
            y=a.y + (b.y - a.y) * ratio,
            width=a.width + (b.width - a.width) * ratio,
            height=a.height + (b.height - a.height) * ratio,
        )

    def motion_at(self, timestamp: float, window: float = MOTION_WINDOW_SECONDS) -> float:
        """Mean mouth motion in ``window`` seconds either side of ``timestamp``."""
        timestamps = self._timestamps()
        low = bisect_left(timestamps, timestamp - window)
        high = bisect_right(timestamps, timestamp + window)
        nearby = self.samples[low:high]
        if not nearby:
            return 0.0
        return sum(s.mouth_motion for s in nearby) / len(nearby)

    def visible_at(self, timestamp: float, gap: float = VISIBLE_GAP_SECONDS) -> bool:
        timestamps = self._timestamps()
        return bisect_right(timestamps, timestamp + gap) > bisect_left(timestamps, timestamp - gap)


def _crop_region(frame: np.ndarray, region: Box) -> np.ndarray | None:
    """Grayscale patch at a fixed size, brightness-normalised.

    Fixed size keeps motion comparable between near and distant faces, and
    removing the mean keeps an exposure change from reading as movement.
    """
    height, width = frame.shape[:2]
    x0 = max(0, int(region.x * width))
    y0 = max(0, int(region.y * height))
    x1 = min(width, int((region.x + region.width) * width))
    y1 = min(height, int((region.y + region.height) * height))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    patch = cv2.resize(gray, (32, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    return patch - float(patch.mean())


def _eye_region(face: Box) -> Box:
    """Upper face band. It moves with the head but not with speech."""
    return Box(
        x=face.x + face.width * 0.15,
        y=face.y + face.height * 0.2,
        width=face.width * 0.7,
        height=face.height * 0.3,
    )


def build_tracks(
    frames: Iterable[tuple[float, np.ndarray]],
    faces_per_frame: Iterable[list[Face]],
) -> list[SpeakerTrack]:
    """Link per-frame detections into tracks and score their lip motion.

    Both arguments may be lazy iterables, so callers can stream decoded frames
    instead of holding a whole clip in memory.
    """
    tracks: list[SpeakerTrack] = []
    # Per track: (timestamp, mouth patch, eye patch) from its last observation.
    previous: dict[int, tuple[float, np.ndarray, np.ndarray | None]] = {}
    next_track_id = 0
    frame_count = 0

    for (timestamp, frame), faces in zip(frames, faces_per_frame):
        frame_count += 1
        claimed: set[int] = set()
        for face in faces:
            match = _best_track(tracks, face.box, claimed)
            if match is None:
                match = SpeakerTrack(track_id=next_track_id)
                tracks.append(match)
                next_track_id += 1
            claimed.add(match.track_id)

            motion = 0.0
            mouth = _crop_region(frame, face.mouth)
            if mouth is not None:
                eyes = _crop_region(frame, _eye_region(face.box))
                earlier = previous.get(match.track_id)
                if earlier is not None and timestamp - earlier[0] <= MAX_MOTION_GAP_SECONDS:
                    motion = _lip_motion(earlier[1], mouth, earlier[2], eyes)
                previous[match.track_id] = (timestamp, mouth, eyes)

            match.samples.append(FaceSample(timestamp=timestamp, face=face, mouth_motion=motion))

    expected = max(1, frame_count)
    merged = merge_fragmented_tracks(tracks)
    kept = [
        t for t in merged
        if len(t.samples) >= MIN_TRACK_SAMPLES and len(t.samples) / expected >= MIN_TRACK_PRESENCE
    ]
    log.info(
        "Speaker tracks built: %d candidate(s), %d after merge, %d kept (from %d sampled frame(s))",
        len(tracks), len(merged), len(kept), frame_count,
    )
    if merged and not kept:
        log.warning(
            "All %d track(s) fell below the presence threshold; falling back to the longest",
            len(merged),
        )
        kept = [max(merged, key=lambda t: len(t.samples))]
    return kept


def _lip_motion(
    mouth_before: np.ndarray,
    mouth_after: np.ndarray,
    eyes_before: np.ndarray | None,
    eyes_after: np.ndarray | None,
) -> float:
    """Mouth change net of whole-face change.

    Head turns, nods and camera moves shift the eyes as much as the mouth, so
    subtracting the eye band's change leaves mostly articulation.
    """
    mouth = float(np.mean(np.abs(mouth_after - mouth_before)))
    if eyes_before is None or eyes_after is None:
        return mouth
    head = float(np.mean(np.abs(eyes_after - eyes_before)))
    return max(0.0, mouth - head)


def _center_distance(a: Box, b: Box) -> float:
    ax, ay = a.center
    bx, by = b.center
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _best_track(tracks: list[SpeakerTrack], box: Box, claimed: set[int]) -> SpeakerTrack | None:
    """Closest existing track for a detection, by overlap or proximity.

    Overlap alone is too strict: a speaker who shifts between samples produces
    boxes that barely intersect, which split one person into many short tracks
    that are then all discarded as too brief.
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


def visible_tracks(timestamp: float, tracks: list[SpeakerTrack]) -> list[SpeakerTrack]:
    """Tracks on screen at ``timestamp``; all tracks if none were seen nearby,
    so the crop still has somewhere to go."""
    return [t for t in tracks if t.visible_at(timestamp)] or tracks


def active_speaker_at(
    timestamp: float,
    tracks: list[SpeakerTrack],
    intervals: list[tuple[float, float]],
) -> SpeakerTrack | None:
    """The track most likely talking at ``timestamp``, judged at that instant.

    Falls back to the largest visible face when nobody is audibly speaking or
    no mouth is clearly moving. ``speaker_timeline`` adds hysteresis on top.
    """
    visible = visible_tracks(timestamp, tracks)
    if not visible:
        return None
    if len(visible) == 1:
        return visible[0]

    if not is_speaking_at(timestamp, intervals):
        return max(visible, key=lambda t: t.mean_area)

    best_track, best_motion = max(
        ((t, t.motion_at(timestamp)) for t in visible), key=lambda item: item[1]
    )
    if best_motion < SILENT_MOTION_THRESHOLD:
        return max(visible, key=lambda t: t.mean_area)
    return best_track


def _labelled_segments(
    transcript_segments: list[dict[str, Any]], start: float, end: float
) -> list[tuple[float, float, str]]:
    """Diarized segments overlapping ``start``..``end``."""
    labelled = []
    for segment in transcript_segments:
        label = segment.get("speaker")
        seg_start = float(segment.get("start", 0.0))
        seg_end = float(segment.get("end", 0.0))
        if label and seg_end > start and seg_start < end and str(segment.get("text", "")).strip():
            labelled.append((seg_start, seg_end, str(label)))
    return sorted(labelled)


def match_labels_to_tracks(
    segments: list[tuple[float, float, str]], tracks: list[SpeakerTrack]
) -> dict[str, SpeakerTrack]:
    """Map each diarization label to the track whose lips move while it talks.

    Motion is summed over all of a label's speech in the clip, which is far
    steadier than any single moment. A label with no clear winner is left
    unmapped, and lip motion alone decides during its speech.
    """
    if len(tracks) < 2:
        return {}
    totals: dict[str, dict[int, float]] = {}
    for seg_start, seg_end, label in segments:
        per_track = totals.setdefault(label, {})
        for track in tracks:
            motion = sum(s.mouth_motion for s in track.samples if seg_start <= s.timestamp <= seg_end)
            per_track[track.track_id] = per_track.get(track.track_id, 0.0) + motion

    by_id = {t.track_id: t for t in tracks}
    mapping: dict[str, SpeakerTrack] = {}
    for label, per_track in totals.items():
        ranked = sorted(per_track.items(), key=lambda item: item[1], reverse=True)
        (best_id, best), (_, runner_up) = ranked[0], ranked[1]
        if best > 0 and best >= runner_up * LABEL_MATCH_RATIO:
            mapping[label] = by_id[best_id]
    return mapping


def _label_at(timestamp: float, segments: list[tuple[float, float, str]]) -> str | None:
    for seg_start, seg_end, label in segments:
        if seg_start <= timestamp <= seg_end:
            return label
    return None


def speaker_timeline(
    timestamps: list[float],
    tracks: list[SpeakerTrack],
    transcript_segments: list[dict[str, Any]],
) -> list[SpeakerTrack | None]:
    """Who to frame at each of ``timestamps``, in order.

    Unlike judging each instant alone, this holds the current speaker through
    pauses and only cuts to someone else once they have clearly been talking
    for ``SWITCH_HOLD_SECONDS``, so the crop does not flicker between faces.
    The switch is then dated back to when they started, so the cut lands on
    their first words as an editor's would, not a beat late.
    """
    if not timestamps or not tracks:
        return [None] * len(timestamps)

    intervals = speech_intervals(transcript_segments)
    labelled = _labelled_segments(transcript_segments, timestamps[0], timestamps[-1])
    label_map = match_labels_to_tracks(labelled, tracks)
    if label_map:
        log.info(
            "Diarization labels matched to tracks: %s",
            {label: track.track_id for label, track in label_map.items()},
        )

    current: SpeakerTrack | None = None
    challenger: SpeakerTrack | None = None
    challenger_since = 0
    timeline: list[SpeakerTrack | None] = []

    for index, timestamp in enumerate(timestamps):
        visible = visible_tracks(timestamp, tracks)
        if current is not None and current not in visible:
            current = None  # They left the shot; pick afresh rather than frame empty space.

        candidate = _candidate_at(timestamp, visible, intervals, labelled, label_map, current)
        if current is None:
            current = candidate
            challenger = None
        elif candidate is not None and candidate is not current:
            if candidate is not challenger:
                challenger, challenger_since = candidate, index
            if timestamp - timestamps[challenger_since] >= SWITCH_HOLD_SECONDS:
                current, challenger = candidate, None
                timeline[challenger_since:] = [current] * (index - challenger_since)
        else:
            challenger = None
        timeline.append(current)
    return timeline


def _candidate_at(
    timestamp: float,
    visible: list[SpeakerTrack],
    intervals: list[tuple[float, float]],
    labelled: list[tuple[float, float, str]],
    label_map: dict[str, SpeakerTrack],
    current: SpeakerTrack | None,
) -> SpeakerTrack | None:
    """Who should be framed right now, or ``None`` to keep whoever is framed."""
    if len(visible) == 1:
        return visible[0]
    fallback = None if current is not None else max(visible, key=lambda t: t.mean_area)
    if not is_speaking_at(timestamp, intervals):
        return fallback

    label = _label_at(timestamp, labelled)
    mapped = label_map.get(label) if label else None
    if mapped is not None and mapped in visible:
        return mapped

    best_track, best_motion = max(
        ((t, t.motion_at(timestamp)) for t in visible), key=lambda item: item[1]
    )
    if best_motion < SILENT_MOTION_THRESHOLD:
        return fallback
    if current is not None and best_track is not current:
        if best_motion < current.motion_at(timestamp) * SWITCH_MOTION_RATIO:
            return None
    return best_track
