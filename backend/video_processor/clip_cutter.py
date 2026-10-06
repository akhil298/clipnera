"""Single owner of cutting a clip: sample, detect, frame, render.

Replaces logic that was spread across ``clip_generation.service``,
``content_intelligence.reframing``, ``content_intelligence.crop_strategy`` and
``video_processor.ffmpeg_service``, where each stage re-derived crop geometry by
hand and no one place was responsible for the result.

Design notes:

* Layout is inferred from faces actually detected in the clip, not from a
  separate analysis pass that had no face data to work with, and is decided
  per camera shot and within it per exchange: two people are stacked through
  a two-shot of them and while they trade quick replies on screen together,
  never over a close-up of one of them or B-roll with nobody in it.
* The crop follows the active speaker per frame and is smoothed, rather than
  being a single static window per scene. A change of speaker is a hard cut,
  as an editor would make it, not a pan across the room.
* Output is deliberately caption-free. Subtitles are burned at export time from
  whichever style the user picks, so one cut serves every style.
* Frames are sampled with a single downscaled FFmpeg pass per clip, which keeps
  CPU and memory flat on a small EC2 instance.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.exceptions import CustomException
from clip_generation.hook import Hook
from core.logging_config import get_logger
from video_processor.editing import (
    THUMBNAIL_SIZE,
    Layout,
    Part,
    Turn,
    choose_layout,
    typical_box,
    framing_stretches,
    picture_difference,
    plan_parts,
    presence_cuts,
    shot_cuts,
    shot_windows,
    speaker_turns,
    tracks_in_shot,
)
from video_processor.face_detection import Face, FaceDetector
from video_processor.ffmpeg_service import bubble_layout
from video_processor.focus import PEOPLE, Focus, decide_focus
from video_processor.regions import Region, content_regions, person_tracks
from video_processor.geometry import (
    Box,
    crop_around,
    crop_covering,
    normalize_box,
    output_dimensions,
    target_crop_size,
    union_box,
)
from video_processor.speaker_tracking import (
    SpeakerTrack,
    build_tracks,
    speaker_timeline,
    visible_tracks,
)

log = get_logger(__name__)

# Seconds between frames sent to face detection, for the whole clip whatever
# its length. Lip motion is measured between consecutive samples, and lips move
# several times a second: at 0.5s the difference mostly measured head movement
# and lighting, so the wrong person was picked as the speaker.
SAMPLE_INTERVAL_SECONDS = 1.0 / 6.0
# Face detection runs on a downscaled copy; boxes are normalised so they map
# back to full resolution exactly.
DETECT_WIDTH = 640
# A cut found between two samples is pinned to its frame by decoding that gap
# at this rate, so the crop changes with the picture rather than up to a
# sample later.
CUT_REFINE_FPS = 50.0
# Crop targets computed per second of output, twice the sampling rate so the
# smoothed path has a point between every pair of detections.
TRACKING_FPS = 4.0
# Played stretches closer than this are analysed as one: jump cuts leave short
# gaps, while a story clip's pieces can sit half an hour apart.
WINDOW_BRIDGE_SECONDS = 10.0
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

# Layouts built from two stacked pictures; captions sit on the seam between them.
STACKED_KINDS = frozenset({"two_speaker_stack", "screen_with_speaker"})

# Content regions are found on every this-many-th sampled frame: a picture on
# screen holds still for seconds, so three frames a second is plenty.
REGION_SAMPLE_STEP = 2

# A new speaker further than this share of the crop width from the last is cut
# to; a nearer one is still inside the frame, so the crop glides.
SWITCH_CUT_DISTANCE = 0.5
# A cut in the crop path: the old position holds until this long before the
# new one, so the move happens inside a single frame.
CUT_HOLD_SECONDS = 0.01

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
    # Teaser played before the clip, inside [start, end) in source seconds.
    hook: Hook | None = None
    # Source ranges the body is stitched from, in play order; None plays
    # [start, end) straight through.
    spans: list[tuple[float, float]] | None = None
    # The director's framing choice and beats (source seconds); see video_processor.editing.
    layout_hint: str = "auto"
    beats: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def body_spans(self) -> list[tuple[float, float]]:
        return list(self.spans) if self.spans else [(self.start, self.end)]

    @property
    def body_duration(self) -> float:
        return sum(end - start for start, end in self.body_spans)

    @property
    def windows(self) -> list[tuple[float, float]]:
        """The source the clip plays (teaser and body), short gaps bridged.

        Frames are sampled and tracked over these rather than ``[start, end)``,
        which for a story clip spans everything between its pieces.
        """
        spans = sorted(self.body_spans + ([(self.hook.start, self.hook.end)] if self.hook else []))
        windows = [list(spans[0])]
        for start, end in spans[1:]:
            if start - windows[-1][1] < WINDOW_BRIDGE_SECONDS:
                windows[-1][1] = max(windows[-1][1], end)
            else:
                windows.append([start, end])
        return [(start, end) for start, end in windows]


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
    # Per aspect ratio: (start, end, seam) wherever two people are stacked, in
    # the rendered file's own seconds, with the seam as a share of its height.
    seams: dict[str, list[tuple[float, float, float]]] = field(default_factory=dict)
    # Per aspect ratio, every stretch of the rendered file: its layout kind, the
    # share of the height its top cell takes, and where faces are in the output
    # (normalised boxes), so graphics added later never cover anyone.
    frames: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
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
        cuts = await asyncio.to_thread(shot_cuts, _decode_frames(frames))
        faded = await asyncio.to_thread(presence_cuts, _decode_frames(frames), faces_per_frame)
        cuts += [c for c in faded if all(abs(c - other) > SAMPLE_INTERVAL_SECONDS * 1.5 for other in cuts)]
        cuts = [await self._refine_cut(request, cut) for cut in sorted(cuts)]
        # A jump between windows is a cut, so the crop never glides across it.
        cuts = sorted(set(cuts) | {start for start, _ in request.windows[1:]})
        tracks = build_tracks(_decode_frames(frames), faces_per_frame, cuts)
        regions_at = _region_finder(frames)
        tracks = _people_only(request, tracks, cuts, regions_at)
        for track in tracks:
            log.info(
                "[TRACK] clip=%s id=%d samples=%d seen=%.2fs-%.2fs mean_area=%.4f mean_motion=%.2f",
                request.clip_id, track.track_id, len(track.samples), track.first_seen,
                track.last_seen, track.mean_area,
                sum(s.mouth_motion for s in track.samples) / len(track.samples),
            )
        layout = self._classify_layout(tracks, request.content_category)
        timestamps = _tracking_timestamps(request)
        # cover_subjects needs the speaker too: it falls back to them whenever
        # the group is too wide for the crop.
        speakers = (
            speaker_timeline(timestamps, tracks, request.transcript_segments)
            if self._strategy_for(layout) != "center"
            else [None] * len(timestamps)
        )
        _log_speaker_switches(request.clip_id, timestamps, speakers)
        turns = speaker_turns(timestamps, speakers)

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

        if cuts:
            log.info("[SHOTS] clip=%s cuts=%s", request.clip_id, ",".join(f"{c:.1f}" for c in cuts))
        for aspect_ratio in request.aspect_ratios:
            tracking = self._build_tracking(
                request=request,
                tracks=tracks,
                timestamps=timestamps,
                speakers=speakers,
                layout=layout,
                aspect_ratio=aspect_ratio,
                source_width=source_width,
                source_height=source_height,
                cuts=cuts,
            )
            result.crop_tracking[aspect_ratio] = [point.copy() for point in tracking]
            output_path = self._output_path(request, aspect_ratio)
            shots = _plan_shots(
                request, layout, tracks, cuts, turns, aspect_ratio, source_width, source_height, regions_at,
            )
            result.layout = next((frame.kind for _, frame in shots if frame.composite), result.layout)
            result.seams[aspect_ratio] = _stack_seams(shots)
            result.frames[aspect_ratio] = _layout_frames(shots, tracks, source_width, source_height, aspect_ratio)
            log.info("[LAYOUT] clip=%s ratio=%s hint=%s detected=%s used=%s beats=%d",
                     request.clip_id, aspect_ratio, request.layout_hint, layout,
                     " ".join(f"{part.start:.1f}-{part.end:.1f}:{frame.kind}" for part, frame in shots),
                     len(request.beats))
            try:
                await self._render(
                    request=request,
                    output_path=output_path,
                    tracking=tracking,
                    aspect_ratio=aspect_ratio,
                    source_width=source_width,
                    source_height=source_height,
                    shots=shots,
                    listener_at=_listener_finder(tracks, timestamps, speakers),
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

    async def _sample_frames(self, request: CutRequest) -> list[tuple[float, bytes]]:
        """Evenly spaced JPEG frames from the clip's windows, one FFmpeg pass each.

        One process per window rather than one per frame. Frames stay
        compressed (tens of KB each) and are decoded one at a time where used,
        so a long clip at the lip-motion sample rate does not hold hundreds of
        raw frames in memory.
        """
        fps = 1.0 / SAMPLE_INTERVAL_SECONDS
        frames: list[tuple[float, bytes]] = []
        for start, end in request.windows:
            frames.extend(await self._sample_window(request, start, end - start, fps))

        log.info(
            "[FRAMES] clip=%s sampled=%d fps=%.2f width=%d",
            request.clip_id, len(frames), fps, DETECT_WIDTH,
        )
        if not frames:
            log.warning("[FRAMES] clip=%s produced no decodable frames; face detection skipped", request.clip_id)
        return frames

    async def _sample_window(
        self, request: CutRequest, start: float, duration: float, fps: float,
    ) -> list[tuple[float, bytes]]:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{start:.3f}",
            "-i", request.source_path,
            "-t", f"{duration:.3f}",
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

        return [(start + index / fps, payload) for index, payload in enumerate(_split_mjpeg(stdout))]

    async def _refine_cut(self, request: CutRequest, cut: float) -> float:
        """``cut``, stamped at the first sample of the new shot, moved to the
        frame where the picture actually changes."""
        start = max(0.0, cut - SAMPLE_INTERVAL_SECONDS)
        width, height = THUMBNAIL_SIZE
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{start:.3f}", "-i", request.source_path, "-t", f"{cut - start + 0.05:.3f}",
            "-vf", f"fps={CUT_REFINE_FPS},scale={width}:{height},format=gray",
            "-an", "-f", "rawvideo", "pipe:1",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        count = len(stdout) // (width * height)
        if proc.returncode != 0 or count < 2:
            return cut
        frames = np.frombuffer(stdout[:count * width * height], np.uint8).reshape(count, height, width).astype(np.float32)
        jump = max(range(1, count), key=lambda i: picture_difference(frames[i - 1], frames[i]))
        return round(start + jump / CUT_REFINE_FPS, 3)

    def _detect_faces(self, clip_id: str, frames: list[tuple[float, bytes]]) -> list[list[Face]]:
        started = time.monotonic()
        faces_per_frame, backend = self._faces.detect_clip(
            lambda: (frame for _, frame in _decode_frames(frames))
        )

        all_faces = [face for faces in faces_per_frame for face in faces]
        frames_with_faces = sum(1 for faces in faces_per_frame if faces)
        log.info(
            "[FACES] clip=%s backend=%s frames=%d with_faces=%d (%d%%) total_faces=%d max_per_frame=%d "
            "avg_confidence=%.2f elapsed=%.2fs",
            clip_id, backend, len(frames), frames_with_faces, frames_with_faces * 100 // max(1, len(frames)), len(all_faces),
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
        timestamps: list[float],
        speakers: list[SpeakerTrack | None],
        layout: str,
        aspect_ratio: str,
        source_width: int,
        source_height: int,
        cuts: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Per-frame crop windows, smoothed within each shot, in source-video timestamps."""
        crop_w, crop_h = target_crop_size(source_width, source_height, aspect_ratio)
        # A crop that already covers the frame cannot pan, so emit one static point.
        if crop_w >= source_width and crop_h >= source_height:
            return [{
                "timestamp": round(request.start, 3),
                "bbox": Box(0.0, 0.0, 1.0, 1.0).as_dict(),
                "strategy": "no_change",
            }]

        strategy = self._strategy_for(layout)
        count = len(timestamps)
        step = 1.0 / TRACKING_FPS
        targets = [
            self._target_center(
                ts, tracks, speaker, strategy, source_width, source_height, aspect_ratio
            )
            for ts, speaker in zip(timestamps, speakers)
        ]
        centred = sum(1 for target in targets if target is None)
        raw = [target or (0.5, 0.5) for target in targets]
        log.info(
            "[CROP] clip=%s ratio=%s strategy=%s crop=%dx%d points=%d subject_framed=%d (%d%%) centred=%d",
            request.clip_id, aspect_ratio, strategy, crop_w, crop_h, count, count - centred,
            (count - centred) * 100 // max(1, count), centred,
        )

        # Smoothed shot by shot: a camera cut is a cut in the crop too, never a
        # slow glide from where the last shot's subject was. So is a switch to
        # a speaker out of frame.
        switches = _switch_cuts(timestamps, speakers, raw, crop_w / source_width)
        boundaries = sorted(set(cuts or []) | set(switches))
        points: list[dict[str, Any]] = []
        for low, high in _shot_ranges(timestamps, boundaries):
            xs = _smooth_series([point[0] for point in raw[low:high]], step)
            ys = _smooth_series([point[1] for point in raw[low:high]], step)
            if points:
                # The crop moves on the cut's own frame, not at the next tracking point.
                cut = min(c for c in boundaries if timestamps[low - 1] < c <= timestamps[low])
                points.append({**points[-1], "timestamp": round(cut - CUT_HOLD_SECONDS, 3)})
                if cut < timestamps[low]:
                    points.append({
                        "timestamp": round(cut, 3),
                        "bbox": crop_around(xs[0], ys[0], source_width, source_height, aspect_ratio).as_dict(),
                        "strategy": strategy,
                    })
            points.extend(
                {
                    "timestamp": round(ts, 3),
                    "bbox": crop_around(x, y, source_width, source_height, aspect_ratio).as_dict(),
                    "strategy": strategy,
                }
                for ts, x, y in zip(timestamps[low:high], xs, ys)
            )
        return points

    def _target_center(
        self,
        timestamp: float,
        tracks: list[SpeakerTrack],
        speaker: SpeakerTrack | None,
        strategy: str,
        source_width: int,
        source_height: int,
        aspect_ratio: str,
    ) -> tuple[float, float] | None:
        """Where to centre the crop, or ``None`` when no subject is available."""
        if strategy == "center" or not tracks:
            return None

        if strategy == "cover_subjects":
            boxes = [b for b in (t.box_at(timestamp) for t in visible_tracks(timestamp, tracks)) if b is not None]
            group = union_box(boxes)
            crop_w, crop_h = target_crop_size(source_width, source_height, aspect_ratio)
            # Only frame the group when it fits. A panel spread across a wide
            # stage does not, and centring on its middle framed empty stage
            # for the whole clip; follow whoever is talking instead.
            if group is not None and group.width <= crop_w / source_width and group.height <= crop_h / source_height:
                return crop_covering(boxes, source_width, source_height, aspect_ratio).center

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
        shots: list[tuple[Part, Layout]],
        listener_at: Any = None,
    ) -> None:
        from video_processor.ffmpeg_service import FFmpegService

        ffmpeg = FFmpegService()
        target_width, target_height = output_dimensions(aspect_ratio)
        crop_w, crop_h = target_crop_size(source_width, source_height, aspect_ratio)
        # Beats reframe inside the crop, so they need a crop smaller than the frame.
        can_reframe = crop_w < source_width or crop_h < source_height

        async def render_part(part: Part, frame: Layout, path: Path) -> None:
            if frame.kind in ("fit", "content"):
                await ffmpeg.render_fit(
                    request.source_path, str(path), part.start, part.end - part.start,
                    target_width, target_height, source_width,
                    box=frame.content.as_dict() if frame.content else None, source_height=source_height,
                    bubble=frame.bubble.as_dict() if frame.bubble else None,
                )
                return
            if frame.composite:
                await ffmpeg.render_stack(
                    request.source_path, str(path), part.start, part.end - part.start,
                    [(cell.box.as_dict(), cell.height, cell.fit) for cell in frame.cells],
                    target_width, source_width, source_height,
                )
                return
            part_tracking = _tracking_from(tracking, part.start)
            if part.hold is not None:
                part_tracking = [{
                    "timestamp": part.start,
                    "bbox": crop_around(part.hold[0], part.hold[1], source_width, source_height, aspect_ratio).as_dict(),
                }]
            await ffmpeg.crop_with_tracking(
                input_path=request.source_path,
                output_path=str(path),
                start_time=part.start,
                duration=part.end - part.start,
                crop_tracking=part_tracking,
                target_width=target_width,
                target_height=target_height,
                source_width=source_width,
                source_height=source_height,
                zoom=part.zoom,
                ease=part.ease,
            )

        sentence_starts = [
            float(segment.get("start", 0.0)) for segment in request.transcript_segments
            if str(segment.get("text", "")).strip()
        ]
        parts: list[tuple[Part, Layout]] = []
        for shot, frame in shots:
            if can_reframe and frame.kind == "follow":
                parts.extend(
                    (part, frame)
                    for part in plan_parts(shot.start, shot.end, request.beats,
                                           listener_at or (lambda _t: None), sentence_starts)
                )
            else:
                parts.append((shot, frame))

        if len(parts) == 1:
            await render_part(*parts[0], output_path)
        else:
            # Every part goes through the same encoder settings, so they join by
            # stream copy and the clip is never encoded a second time.
            part_paths = [output_path.with_suffix(f".part{index}.mp4") for index in range(len(parts))]
            try:
                for (part, frame), path in zip(parts, part_paths):
                    await render_part(part, frame, path)
                await ffmpeg.concat_segments([str(path) for path in part_paths], str(output_path))
            finally:
                for path in part_paths:
                    path.unlink(missing_ok=True)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise CustomException(
                message=f"Render produced an empty file for {aspect_ratio}",
                code="CLIP_RENDER_EMPTY",
                status_code=500,
            )


