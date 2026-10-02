"""What is on screen, measured cheaply over a whole source video.

The Map and Director passes read the transcript and cannot see the picture,
so this pass measures what a format needs (faces, a facecam, a screen, a green
screen, lips moving with the speech, one person playing two parts) and hands
it to them as :class:`formats.VisualEvidence`, one per ``PROBE_WINDOW_SECONDS``.

Only keyframes are decoded. Decoding every frame of a long 1080p upload costs
minutes on a small instance; keyframes (every 1-10s in typical uploads, and at
every camera cut, where encoders place one) decode in seconds and are thinned
to one per ``SAMPLE_SECONDS``. A source with too few keyframes is decoded in
full instead. Frames stream through one FFmpeg process and are measured one at
a time, so memory stays flat however long the video is.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.logging_config import get_logger
from formats.taxonomy import VisualEvidence
from video_processor.clip_cutter import DETECT_WIDTH, _decode_frames, _split_mjpeg
from video_processor.editing import (
    THUMBNAIL_SIZE,
    FACECAM_MAX_AREA,
    FACECAM_MAX_DRIFT,
    PAIR_MIN_SIZE_RATIO,
    region_around,
    shot_cuts,
    thumbnail,
)
from video_processor.face_detection import Face, FaceDetector
from video_processor.geometry import Box
from video_processor.speaker_tracking import (
    _crop_region,
    _lip_motion,
    is_speaking_at,
    speech_intervals,
)

log = get_logger(__name__)

PROBE_WINDOW_SECONDS = 30.0
# At most one sampled frame per this many seconds.
SAMPLE_SECONDS = 2.0
# Keyframes further apart than this on average leave too few samples per
# window; such a source is decoded in full at one frame per SAMPLE_SECONDS.
MAX_KEYFRAME_GAP_SECONDS = 10.0
READ_CHUNK_BYTES = 1 << 16
SHOWINFO_TIME = re.compile(rb"Parsed_showinfo.*?pts_time:\s*(-?[\d.]+)")

# Faces: a second face counts as a second person on screen only when it is
# about the size of the first; a much smaller one is a photo or a facecam.
# Faces in consecutive samples are the same face when they overlap this much.
FACE_MATCH_IOU = 0.3

# Facecam: a webcam bubble spans this many face sizes, at a webcam's shape...
FACECAM_BUBBLE_SPAN = 2.6
FACECAM_BUBBLE_ASPECT = 4 / 3
# ...over content that changes between samples (gameplay, a playing video, a
# scrolling screen) by at least this much (mean grey difference, 0-255), while
# the bubble itself changes at most this share of that. A small face in a still
# wide shot is a person far from the camera, and one in handheld footage moves
# with everything around it; neither is a facecam.
FACECAM_MIN_CONTENT_CHANGE = 6.0
FACECAM_MAX_BUBBLE_CHANGE = 0.5
# A face this close to the side or bottom edge (share of the frame) sits where
# facecams go, not where a camera angle frames its speaker.
FACECAM_MARGIN = 0.25
# A bubble smaller than this share of the frame is an overlay on full-frame
# content; a larger one takes a side of the frame and the content is the rest.
FACECAM_MAX_OVERLAY_AREA = 0.12

# Screen: left-aligned lines of text (code, documents, slides, web pages)...
SCREEN_MIN_ALIGNED_LINES = 4
TEXT_LINE_HEIGHT = (5, 28)
TEXT_LINE_ALIGN_PX = 3
# ...or a UI: long, exactly horizontal or vertical lines (total length in frame
# widths plus heights), flat areas and few colours. Camera footage of a room
# has straight edges too, but never all three: sensor noise and lighting keep
# its areas textured and its colours many.
SCREEN_MIN_AXIS_LENGTH = 0.5
SCREEN_MIN_FLAT = 0.5
SCREEN_MIN_TOP_COLOURS = 0.6
FLAT_BLOCK_STD = 1.0

# Green screen: chroma green (OpenCV HSV) covering this share of the frame
# outside the person, smooth (median Laplacian), unlike foliage or a green graphic.
GREEN_LOW = (35, 90, 50)
GREEN_HIGH = (85, 255, 255)
GREEN_MIN_SHARE = 0.3
GREEN_MAX_TEXTURE = 6.0

# Graphic backdrop: a person whose background did not change at all between
# samples (a composited still) and looks like a graphic. Mean grey difference.
BACKDROP_MAX_CHANGE = 1.5

# Lip sync: mouth-region change (speaker_tracking._lip_motion, 0-255) above
# which a face is talking between two samples. Samples are seconds apart, so
# head motion is not netted out as the cutter does at a sixth of a second: over
# seconds the head turns as much as the mouth moves, and netting it out erased
# real speech. Talking faces measured 23+ (10th percentile); a still face
# under heavy noise, 4-7.
MOUTH_MOTION_MIN = 12.0

# Clone: face crops closer than this (chi-square of LBP histograms) are one
# person (measured: one person 0.12-0.25, two people sharing a studio 0.14+, 1st
# percentile 0.17; strict, since a false clone is worse than a missed one); torsos less alike than this (histogram correlation) are two outfits,
# and a face this far across the frame is a second character, not a reframe.
FACE_MATCH_DISTANCE = 0.15
TORSO_MAX_CORRELATION = 0.5
CLONE_MIN_SHIFT = 0.2

# evidence_prompt stays under this many characters, however long the video.
EVIDENCE_PROMPT_CHARS = 600


@dataclass
class _Sample:
    """One sampled frame's measurements. ``continues`` is whether it is in the
    same shot as the sample before it; pairwise measurements are ``None`` when not."""

    index: int
    timestamp: float = 0.0
    # Frame width and height in pixels.
    size: tuple[int, int] = (16, 9)
    faces: list[Box] = field(default_factory=list)
    two_faces: bool = False
    screen: bool = False
    green: bool = False
    continues: bool = False
    backdrop: bool | None = None
    talking: bool | None = None
    same_person: bool = False
    # The largest face, for matching one person across shots.
    face_signature: np.ndarray | None = None
    torso_signature: np.ndarray | None = None
    # editing.thumbnail of the frame, kept small, for comparing regions between samples.
    thumb: np.ndarray | None = None


@dataclass
class _Previous:
    gray: np.ndarray
    person: np.ndarray
    mouths: list[tuple[Face, np.ndarray | None]]


async def probe_video(
    video_path: str, duration: float, transcript_segments: list[dict] | None = None,
) -> list[VisualEvidence]:
    """Evidence per ``PROBE_WINDOW_SECONDS`` of the video; [] when it cannot be probed."""
    if duration <= 0:
        return []
    try:
        return await asyncio.to_thread(_probe, video_path, duration, transcript_segments)
    except Exception as exc:
        log.warning("Visual probe failed for %s: %s", video_path, exc)
        return []


def _probe(video_path: str, duration: float, transcript_segments: list[dict] | None) -> list[VisualEvidence]:
    started = time.monotonic()
    detector = FaceDetector()
    samples, cuts = _measure(video_path, detector, keyframes_only=True)
    if len(samples) < duration / MAX_KEYFRAME_GAP_SECONDS:
        log.info("Visual probe: %d keyframe(s) in %.0fs; decoding every frame", len(samples), duration)
        samples, cuts = _measure(video_path, detector, keyframes_only=False)
    if not samples:
        return []
    _mark_clone_shots(samples, cuts)
    speech = speech_intervals(transcript_segments) if transcript_segments else None
    windows = _windows(samples, cuts, duration, speech)
    log.info(
        "Visual probe: %d sample(s), %d cut(s), %d window(s) in %.1fs",
        len(samples), len(cuts), len(windows), time.monotonic() - started,
    )
    return windows


def _measure(video_path: str, detector: FaceDetector, keyframes_only: bool) -> tuple[list[_Sample], list[float]]:
    """Every sampled frame measured, with timestamps, and the camera cuts
    (timestamps of the first sample of each new shot)."""
    sampling = (
        f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{SAMPLE_SECONDS})'"
        if keyframes_only else f"fps={1 / SAMPLE_SECONDS:.4f}"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-nostats",
        *(["-skip_frame", "nokey"] if keyframes_only else []),
        "-i", video_path, "-an", "-sn", "-dn",
        "-vf", f"{sampling},scale={DETECT_WIDTH}:-2,showinfo", "-fps_mode", "passthrough",
        "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "pipe:1",
    ]
    meter = _FrameMeter(detector)
    samples: list[_Sample] = []

    def measured(frames: Iterator[tuple[int, np.ndarray]]) -> Iterator[tuple[int, np.ndarray]]:
        for index, frame in frames:
            samples.append(meter.measure(index, frame))
            yield index, frame

    with tempfile.TemporaryFile() as log_file:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log_file)
        try:
            cut_indices = {round(cut) for cut in shot_cuts(measured(_stream(proc)))}
            proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        log_file.seek(0)
        stderr = log_file.read()
    if proc.returncode != 0:
        log.warning("Visual probe sampling failed: %s", stderr.decode("utf-8", errors="ignore")[-200:])

    timestamps = [float(value) for value in SHOWINFO_TIME.findall(stderr)]
    samples = samples[:len(timestamps)]
    for sample in samples:
        sample.timestamp = timestamps[sample.index]
        if sample.index in cut_indices:
            sample.continues = False
            sample.backdrop = sample.talking = None
    return samples, [timestamps[index] for index in sorted(cut_indices) if index < len(timestamps)]


def _stream(proc: subprocess.Popen) -> Iterator[tuple[int, np.ndarray]]:
    """Decoded frames from an MJPEG pipe, one at a time, numbered from 0."""
    buffer = b""
    count = 0
    while chunk := proc.stdout.read(READ_CHUNK_BYTES):
        buffer += chunk
        end = buffer.rfind(b"\xff\xd9")
        if end == -1:
            continue
        images = _split_mjpeg(buffer[:end + 2])
        buffer = buffer[end + 2:]
        yield from _decode_frames(list(enumerate(images, count)))
        count += len(images)


class _FrameMeter:
    """Measures sampled frames in order, comparing each with the one before."""

    def __init__(self, detector: FaceDetector) -> None:
        self._detector = detector
        self._previous: _Previous | None = None

    def measure(self, index: int, frame: np.ndarray) -> _Sample:
        sample = _Sample(index)
        if frame.shape[0] < 8 or frame.shape[1] < 8:
            self._previous = None
            return sample
        height, width = frame.shape[:2]
        sample.size = (width, height)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = sorted(_detect(self._detector, frame), key=lambda f: f.box.area, reverse=True)
        person = np.zeros((height, width), np.uint8)
        for face in faces:
            region = _person_region(face.box)
            cv2.rectangle(
                person, (int(region.x * width), int(region.y * height)),
                (int((region.x + region.width) * width), int((region.y + region.height) * height)), 255, -1,
            )

        sample.faces = [face.box for face in faces]
        sample.two_faces = len(faces) >= 2 and faces[1].box.width >= faces[0].box.width * PAIR_MIN_SIZE_RATIO
        sample.thumb = thumbnail(frame).astype(np.uint8)
        sample.screen = _screen_like(frame, gray)
        sample.green = _chroma_green(frame, gray, person)
        if faces:
            sample.face_signature = _face_signature(gray, faces[0].box)
            sample.torso_signature = _torso_signature(frame, faces[0].box)
        if sample.two_faces:
            sample.same_person = _same_face(sample.face_signature, _face_signature(gray, faces[1].box))

        mouths = [(face, _crop_region(frame, face.mouth)) for face in faces]
        previous = self._previous
        if previous is not None and previous.gray.shape == gray.shape:
            sample.continues = True
            background = cv2.bitwise_not(cv2.bitwise_or(person, previous.person))
            if cv2.countNonZero(background) > background.size * 0.1:
                change = float(cv2.mean(cv2.absdiff(gray, previous.gray), mask=background)[0])
                sample.backdrop = bool(faces) and faces[0].box.area > FACECAM_MAX_AREA and change <= BACKDROP_MAX_CHANGE \
                    and _graphic_like(frame, gray)
            if faces:
                sample.talking = any(_moving_mouth(mouth, previous.mouths) for mouth in mouths)
        self._previous = _Previous(gray, person, mouths)
        return sample


def _detect(detector: FaceDetector, frame: np.ndarray) -> list[Face]:
    """Faces from YuNet alone when it is loaded. A whole-video share does not
    need RetinaFace's accuracy at ~15x the cost; ``detect_clip`` makes the same
    trade for most clips."""
    if detector.backend == "retinaface" and detector._yunet is not None:
        return detector._postprocess(detector._detect_yunet(frame))
    return detector.detect(frame)


def _person_region(face: Box) -> Box:
    """The face with the head and body below it, which hides the background."""
    x = max(0.0, face.x - face.width * 0.75)
    y = max(0.0, face.y - face.height * 0.3)
    return Box(x, y, min(1.0 - x, face.width * 2.5), 1.0 - y)


def _moving_mouth(current: tuple[Face, np.ndarray | None], previous: list[tuple[Face, np.ndarray | None]]) -> bool:
    """Whether a face's mouth changed since the same face's previous sample."""
    face, mouth = current
    match = max(previous, key=lambda p: p[0].box.intersection_over_union(face.box), default=None)
    if mouth is None or match is None or match[1] is None or match[0].box.intersection_over_union(face.box) < FACE_MATCH_IOU:
        return False
    return _lip_motion(match[1], mouth, None, None) >= MOUTH_MOTION_MIN


def _screen_like(frame: np.ndarray, gray: np.ndarray) -> bool:
    """A screen recording, document or slide rather than camera footage."""
    return _aligned_text_lines(gray) >= SCREEN_MIN_ALIGNED_LINES or _ui_like(frame, gray)


def _graphic_like(frame: np.ndarray, gray: np.ndarray) -> bool:
    """Looser than a screen: a backdrop is partly hidden by the person in front."""
    return _aligned_text_lines(gray) >= SCREEN_MIN_ALIGNED_LINES // 2 or _ui_like(frame, gray) \
        or (_flat_share(gray) >= SCREEN_MIN_FLAT and _top_colours(frame) >= SCREEN_MIN_TOP_COLOURS)


def _aligned_text_lines(gray: np.ndarray) -> int:
    """Text-line shapes that share a left edge with at least two others.

    Letters are found by their gradient and joined into lines; requiring lines
    to start at a shared margin is what separates text from the stripes of a
    bookshelf, a fence or a keyboard.
    """
    gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    joined = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    _, _, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    low, high = TEXT_LINE_HEIGHT
    lefts = np.array([
        x for x, _, w, h, area in stats[1:]
        if low <= h <= high and w >= 3 * h and w >= 24 and area >= 0.4 * w * h
    ])
    if lefts.size < SCREEN_MIN_ALIGNED_LINES // 2:
        return 0
    neighbours = (np.abs(lefts[:, None] - lefts[None, :]) <= TEXT_LINE_ALIGN_PX).sum(axis=1)
    return int((neighbours >= 3).sum())


def _ui_like(frame: np.ndarray, gray: np.ndarray) -> bool:
    if _flat_share(gray) < SCREEN_MIN_FLAT or _top_colours(frame) < SCREEN_MIN_TOP_COLOURS:
        return False
    height, width = gray.shape
    segments = cv2.HoughLinesP(cv2.Canny(gray, 60, 160), 1, np.pi / 180, 60, minLineLength=width // 6, maxLineGap=2)
    if segments is None:
        return False
    axis = sum(abs(x2 - x1) + abs(y2 - y1) for x1, y1, x2, y2 in segments[:, 0] if x1 == x2 or y1 == y2)
    return axis / (width + height) >= SCREEN_MIN_AXIS_LENGTH


def _flat_share(gray: np.ndarray) -> float:
    """Share of 8x8 blocks with no texture at all."""
    height, width = (size // 8 * 8 for size in gray.shape)
    blocks = gray[:height, :width].reshape(height // 8, 8, width // 8, 8).astype(np.float32)
    return float((blocks.std(axis=(1, 3)) < FLAT_BLOCK_STD).mean())


def _top_colours(frame: np.ndarray) -> float:
    """Share of the frame in its four most common colours (16 levels a channel)."""
    quantised = frame >> 4
    codes = (quantised[:, :, 0].astype(np.int32) << 8) | (quantised[:, :, 1].astype(np.int32) << 4) | quantised[:, :, 2]
    counts = np.bincount(codes.ravel(), minlength=4096)
    return float(np.sort(counts)[-4:].sum() / codes.size)


def _chroma_green(frame: np.ndarray, gray: np.ndarray, person: np.ndarray) -> bool:
    outside = cv2.bitwise_not(person)
    area = cv2.countNonZero(outside)
    if area < outside.size * 0.1:
        return False
    green = cv2.bitwise_and(cv2.inRange(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), GREEN_LOW, GREEN_HIGH), outside)
    if cv2.countNonZero(green) < area * GREEN_MIN_SHARE:
        return False
    inner = cv2.erode(green, np.ones((3, 3), np.uint8))
    texture = np.abs(cv2.Laplacian(gray, cv2.CV_16S, ksize=3))[inner > 0]
    return texture.size > 0 and float(np.median(texture)) <= GREEN_MAX_TEXTURE


def _crop(image: np.ndarray, box: Box) -> np.ndarray | None:
    height, width = image.shape[:2]
    x0, y0 = max(0, int(box.x * width)), max(0, int(box.y * height))
    x1, y1 = min(width, int((box.x + box.width) * width)), min(height, int((box.y + box.height) * height))
    return image[y0:y1, x0:x1] if x1 - x0 >= 8 and y1 - y0 >= 8 else None


def _face_signature(gray: np.ndarray, face: Box) -> np.ndarray | None:
    """Local binary pattern histograms over a 4x4 grid of the face, as seen and
    mirrored: texture that tells two people apart under the same lighting,
    unlike colour. A clone's characters often face each other, hence the mirror."""
    crop = _crop(gray, face)
    if crop is None:
        return None
    crop = cv2.equalizeHist(cv2.resize(crop, (50, 50), interpolation=cv2.INTER_AREA))
    return np.stack([_lbp_histogram(crop), _lbp_histogram(crop[:, ::-1])])


