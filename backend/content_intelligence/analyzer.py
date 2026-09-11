from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from core.logging_config import get_logger
from video_processor.ffmpeg_service import FFmpegService

log = get_logger(__name__)


class FrameAnalyzer:
    def __init__(self, vision_client: Any | None = None, ffmpeg: FFmpegService | None = None) -> None:
        self._vision = vision_client
        self._ffmpeg = ffmpeg or FFmpegService()

    async def analyze(self, video_path: str, content_category: str, max_frames: int = 30) -> dict:
        duration = await self._ffmpeg.probe_duration(video_path)
        frame_interval = max(5.0, duration / max_frames) if duration > 0 else 5.0
        timestamps = [i * frame_interval for i in range(max_frames) if i * frame_interval < duration]
        frame_analyses = await self.analyze_frames(video_path, timestamps, content_category)

        descriptions = {
            f"{item['timestamp']:.2f}": item.get("description", "")
            for item in frame_analyses
            if item.get("description")
        }
        scene_changes = self._detect_scene_changes(list(descriptions.items())) if len(descriptions) > 1 else []
        return {
            "descriptions": descriptions,
            "scene_changes": scene_changes,
            "frame_interval_seconds": round(frame_interval, 2),
            "content_category": content_category,
            "frames": frame_analyses,
        }

    async def analyze_frames(
        self,
        video_path: str,
        timestamps: list[float],
        content_category: str,
    ) -> list[dict[str, Any]]:
        video_info = await self._ffmpeg.get_video_info(video_path)
        streams = video_info.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type") == "video"), streams[0] if streams else {})
        source_width = int(stream.get("width", 0))
        source_height = int(stream.get("height", 0))
        results: list[dict[str, Any]] = []
        for timestamp in timestamps:
            try:
                results.append(await self._analyze_frame(video_path, timestamp, source_width, source_height, content_category))
            except Exception as exc:
                log.debug(f"Frame analysis failed at {timestamp}: {exc}")
                results.append(self._fallback_frame(timestamp, source_width, source_height, content_category, str(exc)))
        return results

    async def detect_bounding_boxes(
        self,
        video_path: str,
        timestamps: list[float],
        content_category: str,
    ) -> list[dict[str, Any]]:
        frames = await self.analyze_frames(video_path, timestamps, content_category)
        return [
            {
                "timestamp": frame["timestamp"],
                "frame_width": frame["frame_width"],
                "frame_height": frame["frame_height"],
                "subjects": frame.get("subjects", []),
                "objects": frame.get("objects", []),
            }
            for frame in frames
        ]

    async def analyze_candidate_clips(
        self,
        video_path: str,
        clips: list[dict[str, Any]],
        max_frames_per_clip: int = 8,
        frame_interval: float = 2.0,
    ) -> dict[str, list[dict[str, Any]]]:
        analyzed: dict[str, list[dict[str, Any]]] = {}
        for clip in clips:
            clip_id = str(clip.get("clip_id") or clip.get("id") or f"clip_{len(analyzed) + 1:03d}")
            start = float(clip.get("start_time", clip.get("start", 0.0)))
            end = float(clip.get("end_time", clip.get("end", start)))
            count = max(2, min(max_frames_per_clip, int((end - start) / frame_interval) + 1))
            timestamps = [start + index * (end - start) / max(1, count - 1) for index in range(count)]
            timestamps = [round(timestamp, 3) for timestamp in timestamps]
            analyzed[clip_id] = await self.analyze_frames(video_path, timestamps, str(clip.get("content_category", "unknown")))
        return analyzed

    async def _analyze_frame(
        self,
        video_path: str,
        timestamp: float,
        source_width: int,
        source_height: int,
        content_category: str,
    ) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmpdir:
            frame_path = os.path.join(tmpdir, "frame.jpg")
            await self._ffmpeg.extract_frame(video_path, timestamp, frame_path)
            if not os.path.exists(frame_path):
                return self._fallback_frame(timestamp, source_width, source_height, content_category, "Frame was not created")
            image_bytes = Path(frame_path).read_bytes()

        if not self._vision:
            return self._fallback_frame(timestamp, source_width, source_height, content_category, "Vision client is not configured")

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Analyze this video frame and return only valid JSON. Include normalized bounding boxes in the range 0..1 "
            "and pixel bounding boxes when possible. Identify the main speaker, people, faces, body position, important "
            "objects, on-screen text or logos, scene, camera shot, visual quality, and whether the main subject can be "
            "kept in a vertical crop. Use this schema: "
            "{"
            '"description":"short description",'
            '"subjects":[{"label":"subject label","confidence":0.0,"is_speaker":false,"speaker":"optional speaker name","role":"optional role","bounding_box":{"x":0.0,"y":0.0,"width":0.0,"height":0.0},"pixel_bounding_box":{"x":0,"y":0,"width":0,"height":0}}],'
            '"faces":[{"label":"face","confidence":0.0,"bounding_box":{"x":0.0,"y":0.0,"width":0.0,"height":0.0}}],'
            '"important_objects":[{"label":"object","confidence":0.0,"bounding_box":{"x":0.0,"y":0.0,"width":0.0,"height":0.0}}],'
            '"on_screen_text":[],"scene":"scene","camera_shot":"shot","visual_quality":{"score":0.0,"issues":[]},'
            '"main_subject_position":{"x":0.0,"y":0.0,"width":0.0,"height":0.0},"suitable_for_vertical_crop":true'
            "}"
        )
        try:
            response = await self._vision.chat([
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ], temperature=0.1, max_tokens=1200)
            data = self._parse_json(response)
            width = int(data.get("frame_width") or source_width)
            height = int(data.get("frame_height") or source_height)
            subjects = self._normalize_subjects(data.get("subjects", []), width, height)
            objects = self._normalize_subjects(data.get("important_objects") or data.get("objects", []), width, height)
            faces = self._normalize_subjects(data.get("faces", []), width, height)
            main_box = (
                data.get("main_subject_position")
                or data.get("subject_position")
                or (subjects[0].get("bounding_box") if subjects else None)
            )
            return {
                "timestamp": round(float(timestamp), 3),
                "frame_width": width,
                "frame_height": height,
                "description": str(data.get("description", "")).strip(),
                "subjects": subjects,
                "faces": faces,
                "objects": objects,
                "on_screen_text": data.get("on_screen_text", []),
                "scene": data.get("scene", ""),
                "camera_shot": data.get("camera_shot", ""),
                "body_position": data.get("body_position", ""),
                "speaker": data.get("speaker"),
                "visual_quality": data.get("visual_quality", {"score": 0.0, "issues": []}),
                "text_logos": data.get("text_logos", data.get("on_screen_text", [])),
                "main_subject_position": self._normalize_box(main_box, width, height) if main_box else None,
                "suitable_for_vertical_crop": bool(data.get("suitable_for_vertical_crop", True)),
                "content_category": content_category,
            }
        except Exception as exc:
            log.debug(f"Vision analysis failed at {timestamp}: {exc}")
            return self._fallback_frame(timestamp, source_width, source_height, content_category, str(exc))

    async def _describe_frame(self, video_path: str, timestamp: float) -> str:
        frame = await self._analyze_frame(video_path, timestamp, 0, 0, "unknown")
        return frame.get("description", "")

    @staticmethod
    def _normalize_box(box: dict[str, Any] | None, frame_width: int, frame_height: int) -> dict[str, float] | None:
        if not box:
            return None
        x = float(box.get("x", 0.0))
        y = float(box.get("y", 0.0))
        width = float(box.get("width", 0.0))
        height = float(box.get("height", 0.0))
        if frame_width and max(x, width) > 1.0:
            x /= frame_width
            width /= frame_width
        if frame_height and max(y, height) > 1.0:
            y /= frame_height
            height /= frame_height
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        width = min(1.0 - x, max(0.0, width))
        height = min(1.0 - y, max(0.0, height))
        return {"x": round(x, 6), "y": round(y, 6), "width": round(width, 6), "height": round(height, 6)}

    @classmethod
    def _normalize_subjects(cls, subjects: list[dict[str, Any]], frame_width: int, frame_height: int) -> list[dict[str, Any]]:
        normalized = []
        for subject in subjects:
            item = dict(subject)
            box = cls._normalize_box(subject.get("bounding_box") or subject.get("bbox"), frame_width, frame_height)
            pixel_box = subject.get("pixel_bounding_box") or box
            if box:
                item["bounding_box"] = box
            if pixel_box:
                item["pixel_bounding_box"] = pixel_box
            normalized.append(item)
        return normalized

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _fallback_frame(timestamp: float, width: int, height: int, category: str, error: str) -> dict[str, Any]:
        return {
            "timestamp": round(float(timestamp), 3),
            "frame_width": width,
            "frame_height": height,
            "description": "",
            "subjects": [],
            "faces": [],
            "objects": [],
            "on_screen_text": [],
            "scene": "",
            "camera_shot": "",
            "body_position": "",
            "speaker": None,
            "visual_quality": {"score": 0.0, "issues": [error]},
            "text_logos": [],
            "main_subject_position": None,
            "suitable_for_vertical_crop": True,
            "content_category": category,
        }

    def _detect_scene_changes(self, frame_items: list[tuple[str, str]], threshold: float = 0.5) -> list[float]:
        changes = []
        for i in range(1, len(frame_items)):
            prev_words = set(frame_items[i - 1][1].lower().split())
            curr_words = set(frame_items[i][1].lower().split())
            if not prev_words or not curr_words:
                continue
            overlap = len(prev_words & curr_words) / len(prev_words | curr_words)
            if overlap < (1.0 - threshold):
                changes.append(round(float(frame_items[i][0]), 2))
        return changes