def _plan_shots(
    request: CutRequest,
    detected: str,
    tracks: list[SpeakerTrack],
    cuts: list[float],
    turns: list[Turn],
    aspect_ratio: str,
    source_width: int,
    source_height: int,
    regions_at: Any = None,
) -> list[tuple[Part, Layout]]:
    """The clip in play order (hook first), one entry per run of shots sharing a layout.

    Each shot is framed from the people in that shot alone, and split further
    where two of them trade replies (see :func:`framing_stretches`).
    Neighbouring stretches that both follow the speaker, or both show the frame
    whole, render as one part: the tracked crop already cuts cleanly at shot
    boundaries, and fewer parts mean fewer encoder runs.
    """
    output_size = output_dimensions(aspect_ratio)
    spans = ([(request.hook.start, request.hook.end)] if request.hook else []) + request.body_spans
    shots: list[tuple[Part, Layout]] = []
    for span_start, span_end in spans:
        joinable = False  # Never join across spans: they are separate stretches of source.
        for shot_start, shot_end in shot_windows(span_start, span_end, cuts):
            present = tracks_in_shot(tracks, shot_start, shot_end, SAMPLE_INTERVAL_SECONDS)
            focus = _shot_focus(request, shot_start, shot_end, present, regions_at)
            # A shot about something on screen is one stretch: its layout does
            # not change with who is talking.
            stretches = [(shot_start, shot_end, [])] if focus.shows_content else framing_stretches(
                shot_start, shot_end, turns, SAMPLE_INTERVAL_SECONDS, request.transcript_segments, present=present,
            )
            for start, end, pair in stretches:
                frame = choose_layout(
                    request.layout_hint, detected, tracks_in_shot(tracks, start, end, SAMPLE_INTERVAL_SECONDS),
                    aspect_ratio, source_width, source_height, *output_size, pair=pair, focus=focus,
                )
                if joinable and _joins(shots[-1][1], frame):
                    shots[-1] = (Part(shots[-1][0].start, end), frame)
                else:
                    shots.append((Part(start, end), frame))
                joinable = True
    return shots


