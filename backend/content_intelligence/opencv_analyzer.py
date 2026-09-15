from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from core.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class OpenCVFrame:
    timestamp: float
    frame: np.ndarray
    width: int = 0
    height: int = 0
    gray: np.ndarray | None = None
    hist: np.ndarray | None = None


@dataclass
class OpenCVScene:
    start: float
    end: float
    frames: list[OpenCVFrame] = field(default_factory=list)


class OpenCVAnalyzer:
    def __init__(
        self,
        scene_threshold: float = 0.4,
        max_frames: int = 30,
        frame_interval: float | None = None,
    ) -> None:
        self._scene_threshold = scene_threshold
        self._max_frames = max_frames
        self._frame_interval = frame_interval

    async def extract_frames(self, video_path: str, duration: float) -> list[OpenCVFrame]:
        if duration <= 0:
            log.warning("[OPENCV] [EXTRACT SKIP] invalid duration=%.3fs video=%s", duration, video_path)
            return []
        interval = self._frame_interval or max(2.0, duration / self._max_frames)
        timestamps = [i * interval for i in range(self._max_frames) if i * interval < duration]
        log.info(
            "[OPENCV] [EXTRACT START] video=%s duration=%.3fs frames=%d interval=%.3fs",
            video_path,
            duration,
            len(timestamps),
            interval,
        )
        frames = await asyncio.to_thread(self._extract_frames_sync, video_path, timestamps)
        log.info("[OPENCV] [EXTRACT COMPLETE] video=%s extracted=%d", video_path, len(frames))
        return frames

    def detect_scenes(self, frames: list[OpenCVFrame]) -> list[float]:
        if len(frames) < 2:
            return []
        log.info("[OPENCV] [SCENES START] frames=%d threshold=%.3f", len(frames), self._scene_threshold)
        changes: list[float] = []
        prev_hist = frames[0].hist
        if prev_hist is None:
            return []
        for i in range(1, len(frames)):
            curr_hist = frames[i].hist
            if curr_hist is None:
                continue
            corr = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
            if corr < (1.0 - self._scene_threshold):
                changes.append(round(frames[i].timestamp, 3))
            prev_hist = curr_hist
        log.info("[OPENCV] [SCENES COMPLETE] changes=%d", len(changes))
        return changes

    def compute_motion_map(self, frames: list[OpenCVFrame]) -> dict[float, dict[str, float]]:
        log.info("[OPENCV] [MOTION START] frames=%d", len(frames))
        motion: dict[float, dict[str, float]] = {}
        for i in range(1, len(frames)):
            prev = frames[i - 1]
            curr = frames[i]
            if prev.gray is None or curr.gray is None:
                continue
            diff = cv2.absdiff(prev.gray, curr.gray)
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            motion_pixels = int(np.count_nonzero(thresh))
            total_pixels = thresh.shape[0] * thresh.shape[1]
            motion_ratio = min(1.0, motion_pixels / max(1, total_pixels))
            motion[curr.timestamp] = {
                "motion_ratio": round(motion_ratio, 4),
                "motion_pixels": motion_pixels,
                "total_pixels": total_pixels,
            }
        log.info("[OPENCV] [MOTION COMPLETE] samples=%d", len(motion))
        return motion

    def compute_saliency(self, frame: OpenCVFrame) -> dict[str, float] | None:
        if frame.frame is None or frame.frame.size == 0:
            return None
        try:
            saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
            _, saliency_map = saliency.computeSaliency(frame.frame)
            saliency_map = (saliency_map * 255).astype(np.uint8)
            moments = cv2.moments(saliency_map, binaryImage=False)
            if moments["m00"] == 0:
                return None
            cx = float(moments["m10"] / moments["m00"]) / max(1, frame.width)
            cy = float(moments["m01"] / moments["m00"]) / max(1, frame.height)
            _, thresh = cv2.threshold(saliency_map, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            return {
                "x": round(x / max(1, frame.width), 6),
                "y": round(y / max(1, frame.height), 6),
                "width": round(w / max(1, frame.width), 6),
                "height": round(h / max(1, frame.height), 6),
                "centroid_x": round(min(1.0, max(0.0, cx)), 6),
                "centroid_y": round(min(1.0, max(0.0, cy)), 6),
                "saliency_score": round(float(np.mean(saliency_map)) / 255.0, 4),
            }
        except Exception as exc:
            log.debug("Saliency computation failed: %s", exc)
            return None

    def _extract_frames_sync(self, video_path: str, timestamps: list[float]) -> list[OpenCVFrame]:
        log.info("[OPENCV] [EXTRACT OPENED] decoder=ffmpeg software video=%s", video_path)
        frames: list[OpenCVFrame] = []
        for index, ts in enumerate(timestamps, start=1):
            frame = self._decode_frame_with_ffmpeg(video_path, ts)
            if frame is None:
                log.warning("[OPENCV] [FRAME SKIP] index=%d/%d timestamp=%.3fs", index, len(timestamps), ts)
                continue
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            log.info("[OPENCV] [FRAME] index=%d/%d timestamp=%.3fs size=%dx%d", index, len(timestamps), ts, w, h)
            frames.append(OpenCVFrame(
                timestamp=round(ts, 3),
                frame=frame,
                width=w,
                height=h,
                gray=gray,
                hist=hist,
            ))
        return frames

    @staticmethod
    def _decode_frame_with_ffmpeg(video_path: str, timestamp: float) -> np.ndarray | None:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-hwaccel",
            "none",
            "-ss",
            str(timestamp),
            "-i",
            video_path,
            "-an",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-q:v",
            "2",
            "pipe:1",
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            log.error("[OPENCV] FFmpeg frame decode unavailable: %s", exc)
            return None
        if result.returncode != 0 or not result.stdout:
            error = result.stderr.decode("utf-8", errors="ignore").strip().replace("\n", " ")
            log.debug("[OPENCV] FFmpeg frame decode failed at %.3fs: %s", timestamp, error[-300:])
            return None
        frame = cv2.imdecode(np.frombuffer(result.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
        return frame if frame is not None and frame.size else None