def _lbp_histogram(crop: np.ndarray) -> np.ndarray:
    pixels = crop.astype(np.int16)
    centre = pixels[1:-1, 1:-1]
    codes = np.zeros(centre.shape, np.uint8)
    for bit, (dy, dx) in enumerate(((-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1))):
        codes |= ((pixels[1 + dy:49 + dy, 1 + dx:49 + dx] >= centre) << bit).astype(np.uint8)
    cells = codes.reshape(4, 12, 4, 12).transpose(0, 2, 1, 3).reshape(16, 144) >> 3
    hist = np.stack([np.bincount(cell, minlength=32) for cell in cells]).astype(np.float32).ravel()
    return hist / hist.sum()


def _same_face(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    """Whether two face signatures are one person, either way round."""
    if a is None or b is None:
        return False
    return min(float(0.5 * np.sum((a[0] - other) ** 2 / (a[0] + other + 1e-9))) for other in b) <= FACE_MATCH_DISTANCE


def _torso_signature(frame: np.ndarray, face: Box) -> np.ndarray | None:
    """Hue-saturation histogram of the clothes below the face."""
    crop = _crop(frame, Box(face.x - face.width * 0.5, face.y + face.height * 1.2, face.width * 2.0, face.height * 1.3))
    if crop is None:
        return None
    hist = cv2.calcHist([cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)], [0, 1], None, [12, 4], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).ravel()