def _joins(previous: Layout, frame: Layout) -> bool:
    """Whether two neighbouring stretches render as one part."""
    return (not frame.composite and previous.kind == frame.kind and previous.content == frame.content
            and previous.bubble == frame.bubble)


def _shot_focus(
    request: CutRequest, start: float, end: float, present: list[SpeakerTrack], regions_at: Any,
) -> Focus:
    """What the shot ``start``..``end`` is about; people unless something on screen clearly is."""
    if regions_at is None:
        return PEOPLE
    regions = regions_at(start, end)
    if not regions:
        return PEOPLE
    focus = decide_focus(
        regions, person_tracks(present, regions), start, hint=request.layout_hint,
        category=request.content_category, spoken=_spoken(request.transcript_segments, start, end),
    )
    if focus.shows_content:
        log.info("[FOCUS] clip=%s %.1f-%.1f %s box=%s", request.clip_id, start, end, focus.kind,
                 focus.content.box.as_dict())
    return focus


def _spoken(segments: list[dict[str, Any]], start: float, end: float) -> str:
    return " ".join(
        str(segment.get("text", "")) for segment in segments
        if float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
    )


def _region_finder(frames: list[tuple[float, bytes]]):
    """``(start, end) -> content regions`` over the sampled frames in that range, computed once each."""
    cache: dict[tuple[float, float], list[Region]] = {}

    def regions_at(start: float, end: float) -> list[Region]:
        key = (round(start, 3), round(end, 3))
        if key not in cache:
            picked = [frame for frame in frames if start <= frame[0] < end][::REGION_SAMPLE_STEP]
            cache[key] = content_regions(list(_decode_frames(picked)))
        return cache[key]

    return regions_at


