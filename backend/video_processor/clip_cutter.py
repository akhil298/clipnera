"""Single owner of cutting a clip: sample, detect, frame, render.

Replaces logic that was spread across ``clip_generation.service``,
``content_intelligence.reframing``, ``content_intelligence.crop_strategy`` and
``video_processor.ffmpeg_service``, where each stage re-derived crop geometry by
hand and no one place was responsible for the result.

Design notes:

* Layout is inferred from faces actually detected in the clip, not from a
  separate analysis pass that had no face data to work with.
* The crop follows the active speaker per frame and is smoothed, rather than
  being a single static window per scene.
* Output is deliberately caption-free. Subtitles are burned at export time from
  whichever style the user picks, so one cut serves every style.
* Frames are sampled with a single downscaled FFmpeg pass per clip, which keeps
  CPU and memory flat on a small EC2 instance.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.exceptions import CustomException
from core.logging_config import get_logger
from video_processor.face_detection import Face, FaceDetector
from video_processor.geometry import (
    Box,
    crop_around,
    crop_covering,
    normalize_box,
    output_dimensions,
    target_crop_size,
)
from video_processor.speaker_tracking import (
    SpeakerTrack,
    active_speaker_at,
    build_tracks,
    speech_intervals,
)

log = get_logger(__name__)

# Frames sampled per second of clip. Two is enough to follow a speaker turn
# while keeping one 60s clip to ~120 detections.
SAMPLE_FPS = 2.0
MAX_SAMPLED_FRAMES = 120
# Face detection runs on a downscaled copy; boxes are normalised so they map
# back to full resolution exactly.
DETECT_WIDTH = 640
# Crop points emitted per second of output.
TRACKING_FPS = 4.0
MAX_TRACKING_POINTS = 240
# Exponential smoothing factor, applied forward then backward for zero phase
# lag. Lower is calmer.
SMOOTHING_ALPHA = 0.22
# Width of the median pre-filter, in samples. Removes single-sample detector
# jitter before smoothing so it is never baked into the curve.
MEDIAN_WINDOW = 5
# Crop ignores speaker movement smaller than this fraction of the frame, so a
# subject shifting slightly in their seat does not cause the frame to drift.
MOVEMENT_DEADZONE = 0.015
# Hard ceiling on pan speed, in fractions of frame width per second. Keeps a
# speaker switch as a controlled glide instead of a snap.
MAX_PAN_PER_SECOND = 0.35
# Faces occupying less than this share of frame width suggest the subject is not
# the point of the shot (gameplay, slides, wide stage).
SMALL_FACE_RATIO = 0.08

# Headroom so a framed face sits slightly above centre, as a camera operator
# would frame it, instead of dead centre.
VERTICAL_BIAS = 0.06


@dataclass
class CutRequest:
    """Everything needed to cut one clip."""

    source_path: str
    output_dir: Path
    clip_id: str
    start: float
    end: float
    aspect_ratios: list[str]
    content_category: str = "unknown"
    transcript_segments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class CutResult:
    """What a cut produced, per aspect ratio."""

    clip_id: str
    start: float
    end: float
    duration: float
    layout: str
    strategy: str
    speaker_count: int
    output_files: dict[str, str] = field(default_factory=dict)
    crop_tracking: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    faces: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def rendered(self) -> bool:
        return any(self.output_files.values())


class ClipCutter:
    """Cuts a time range out of a source video, framed on whoever is talking."""

    def __init__(self, face_detector: FaceDetector | None = None) -> None:
        self._faces = face_detector or FaceDetector()

    async def cut(self, request: CutRequest) -> CutResult:
        if request.duration <= 0:
            raise CustomException(
                message=f"Clip {request.clip_id} has a non-positive duration",
                code="INVALID_CLIP_RANGE",
                status_code=400,
            )

        started = time.monotonic()
        source_width, source_height = await self._source_dimensions(request.source_path)

        frames = await self._sample_frames(request)
        faces_per_frame = await asyncio.to_thread(self._detect_faces, request.clip_id, frames)
        tracks = build_tracks(frames, faces_per_frame)
        for track in tracks:
            log.info(
                "[TRACK] clip=%s id=%d samples=%d seen=%.2fs-%.2fs mean_area=%.4f mean_motion=%.2f",
                request.clip_id, track.track_id, len(track.samples), track.first_seen,
                track.last_seen, track.mean_area,
                sum(s.mouth_motion for s in track.samples) / len(track.samples),
            )
        intervals = speech_intervals(request.transcript_segments)
        layout = self._classify_layout(tracks, request.content_category)

        result = CutResult(
            clip_id=request.clip_id,
            start=request.start,
            end=request.end,
            duration=request.duration,
            layout=layout,
            strategy=self._strategy_for(layout),
            speaker_count=len(tracks),
            faces=[s.face.as_dict() for t in tracks for s in t.samples[:1]],
        )

        log.info(
            "[CUT] clip=%s %.2fs-%.2fs (%.2fs) layout=%s speakers=%d frames=%d backend=%s",
            request.clip_id, request.start, request.end, request.duration,
            layout, len(tracks), len(frames), self._faces.backend,
        )

        for aspect_ratio in request.aspect_ratios:
            tracking = self._build_tracking(
                request=request,
                tracks=tracks,
                intervals=intervals,
                layout=layout,
                aspect_ratio=aspect_ratio,
                source_width=source_width,
                source_height=source_height,
            )
            result.crop_tracking[aspect_ratio] = [point.copy() for point in tracking]
            output_path = self._output_path(request, aspect_ratio)
            try:
                await self._render(
                    request=request,
                    output_path=output_path,
                    tracking=tracking,
                    aspect_ratio=aspect_ratio,
                    source_width=source_width,
                    source_height=source_height,
                )
                result.output_files[aspect_ratio] = str(output_path)
            except CustomException as exc:
                log.error(
                    "[CUT FAIL] clip=%s ratio=%s: %s",
                    request.clip_id, aspect_ratio, exc.message,
                )
                result.output_files[aspect_ratio] = ""
                result.errors.append(f"{aspect_ratio}: {exc.message}")

        log.info(
            "[CUT DONE] clip=%s rendered=%d/%d elapsed=%.1fs",
            request.clip_id,
            sum(1 for path in result.output_files.values() if path),
            len(request.aspect_ratios),
            time.monotonic() - started,
        )
        return result

    # ---- source inspection -------------------------------------------------

    async def _source_dimensions(self, source_path: str) -> tuple[int, int]:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            source_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        raw = stdout.decode("utf-8", errors="ignore").strip().splitlines()
        if proc.returncode != 0 or not raw:
            raise CustomException(
                message=f"Could not read video dimensions: {stderr.decode('utf-8', errors='ignore')[-200:]}",
                code="VIDEO_DIMENSIONS_UNAVAILABLE",
                status_code=400,
            )
        try:
            width, height = (int(part) for part in raw[0].split("x", 1))
        except ValueError as exc:
            raise CustomException(
                message=f"Unexpected ffprobe dimensions output: {raw[0]!r}",
                code="VIDEO_DIMENSIONS_UNAVAILABLE",
                status_code=400,
            ) from exc
        if width <= 0 or height <= 0:
            raise CustomException(
                message="Source video reports zero dimensions",
                code="VIDEO_DIMENSIONS_UNAVAILABLE",
                status_code=400,
            )
        return width, height

    # ---- frame sampling ----------------------------------------------------

    async def _sample_frames(self, request: CutRequest) -> list[tuple[float, np.ndarray]]:
        """Decode evenly spaced frames from the clip range in one FFmpeg pass.

        One process per clip rather than one per frame; at 8 frames a clip the
        old per-frame approach spawned 80 processes for a 10-clip project.
        """
        fps = min(SAMPLE_FPS, MAX_SAMPLED_FRAMES / max(1e-6, request.duration))
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{request.start:.3f}",
            "-i", request.source_path,
            "-t", f"{request.duration:.3f}",
            "-vf", f"fps={fps:.4f},scale={DETECT_WIDTH}:-2",
            "-an", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5",
            "pipe:1",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.warning(
                "Frame sampling failed for clip %s: %s",
                request.clip_id, stderr.decode("utf-8", errors="ignore")[-200:],
            )
            return []

        images = _split_mjpeg(stdout)
        step = 1.0 / fps if fps > 0 else request.duration
        frames: list[tuple[float, np.ndarray]] = []
        for index, payload in enumerate(images):
            frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.size == 0:
                continue
            frames.append((request.start + index * step, frame))

        log.info(
            "[FRAMES] clip=%s sampled=%d decoded=%d fps=%.2f width=%d",
            request.clip_id, len(images), len(frames), fps, DETECT_WIDTH,
        )
        if not frames:
            log.warning("[FRAMES] clip=%s produced no decodable frames; face detection skipped", request.clip_id)
        return frames

    def _detect_faces(self, clip_id: str, frames: list[tuple[float, np.ndarray]]) -> list[list[Face]]:
        started = time.monotonic()
        faces_per_frame = [self._faces.detect(frame) for _, frame in frames]

        all_faces = [face for faces in faces_per_frame for face in faces]
        frames_with_faces = sum(1 for faces in faces_per_frame if faces)
        log.info(
            "[FACES] clip=%s backend=%s frames=%d with_faces=%d total_faces=%d max_per_frame=%d "
            "avg_confidence=%.2f elapsed=%.2fs",
            clip_id, self._faces.backend, len(frames), frames_with_faces, len(all_faces),
            max((len(faces) for faces in faces_per_frame), default=0),
            sum(f.confidence for f in all_faces) / len(all_faces) if all_faces else 0.0,
            time.monotonic() - started,
        )
        if frames and not all_faces:
            log.warning("[FACES] clip=%s no faces detected in any sampled frame; crop will centre", clip_id)
        return faces_per_frame

    # ---- layout ------------------------------------------------------------

    def _classify_layout(self, tracks: list[SpeakerTrack], content_category: str) -> str:
        """Infer layout from the faces actually found in this clip.

        The previous layout analyser keyed off vision-model output that was
        never produced, so it always reported "unknown" and every clip fell back
        to a centre crop.
        """
        category = (content_category or "unknown").lower()
        if not tracks:
            if category in ("gaming", "tech", "tutorial_educational"):
                return "gameplay_only"
            return "no_subject"

        largest = max(t.mean_area for t in tracks)
        small_faces = largest < (SMALL_FACE_RATIO ** 2)

        if category == "gaming":
            return "gaming_with_facecam" if tracks else "gameplay_only"
        if small_faces and category in ("tutorial_educational", "tech", "news_politics"):
            return "speaker_plus_screen"

        if len(tracks) == 1:
            return "single_subject"
        if len(tracks) == 2:
            first, second = (t.samples[0].face.box for t in tracks[:2])
            dx = abs(first.center[0] - second.center[0])
            dy = abs(first.center[1] - second.center[1])
            return "two_subjects_left_right" if dx >= dy else "two_subjects_top_bottom"
        return "multi_subject_grid"

    @staticmethod
    def _strategy_for(layout: str) -> str:
        return {
            "single_subject": "follow_speaker",
            "two_subjects_left_right": "follow_speaker",
            "two_subjects_top_bottom": "follow_speaker",
            "multi_subject_grid": "cover_subjects",
            "gaming_with_facecam": "cover_subjects",
            "gameplay_only": "center",
            "speaker_plus_screen": "cover_subjects",
            "no_subject": "center",
        }.get(layout, "center")

    # ---- crop tracking -----------------------------------------------------

    def _build_tracking(
        self,
        request: CutRequest,
        tracks: list[SpeakerTrack],
        intervals: list[tuple[float, float]],
        layout: str,
        aspect_ratio: str,
        source_width: int,
        source_height: int,
    ) -> list[dict[str, Any]]:
        """Per-frame crop windows, smoothed, in source-video timestamps."""
        crop_w, crop_h = target_crop_size(source_width, source_height, aspect_ratio)
        # A crop that already covers the frame cannot pan, so emit one static point.
        if crop_w >= source_width and crop_h >= source_height:
            return [{
                "timestamp": round(request.start, 3),
                "bbox": Box(0.0, 0.0, 1.0, 1.0).as_dict(),
                "strategy": "no_change",
            }]

        strategy = self._strategy_for(layout)
        count = max(2, min(MAX_TRACKING_POINTS, int(request.duration * TRACKING_FPS)))
        step = request.duration / max(1, count - 1)

        timestamps = [request.start + index * step for index in range(count)]
        targets = [
            self._target_center(
                ts, tracks, intervals, strategy, source_width, source_height, aspect_ratio
            )
            for ts in timestamps
        ]
        centred = sum(1 for target in targets if target is None)
        raw = [target or (0.5, 0.5) for target in targets]
        log.info(
            "[CROP] clip=%s ratio=%s strategy=%s crop=%dx%d points=%d subject_framed=%d centred=%d",
            request.clip_id, aspect_ratio, strategy, crop_w, crop_h, count, count - centred, centred,
        )

        xs = _smooth_series([point[0] for point in raw], step)
        ys = _smooth_series([point[1] for point in raw], step)

        return [
            {
                "timestamp": round(ts, 3),
                "bbox": crop_around(x, y, source_width, source_height, aspect_ratio).as_dict(),
                "strategy": strategy,
            }
            for ts, x, y in zip(timestamps, xs, ys)
        ]

    def _target_center(
        self,
        timestamp: float,
        tracks: list[SpeakerTrack],
        intervals: list[tuple[float, float]],
        strategy: str,
        source_width: int,
        source_height: int,
        aspect_ratio: str,
    ) -> tuple[float, float] | None:
        """Where to centre the crop, or ``None`` when no subject is available."""
        if strategy == "center" or not tracks:
            return None

        if strategy == "cover_subjects":
            boxes = [b for b in (t.box_at(timestamp) for t in tracks) if b is not None]
            if not boxes:
                return None
            covering = crop_covering(boxes, source_width, source_height, aspect_ratio)
            return covering.center

        speaker = active_speaker_at(timestamp, tracks, intervals)
        box = speaker.box_at(timestamp) if speaker else None
        if box is None:
            return None
        center_x, center_y = box.center
        # Lift the frame slightly so the subject is not dead centre, and so the
        # lower third stays clear for captions added at export.
        return center_x, max(0.0, center_y - VERTICAL_BIAS)

    # ---- rendering ---------------------------------------------------------

    def _output_path(self, request: CutRequest, aspect_ratio: str) -> Path:
        path = request.output_dir / _safe_name(request.clip_id) / f"{aspect_ratio.replace(':', 'x')}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def _render(
        self,
        request: CutRequest,
        output_path: Path,
        tracking: list[dict[str, Any]],
        aspect_ratio: str,
        source_width: int,
        source_height: int,
    ) -> None:
        from video_processor.ffmpeg_service import FFmpegService

        target_width, target_height = output_dimensions(aspect_ratio)
        await FFmpegService().crop_with_tracking(
            input_path=request.source_path,
            output_path=str(output_path),
            start_time=request.start,
            duration=request.duration,
            crop_tracking=tracking,
            target_width=target_width,
            target_height=target_height,
            source_width=source_width,
            source_height=source_height,
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise CustomException(
                message=f"Render produced an empty file for {aspect_ratio}",
                code="CLIP_RENDER_EMPTY",
                status_code=500,
            )


def _split_mjpeg(payload: bytes) -> list[bytes]:
    """Split a concatenated MJPEG byte stream into individual JPEG images."""
    images: list[bytes] = []
    start = payload.find(b"\xff\xd8")
    while start != -1:
        end = payload.find(b"\xff\xd9", start + 2)
        if end == -1:
            break
        images.append(payload[start:end + 2])
        start = payload.find(b"\xff\xd8", end + 2)
    return images


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)


def _median_filter(values: list[float], window: int) -> list[float]:
    """Drop single-sample spikes before smoothing.

    A missed detection for one frame otherwise pulls the curve toward the
    fallback centre and the smoother turns that into a visible lurch.
    """
    if window < 3 or len(values) < window:
        return list(values)
    half = window // 2
    filtered: list[float] = []
    for index in range(len(values)):
        low = max(0, index - half)
        high = min(len(values), index + half + 1)
        filtered.append(float(np.median(values[low:high])))
    return filtered


def _ema(values: list[float], alpha: float) -> list[float]:
    smoothed: list[float] = []
    current = values[0]
    for value in values:
        if abs(value - current) > MOVEMENT_DEADZONE:
            current += (value - current) * alpha
        smoothed.append(current)
    return smoothed


def _limit_velocity(values: list[float], step: float, max_per_second: float) -> list[float]:
    """Cap how fast the crop may travel between consecutive points."""
    if not values:
        return values
    max_delta = max(1e-6, max_per_second * max(1e-6, step))
    limited = [values[0]]
    for value in values[1:]:
        previous = limited[-1]
        delta = max(-max_delta, min(max_delta, value - previous))
        limited.append(previous + delta)
    return limited


def _smooth_series(values: list[float], step: float) -> list[float]:
    """Turn raw per-frame targets into a smooth, lag-free camera path.

    Median filter removes detector spikes, then a forward and backward EMA pass
    smooths without the phase lag a single pass introduces (which would make the
    crop trail the speaker), and finally a velocity cap keeps speaker switches a
    glide rather than a snap.
    """
    if len(values) < 3:
        return list(values)
    filtered = _median_filter(values, MEDIAN_WINDOW)
    forward = _ema(filtered, SMOOTHING_ALPHA)
    backward = list(reversed(_ema(list(reversed(forward)), SMOOTHING_ALPHA)))
    return _limit_velocity(backward, step, MAX_PAN_PER_SECOND)