def _mark_clone_shots(samples: list[_Sample], cuts: list[float]) -> None:
    """Mark both sides of a cut between two shots of one face in different
    clothes at a different place in the frame: one creator as two characters."""
    shots: list[list[_Sample]] = [[]]
    cut_set = set(cuts)
    for sample in samples:
        if sample.timestamp in cut_set and shots[-1]:
            shots.append([])
        shots[-1].append(sample)
    leads = [next((s for s in shot if s.face_signature is not None), None) for shot in shots]
    for (shot, lead), (next_shot, next_lead) in zip(zip(shots, leads), zip(shots[1:], leads[1:])):
        if lead is None or next_lead is None or not _same_face(lead.face_signature, next_lead.face_signature):
            continue
        shift = abs(lead.faces[0].center[0] - next_lead.faces[0].center[0])
        if shift < CLONE_MIN_SHIFT or lead.torso_signature is None or next_lead.torso_signature is None:
            continue
        if cv2.compareHist(lead.torso_signature, next_lead.torso_signature, cv2.HISTCMP_CORREL) <= TORSO_MAX_CORRELATION:
            for sample in shot + next_shot:
                sample.same_person = sample.same_person or bool(sample.faces)


def _windows(
    samples: list[_Sample], cuts: list[float], duration: float, speech: list[tuple[float, float]] | None,
) -> list[VisualEvidence]:
    """One VisualEvidence per window; a window no sample fell in copies its nearest neighbour."""
    count = max(1, int(np.ceil(duration / PROBE_WINDOW_SECONDS)))
    measured: list[VisualEvidence | None] = []
    for number in range(count):
        start, end = number * PROBE_WINDOW_SECONDS, min(duration, (number + 1) * PROBE_WINDOW_SECONDS)
        inside = [s for s in samples if start <= s.timestamp < end or (number == count - 1 and s.timestamp >= end)]
        measured.append(_window(inside, sum(start <= c < end for c in cuts), start, end, speech) if inside else None)
    filled = [w for w in measured if w is not None]
    if not filled:
        return []
    windows = []
    for number, window in enumerate(measured):
        if window is None:
            start = number * PROBE_WINDOW_SECONDS
            nearest = min(filled, key=lambda w: abs(w.start - start))
            window = VisualEvidence(**{**nearest.__dict__, "start": start, "end": min(duration, start + PROBE_WINDOW_SECONDS)})
        windows.append(window)
    return windows


