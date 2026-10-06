"""What is on screen besides people: the thing being shown, and which faces are real.

A stream or screen-share frame holds more than the speaker: a picture, a
browser window or a video being reacted to, a chat column, a follower bar.
Cropping by faces alone throws the picture away and can stack a face drawn in
fan art as if it were a guest. This module finds, per shot:

* content regions: framed rectangles (a picture, a window, a video player)
  that stay on screen, ranked by how likely they are to be what the viewer is
  meant to look at;
* face roles: a person on camera, or a face that is part of the content (a
  drawing, an avatar, a photo, someone inside the video being watched).

Everything is plain geometry on the frames the cutter already samples, so it
costs a few milliseconds a frame and needs no model.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from video_processor.geometry import Box
from video_processor.speaker_tracking import SpeakerTrack

# A content rectangle covers at least this share of the frame, and at most this
# much: smaller is an icon or a thumbnail, larger is the frame itself.
MIN_CONTENT_AREA = 0.04
MAX_CONTENT_AREA = 0.85
# Each side spans at least this share of the frame's side.
MIN_CONTENT_SIDE = 0.12
# A border is a straight edge at least this share of the frame's side long;
# shorter strokes belong to whatever is drawn inside.
LINE_MIN_SHARE = 0.08
# A side counts as drawn when a straight edge covers this share of it...
SIDE_COVERAGE = 0.6
# Collinear pieces of one edge closer than this share of the frame are one edge,
# when they sit within this many pixels of the same row or column.
SEGMENT_GAP_SHARE = 0.06
SEGMENT_POSITION_SLACK = 3
# Edges meeting within this share of the frame width make a corner.
CORNER_SLACK_SHARE = 0.02
# A border without a clean line: pixels this far inside and outside it differ
# by at least this much (sum over B, G, R) along this share of the side.
STEP_OFFSET = 3
STEP_COLOUR_DISTANCE = 60
STEP_COVERAGE = 0.75
# ...and a rectangle needs this many drawn sides (one may be lost to a
# drawing bleeding off its edge, or a window touching the frame).
MIN_DRAWN_SIDES = 3
# A side panel (chat, member list) is narrow and hugs the frame's edge.
PANEL_MAX_WIDTH = 0.25
EDGE_MARGIN = 0.02
# Detections in different samples are one region when they overlap this much.
SAME_REGION_IOU = 0.75
# A region must be seen in this share of a shot's samples to count.
MIN_PRESENCE = 0.4
# Mean absolute grey difference (0-255) between samples inside a region, above
# which it is moving picture (a video, a webcam) rather than a still image.
MOVING_PICTURE_DIFFERENCE = 6.0
# A moving region this small holding a face is a webcam, not content.
CAM_MAX_AREA = 0.12
# A face counts as inside a region when its centre is this far inside the edge.
INSIDE_MARGIN = 0.01


@dataclass(frozen=True)
class Region:
    """A framed rectangle seen across a shot."""

    box: Box
    # Share of the shot's samples it was found in.
    presence: float
    # Share of edge pixels inside it: a blank panel scores near zero.
    detail: float
    # Mean grey difference between consecutive samples inside it.
    motion: float
    # First sample time it was seen.
    first_seen: float

    @property
    def moving(self) -> bool:
        return self.motion >= MOVING_PICTURE_DIFFERENCE

    @property
    def score(self) -> float:
        """How likely this is the thing the viewer should see."""
        cx, cy = self.box.center
        central = 1.0 - min(1.0, abs(cx - 0.5) + abs(cy - 0.5))
        return self.box.area * self.presence * (0.5 + self.detail) * (0.5 + central)

    def contains(self, box: Box) -> bool:
        cx, cy = box.center
        return (
            self.box.x + INSIDE_MARGIN <= cx <= self.box.x + self.box.width - INSIDE_MARGIN
            and self.box.y + INSIDE_MARGIN <= cy <= self.box.y + self.box.height - INSIDE_MARGIN
        )


def frame_rectangles(frame: np.ndarray) -> list[Box]:
    """Framed rectangles in one frame: pictures, windows and players with a clear border.

    Only long straight edges are kept, so strokes of a drawing that touch its
    border cannot break the frame into pieces; a rectangle needs at least
    ``MIN_DRAWN_SIDES`` of its sides drawn.
    """
    height, width = frame.shape[:2]
    edges = cv2.Canny(cv2.GaussianBlur(_grey(frame), (3, 3), 0), 20, 60)
    # Grain makes an edge zig-zag a pixel either way; thickening it across its
    # direction first keeps a border one unbroken line.
    across = cv2.morphologyEx(cv2.dilate(edges, np.ones((3, 1), np.uint8)), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(width * LINE_MIN_SHARE)), 1)))
    down = cv2.morphologyEx(cv2.dilate(edges, np.ones((1, 3), np.uint8)), cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(height * LINE_MIN_SHARE)))))
    # Each straight edge on its own: lines of the surrounding UI that touch a
    # picture's border stay separate segments instead of one merged blob.
    rows = _segments(cv2.dilate(across, np.ones((3, 1), np.uint8)), horizontal=True)
    cols = _segments(cv2.dilate(down, np.ones((1, 3), np.uint8)), horizontal=False)
    rows = _joined(rows, int(width * SEGMENT_GAP_SHARE))
    cols = _joined(cols, int(height * SEGMENT_GAP_SHARE))
    # Two parallel edges of a picture overlap along most of their length. The
    # overlap and the full span are both tried; the drawn-sides check decides,
    # so an edge shortened by a stroke still yields the whole picture.
    candidates: list[tuple[int, int, int, int]] = []
    for (a0, a1, ay), (b0, b1, by) in _pairs(rows):
        if min(a1, b1) - max(a0, b0) >= 0.6 * max(a1 - a0, b1 - b0):
            for left, right in ((max(a0, b0), min(a1, b1)), (min(a0, b0), max(a1, b1))):
                candidates.append((left, min(ay, by), right - left, abs(by - ay)))
    for (a0, a1, ax), (b0, b1, bx) in _pairs(cols):
        if min(a1, b1) - max(a0, b0) >= 0.6 * max(a1 - a0, b1 - b0):
            for top, bottom in ((max(a0, b0), min(a1, b1)), (min(a0, b0), max(a1, b1))):
                candidates.append((min(ax, bx), top, abs(bx - ax), bottom - top))
    candidates += _corner_rectangles(rows, cols, int(width * CORNER_SLACK_SHARE))
    scored: list[tuple[int, Box]] = []
    for x, y, w, h in candidates:
        box = Box(x / width, y / height, w / width, h / height)
        if not _plausible(box):
            continue
        sides = _drawn_sides(frame, across, down, x, y, w, h)
        if sides >= MIN_DRAWN_SIDES:
            scored.append((sides, box))
    # Most sides drawn first, then the larger. Nested rectangles are kept: a
    # picture sits inside a window, and ranking decides which one is shown.
    boxes: list[Box] = []
    for _, box in sorted(scored, key=lambda item: (item[0], item[1].area), reverse=True):
        if not any(box.intersection_over_union(kept) >= SAME_REGION_IOU for kept in boxes):
            boxes.append(box)
    return boxes


def _segments(mask: np.ndarray, horizontal: bool) -> list[tuple[int, int, int]]:
    """(start, end, position) of each straight edge: x range and row, or y range and column."""
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    segments = []
    for x, y, w, h, _ in stats[1:count]:
        segments.append((x, x + w, y + h // 2) if horizontal else (y, y + h, x + w // 2))
    return segments


def _joined(segments: list[tuple[int, int, int]], max_gap: int) -> list[tuple[int, int, int]]:
    """Pieces of one edge rejoined: a stroke touching a border splits it into collinear segments."""
    joined: list[list[int]] = []
    for start, end, position in sorted(segments, key=lambda s: (s[2], s[0])):
        last = next((j for j in reversed(joined) if abs(j[2] - position) <= SEGMENT_POSITION_SLACK), None)
        if last is not None and start - last[1] <= max_gap:
            last[1] = max(last[1], end)
        else:
            joined.append([start, end, position])
    return [(start, end, position) for start, end, position in joined]


def _pairs(segments: list[tuple[int, int, int]]) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    ordered = sorted(segments, key=lambda s: s[2])
    return [(a, b) for i, a in enumerate(ordered) for b in ordered[i + 1:]]


def _corner_rectangles(
    rows: list[tuple[int, int, int]], cols: list[tuple[int, int, int]], slack: int,
) -> list[tuple[int, int, int, int]]:
    """Rectangles spanned by a horizontal and a vertical edge meeting at a corner.

    A drawing that runs off two sides of its picture leaves only the other two
    as clean lines; their corner still pins the picture down.
    """
    found: list[tuple[int, int, int, int]] = []
    for x0, x1, y in rows:
        for y0, y1, x in cols:
            if abs(y0 - y) <= slack:  # the column hangs down from the row
                bottom = y1
                top = y
            elif abs(y1 - y) <= slack:  # the column rises up to the row
                top, bottom = y0, y
            else:
                continue
            if abs(x0 - x) <= slack:
                found.append((x, top, x1 - x, bottom - top))
            elif abs(x1 - x) <= slack:
                found.append((x0, top, x - x0, bottom - top))
    return found


def _drawn_sides(
    frame: np.ndarray, across: np.ndarray, down: np.ndarray, x: int, y: int, w: int, h: int,
) -> int:
    """How many of the rectangle's four sides are a border.

    A side is a border when a straight edge covers most of it, or when the
    colour steps sharply across it along most of its length: a picture whose
    drawing runs off its edge has no clean line there but still stands out
    from what surrounds it.
    """
    pad = 3

    def lined(mask: np.ndarray, rows: slice, cols: slice, axis: int) -> bool:
        band = mask[rows, cols]
        return band.size > 0 and float(band.any(axis=axis).mean()) >= SIDE_COVERAGE

    top = lined(across, slice(max(0, y - pad), y + pad), slice(x, x + w), 0)
    bottom = lined(across, slice(max(0, y + h - pad - 4), y + h + pad), slice(x, x + w), 0)
    left = lined(down, slice(y, y + h), slice(max(0, x - pad), x + pad), 1)
    right = lined(down, slice(y, y + h), slice(max(0, x + w - pad - 4), x + w + pad), 1)
    top = top or _stepped(frame, y + STEP_OFFSET, y - STEP_OFFSET, x, x + w, across_rows=True)
    bottom = bottom or _stepped(frame, y + h - STEP_OFFSET, y + h + STEP_OFFSET, x, x + w, across_rows=True)
    left = left or _stepped(frame, x + STEP_OFFSET, x - STEP_OFFSET, y, y + h, across_rows=False)
    right = right or _stepped(frame, x + w - STEP_OFFSET, x + w + STEP_OFFSET, y, y + h, across_rows=False)
    return sum((top, bottom, left, right))


def _stepped(frame: np.ndarray, inside: int, outside: int, start: int, end: int, across_rows: bool) -> bool:
    """Whether the colour changes sharply between two parallel lines of pixels.

    ``inside`` and ``outside`` are rows (``across_rows``) or columns; the
    lines run from ``start`` to ``end`` along them.
    """
    limit = frame.shape[0] if across_rows else frame.shape[1]
    if not (0 <= inside < limit and 0 <= outside < limit) or end <= start:
        return False
    a = frame[inside, start:end] if across_rows else frame[start:end, inside]
    b = frame[outside, start:end] if across_rows else frame[start:end, outside]
    distance = np.abs(a.astype(np.int16) - b.astype(np.int16))
    if distance.ndim == 2:
        distance = distance.sum(axis=1)
    return float((distance >= STEP_COLOUR_DISTANCE).mean()) >= STEP_COVERAGE


def _plausible(box: Box) -> bool:
    if not (MIN_CONTENT_AREA <= box.area <= MAX_CONTENT_AREA):
        return False
    if box.width < MIN_CONTENT_SIDE or box.height < MIN_CONTENT_SIDE:
        return False
    hugs_side = box.x <= EDGE_MARGIN or box.x + box.width >= 1.0 - EDGE_MARGIN
    return not (hugs_side and box.width <= PANEL_MAX_WIDTH)


def content_regions(samples: list[tuple[float, np.ndarray]]) -> list[Region]:
    """Rectangles that persist across ``samples`` (one shot), best first."""
    if not samples:
        return []
    clusters: list[list[tuple[int, Box]]] = []
    for index, (_, frame) in enumerate(samples):
        for box in frame_rectangles(frame):
            match = next((c for c in clusters if box.intersection_over_union(_median(c)) >= SAME_REGION_IOU), None)
            if match is None:
                clusters.append([(index, box)])
            elif match[-1][0] != index:
                match.append((index, box))
    regions: list[Region] = []
    for cluster in clusters:
        presence = len(cluster) / len(samples)
        if presence < MIN_PRESENCE:
            continue
        box = _median(cluster)
        frames = [samples[i][1] for i, _ in cluster]
        regions.append(Region(
            box=box,
            presence=presence,
            detail=_detail(frames[len(frames) // 2], box),
            motion=_motion(frames, box),
            first_seen=samples[cluster[0][0]][0],
        ))
    return sorted(regions, key=lambda r: r.score, reverse=True)


def _median(cluster: list[tuple[int, Box]]) -> Box:
    boxes = [box for _, box in cluster]
    return Box(*(float(np.median([getattr(b, key) for b in boxes])) for key in ("x", "y", "width", "height")))


def _crop(frame: np.ndarray, box: Box) -> np.ndarray:
    height, width = frame.shape[:2]
    x0, y0 = int(box.x * width), int(box.y * height)
    x1, y1 = int((box.x + box.width) * width), int((box.y + box.height) * height)
    return frame[y0:max(y0 + 1, y1), x0:max(x0 + 1, x1)]


def _grey(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame


def _detail(frame: np.ndarray, box: Box) -> float:
    patch = _grey(_crop(frame, box))
    if patch.size == 0:
        return 0.0
    return float((cv2.Canny(patch, 60, 160) > 0).mean())


def _motion(frames: list[np.ndarray], box: Box) -> float:
    patches = [cv2.resize(_grey(_crop(f, box)), (64, 64)).astype(np.float32) for f in frames]
    if len(patches) < 2:
        return 0.0
    return float(np.mean([np.abs(a - b).mean() for a, b in zip(patches, patches[1:])]))


def person_tracks(tracks: list[SpeakerTrack], regions: list[Region]) -> list[SpeakerTrack]:
    """The tracks that are people on camera; faces belonging to content are dropped.

    A face whose centre sits inside a still content rectangle for most of its
    samples is part of a picture (fan art, an avatar, a photo). Inside a moving
    rectangle it is a webcam when the rectangle is small, and someone in the
    video being watched when it is large. Without content regions every track
    is a person, which is how framing worked before this module.
    """
    if not regions:
        return list(tracks)
    people: list[SpeakerTrack] = []
    for track in tracks:
        if not track.samples:
            continue
        holder = _holding_region(track, regions)
        if holder is None or (holder.moving and holder.box.area <= CAM_MAX_AREA):
            people.append(track)
    return people


def _holding_region(track: SpeakerTrack, regions: list[Region]) -> Region | None:
    """The content region the face sits inside for most of its samples, or None."""
    for region in regions:
        inside = sum(1 for s in track.samples if region.contains(s.face.box))
        if inside >= 0.6 * len(track.samples):
            return region
    return None


def main_content(regions: list[Region], people: list[SpeakerTrack]) -> Region | None:
    """The region the viewer should see, skipping a webcam that frames one of ``people``."""
    for region in regions:
        if region.moving and region.box.area <= CAM_MAX_AREA and any(
            region.contains(s.face.box) for track in people for s in track.samples
        ):
            continue
        return region
    return None