def _people_only(
    request: CutRequest, tracks: list[SpeakerTrack], cuts: list[float], regions_at: Any,
) -> list[SpeakerTrack]:
    """``tracks`` without faces that belong to content: one that is part of a
    picture in every shot it appears in is never framed as a speaker."""
    depicted: dict[int, bool] = {}
    for window_start, window_end in request.windows:
        for start, end in shot_windows(window_start, window_end, cuts):
            present = tracks_in_shot(tracks, start, end, SAMPLE_INTERVAL_SECONDS)
            people = {track.track_id for track in person_tracks(present, regions_at(start, end))}
            for track in present:
                depicted[track.track_id] = depicted.get(track.track_id, True) and track.track_id not in people
    dropped = [track.track_id for track in tracks if depicted.get(track.track_id)]
    if dropped:
        log.info("[FACES] clip=%s faces in content, not framed: %s", request.clip_id, dropped)
    return [track for track in tracks if not depicted.get(track.track_id)]


def _stack_seams(shots: list[tuple[Part, Layout]]) -> list[tuple[float, float, float]]:
    """Where the frame is two stacked pictures (two people, or shown content
    over its audience), on the rendered file's timeline: the shots play back
    to back, so each starts where the last one ended. Captions sit on the seam."""
    seams: list[tuple[float, float, float]] = []
    cursor = 0.0
    for part, frame in shots:
        length = part.end - part.start
        if frame.kind in STACKED_KINDS:
            seam = frame.cells[0].height / sum(cell.height for cell in frame.cells)
            seams.append((round(cursor, 3), round(cursor + length, 3), round(seam, 4)))
        cursor += length
    return seams