def _window(
    samples: list[_Sample], cut_count: int, start: float, end: float, speech: list[tuple[float, float]] | None,
) -> VisualEvidence:
    def share(flags: list[bool]) -> float:
        return round(sum(flags) / len(flags), 3) if flags else 0.0

    evidence = VisualEvidence(
        start=start,
        end=end,
        face=share([bool(s.faces) for s in samples]),
        two_faces=share([s.two_faces for s in samples]),
        screen=share([s.screen for s in samples]),
        green=share([s.green for s in samples]),
        graphic_backdrop=share([bool(s.backdrop) for s in samples]),
        lip_sync=_lip_sync(samples, speech),
        same_person=share([s.same_person for s in samples]),
        cuts_per_minute=round(cut_count * 60 / max(1.0, end - start), 2),
    )
    _add_facecam(evidence, samples)
    return evidence


def _lip_sync(samples: list[_Sample], speech: list[tuple[float, float]] | None) -> float:
    """Share of speech samples where a visible face is talking. Samples with a
    face that could not be compared with the one before are left out."""
    if speech is None:
        return 1.0 if any(s.faces for s in samples) else 0.0
    spoken = [s for s in samples if is_speaking_at(s.timestamp, speech) and (not s.faces or s.talking is not None)]
    if not spoken:
        return 1.0
    return round(sum(bool(s.talking) for s in spoken) / len(spoken), 3)


