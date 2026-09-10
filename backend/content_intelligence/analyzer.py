from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from core.logging_config import get_logger
from core.exceptions import CustomException
from video_processor.ffmpeg_service import FFmpegService

log = get_logger(__name__)


class FrameAnalyzer:
    def __init__(self, gemini_client: Any) -> None:
        self._gemini = gemini_client
        self._ffmpeg = FFmpegService()

    async def analyze(self, video_path: str, content_category: str, max_frames: int = 30) -> dict:
        duration = await self._ffmpeg.probe_duration(video_path)
        frame_interval = max(5.0, duration / max_frames)
        timestamps = [i * frame_interval for i in range(max_frames) if i * frame_interval < duration]

        descriptions: dict[str, str] = {}
        scene_changes: list[float] = []

        for ts in timestamps:
            try:
                desc = await self._describe_frame(video_path, ts)
                descriptions[f"{ts:.2f}"] = desc
            except Exception as exc:
                log.debug(f"Frame description failed at {ts}: {exc}")

        if len(descriptions) > 1:
            scene_changes = self._detect_scene_changes(list(descriptions.items()))

        return {
            "descriptions": descriptions,
            "scene_changes": scene_changes,
            "frame_interval_seconds": round(frame_interval, 2),
            "content_category": content_category,
        }

    async def _describe_frame(self, video_path: str, timestamp: float) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            frame_path = os.path.join(tmpdir, "frame.jpg")
            await self._ffmpeg.extract_frame(video_path, timestamp, frame_path)

            if not os.path.exists(frame_path):
                return ""

            with open(frame_path, "rb") as f:
                image_bytes = f.read()

        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            response = await self._gemini.chat([
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this frame in 1-2 sentences. Focus on visual content, text on screen, actions, and context."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ], temperature=0.1, max_tokens=150)
            return response.strip()
        except Exception as exc:
            log.debug(f"Gemini vision failed: {exc}")
            return ""

    def _detect_scene_changes(self, frame_items: list[tuple[str, str]], threshold: float = 0.5) -> list[float]:
        changes = []
        for i in range(1, len(frame_items)):
            prev_desc = frame_items[i - 1][1].lower()
            curr_desc = frame_items[i][1].lower()
            prev_words = set(prev_desc.split())
            curr_words = set(curr_desc.split())
            if not prev_words or not curr_words:
                continue
            overlap = len(prev_words & curr_words) / len(prev_words | curr_words)
            if overlap < (1.0 - threshold):
                ts = float(frame_items[i][0])
                changes.append(round(ts, 2))
        return changes