def _layout_frames(
    shots: list[tuple[Part, Layout]], tracks: list[SpeakerTrack], source_width: int, source_height: int,
    aspect_ratio: str,
) -> list[dict[str, Any]]:
    """Each stretch's layout on the rendered file's timeline: its kind, the
    share of the height its top cell takes (0 for one picture), and the
    people's faces as normalised boxes of the output."""
    frames: list[dict[str, Any]] = []
    cursor = 0.0
    for part, frame in shots:
        length = part.end - part.start
        top = frame.cells[0].height / sum(cell.height for cell in frame.cells) if frame.cells else 0.0
        people = tracks_in_shot(tracks, part.start, part.end, SAMPLE_INTERVAL_SECONDS)
        faces = _faces_on_output(frame, [typical_box(track) for track in people], source_width, source_height,
                                 aspect_ratio)
        frames.append({
            "start": round(cursor, 3), "end": round(cursor + length, 3), "kind": frame.kind, "top": round(top, 4),
            "faces": [[round(v, 4) for v in (b.x, b.y, b.width, b.height)] for b in faces],
        })
        cursor += length
    return frames


def _faces_on_output(
    frame: Layout, faces: list[Box], source_width: int, source_height: int, aspect_ratio: str,
) -> list[Box]:
    """Where ``faces`` (source boxes) appear in the output frame for ``frame``'s layout."""
    if frame.kind == "content":
        if frame.bubble is None:
            return []
        out_w, out_h = output_dimensions(aspect_ratio)
        content = frame.content or Box()
        width_px, height_px = content.width * source_width, content.height * source_height
        fitted = int(height_px * min(out_w / width_px, out_h / height_px)) // 2 * 2
        _, x, y, diameter = bubble_layout(out_w, out_h, fitted)
        return [Box(x / out_w, y / out_h, diameter / out_w, diameter / out_h)]
    if frame.cells:
        total = sum(cell.height for cell in frame.cells)
        placed, offset = [], 0.0
        for cell in frame.cells:
            share = cell.height / total
            if not cell.fit:
                placed += [_through(face, cell.box, offset, share) for face in faces if _centred_in(face, cell.box)]
            offset += share
        return placed
    out_w, out_h = output_dimensions(aspect_ratio)
    if frame.kind == "fit":
        share = min(1.0, source_height * out_w / source_width / out_h)
        return [_through(face, Box(), (1 - share) / 2, share) for face in faces]
    if not faces:
        return []
    # A followed shot is centred on its speaker, lifted by the headroom bias.
    lead = max(faces, key=lambda face: face.area)
    window = crop_around(lead.center[0], max(0.0, lead.center[1] - VERTICAL_BIAS), source_width, source_height,
                         aspect_ratio)
    return [_through(face, window, 0.0, 1.0) for face in faces if _centred_in(face, window)]