def _add_facecam(evidence: VisualEvidence, samples: list[_Sample]) -> None:
    """Set the facecam share and boxes from a small face holding one place
    while the picture around it changes: across a cut, around a still bubble,
    or on a screen."""
    small = [(s, box) for s in samples for box in s.faces if box.area <= FACECAM_MAX_AREA]
    if not small:
        return

    def near(a: Box, b: Box) -> bool:
        return abs(a.center[0] - b.center[0]) + abs(a.center[1] - b.center[1]) <= FACECAM_MAX_DRIFT

    anchor = max((box for _, box in small), key=lambda box: sum(near(box, other) for _, other in small))
    held = {id(s): box for s, box in small if near(box, anchor)}
    if len(held) < 2:
        return
    boxes = list(held.values())
    face = Box(*(float(np.median([getattr(b, key) for b in boxes])) for key in ("x", "y", "width", "height")))
    bubble = region_around(face, FACECAM_BUBBLE_SPAN, FACECAM_BUBBLE_ASPECT, *samples[0].size)
    # The picture cut away while a face in the margin stayed put: an overlay. A
    # face nearer the middle may be the next camera angle's speaker in the same spot.
    cx, cy = face.center
    marginal = min(cx, 1.0 - cx) <= FACECAM_MARGIN or cy >= 1.0 - FACECAM_MARGIN
    across_cut = marginal and any(
        not s.continues and id(s) in held and id(p) in held for p, s in zip(samples, samples[1:])
    )
    if not (across_cut or evidence.screen >= 0.35 or _moves_around(samples, bubble)):
        return
    evidence.facecam = round(len(held) / len(samples), 3)
    evidence.facecam_box = _rounded(bubble)
    evidence.content_box = _rounded(_content_beside(bubble))