def _centred_in(face: Box, window: Box) -> bool:
    cx, cy = face.center
    return window.x <= cx <= window.x + window.width and window.y <= cy <= window.y + window.height


def _through(face: Box, window: Box, offset: float, share: float) -> Box:
    """``face`` seen through ``window``, drawn into the band ``offset``..``offset + share`` of the output."""
    return Box(
        (face.x - window.x) / window.width,
        offset + (face.y - window.y) / window.height * share,
        face.width / window.width,
        face.height / window.height * share,
    )


def _switch_cuts(
    timestamps: list[float],
    speakers: list[SpeakerTrack | None],
    targets: list[tuple[float, float]],
    crop_width: float,
) -> list[float]:
    """Times the framed speaker changes to someone outside the current crop."""
    return [
        timestamps[i] for i in range(1, len(timestamps))
        if speakers[i] is not speakers[i - 1] and None not in (speakers[i], speakers[i - 1])
        and abs(targets[i][0] - targets[i - 1][0]) > crop_width * SWITCH_CUT_DISTANCE
    ]


def _shot_ranges(timestamps: list[float], cuts: list[float]) -> list[tuple[int, int]]:
    """Index ranges of ``timestamps`` falling within each shot."""
    ranges: list[tuple[int, int]] = []
    low = 0
    for cut in sorted(cuts):
        high = next((i for i in range(low, len(timestamps)) if timestamps[i] >= cut), len(timestamps))
        if high > low:
            ranges.append((low, high))
            low = high
    if low < len(timestamps):
        ranges.append((low, len(timestamps)))
    return ranges


def _listener_finder(
    tracks: list[SpeakerTrack], timestamps: list[float], speakers: list[SpeakerTrack | None],
):
    """``t -> centre`` of the most visible person who is not speaking at ``t``."""
    def listener_at(t: float) -> tuple[float, float] | None:
        if len(tracks) < 2 or not timestamps:
            return None
        index = min(range(len(timestamps)), key=lambda i: abs(timestamps[i] - t))
        speaker = speakers[index] if index < len(speakers) else None
        others = [track for track in visible_tracks(t, tracks) if track is not speaker]
        if not others:
            return None
        box = max(others, key=lambda track: track.mean_area).box_at(t)
        if box is None:
            return None
        return box.center[0], max(0.0, box.center[1] - VERTICAL_BIAS)

    return listener_at


def _tracking_timestamps(request: CutRequest) -> list[float]:
    """Source-video times at which a crop window is computed, across the clip's windows."""
    timestamps: list[float] = []
    for start, end in request.windows:
        count = max(2, int((end - start) * TRACKING_FPS))
        step = (end - start) / (count - 1)
        timestamps.extend(start + index * step for index in range(count))
    return timestamps


def _tracking_from(tracking: list[dict[str, Any]], start: float) -> list[dict[str, Any]]:
    """Tracking for a render starting at ``start``, keeping the point in effect then.

    The renderer clamps earlier points to its first frame, so passing them all
    would pin the opening crop to wherever the clip itself began.
    """
    earlier = [point for point in tracking if point["timestamp"] <= start]
    return earlier[-1:] + [point for point in tracking if point["timestamp"] > start]


def _decode_frames(frames: list[tuple[float, bytes]]) -> Iterator[tuple[float, np.ndarray]]:
    """Decode JPEG frames one at a time, substituting a blank for a corrupt one
    so timestamps stay aligned with the detections made from the same list."""
    for timestamp, payload in frames:
        frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        yield timestamp, frame if frame is not None else np.zeros((1, 1, 3), dtype=np.uint8)


def _log_speaker_switches(
    clip_id: str, timestamps: list[float], speakers: list[SpeakerTrack | None]
) -> None:
    """One line per change of framed speaker, to debug tracking from logs."""
    previous: SpeakerTrack | None = None
    switches = []
    for timestamp, speaker in zip(timestamps, speakers):
        if speaker is not previous and speaker is not None:
            switches.append(f"{timestamp:.1f}s->#{speaker.track_id}")
        previous = speaker
    if switches:
        log.info("[SPEAKER] clip=%s %s", clip_id, " ".join(switches))


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