def _moves_around(samples: list[_Sample], bubble: Box) -> bool:
    """Whether the picture outside ``bubble`` changes between samples while the bubble holds still."""
    height, width = THUMBNAIL_SIZE[1], THUMBNAIL_SIZE[0]
    inside = np.zeros((height, width), bool)
    inside[int(bubble.y * height):int(np.ceil((bubble.y + bubble.height) * height)),
           int(bubble.x * width):int(np.ceil((bubble.x + bubble.width) * width))] = True
    if inside.all():
        return False
    pairs = [
        np.abs(s.thumb.astype(np.float32) - p.thumb.astype(np.float32))
        for p, s in zip(samples, samples[1:]) if s.continues and s.thumb is not None and p.thumb is not None
    ]
    if not pairs:
        return False
    outside = float(np.median([d[~inside].mean() for d in pairs]))
    within = float(np.median([d[inside].mean() for d in pairs]))
    return outside >= FACECAM_MIN_CONTENT_CHANGE and within <= outside * FACECAM_MAX_BUBBLE_CHANGE


def _content_beside(bubble: Box) -> Box:
    """The whole frame under a small overlay, else the largest strip beside the bubble."""
    if bubble.area <= FACECAM_MAX_OVERLAY_AREA:
        return Box()
    right = bubble.x + bubble.width
    bottom = bubble.y + bubble.height
    strips = (
        Box(0.0, 0.0, bubble.x, 1.0), Box(right, 0.0, 1.0 - right, 1.0),
        Box(0.0, 0.0, 1.0, bubble.y), Box(0.0, bottom, 1.0, 1.0 - bottom),
    )
    return max(strips, key=lambda box: box.width * box.height)


def _rounded(box: Box) -> tuple[float, float, float, float]:
    return tuple(round(value, 4) for value in (box.x, box.y, box.width, box.height))  # type: ignore[return-value]


def evidence_prompt(windows: list[VisualEvidence]) -> str:
    """The probe as a few lines for the AI prompts: shares over the whole video,
    then what is on screen when, e.g. ``0:00-4:30 one face, talking``."""
    if not windows:
        return ""
    total = sum(w.end - w.start for w in windows) or 1.0

    def mean(key: str) -> float:
        return sum(getattr(w, key) * (w.end - w.start) for w in windows) / total

    shares = ", ".join(
        f"{label} {mean(key):.0%}" for key, label in (
            ("face", "face"), ("two_faces", "two faces"), ("facecam", "facecam"), ("screen", "screen"),
            ("green", "green screen"), ("graphic_backdrop", "graphic backdrop"), ("lip_sync", "lips match speech"),
            ("same_person", "same person twice"),
        )
    )
    spans: list[list[Any]] = []
    for window in windows:
        label = _describe(window)
        if spans and spans[-1][2] == label:
            spans[-1][1] = window.end
        else:
            spans.append([window.start, window.end, label])
    timeline = "; ".join(f"{_clock(start)}-{_clock(end)} {label}" for start, end, label in spans)
    text = f"Whole video: {shares}; {mean('cuts_per_minute'):.1f} cuts/min.\nOver time: {timeline}"
    return text if len(text) <= EVIDENCE_PROMPT_CHARS else text[:EVIDENCE_PROMPT_CHARS - 3].rsplit(";", 1)[0] + "; ..."


def _describe(w: VisualEvidence) -> str:
    """What a window shows, in a few words."""
    if w.green >= 0.4:
        return "green screen"
    if w.graphic_backdrop >= 0.5:
        return "person over a still graphic"
    if w.screen >= 0.5:
        label = "screen recording or slides"
        if w.facecam >= 0.4 and w.facecam_box:
            label += f" with webcam {_place(w.facecam_box)}"
        return label
    if w.same_person >= 0.5:
        return "same person twice"
    if w.facecam >= 0.5 and w.facecam_box:
        return f"facecam {_place(w.facecam_box)} over other footage"
    if w.two_faces >= 0.5:
        return "two people on screen"
    if w.face < 0.2:
        return "no face, footage only"
    if w.lip_sync < 0.3:
        return "face on screen, not the voice"
    return "one face, talking" if w.face >= 0.5 else "a face some of the time"


def _place(box: tuple[float, float, float, float]) -> str:
    x, y, width, height = box
    cx, cy = x + width / 2, y + height / 2
    vertical = "top" if cy < 0.4 else "bottom" if cy > 0.6 else "middle"
    horizontal = "left" if cx < 0.4 else "right" if cx > 0.6 else "centre"
    return f"{vertical}-{horizontal}"


def _clock(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"
