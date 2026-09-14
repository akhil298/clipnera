from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from core.logging_config import get_logger
from core.exceptions import CustomException
from video_processor.ffmpeg_service import FFmpegService
from depth_captions.schema import (
    VideoNormalizationConfig,
    VideoMetadata,
    TranscriptSegment,
    TranscriptWord,
    PersonTrack,
    PersonTrackPoint,
    BoundingBox,
)

log = get_logger(__name__)


class VideoAnalyzer:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def normalize_video(
        self,
        video_path: str,
        output_dir: Path,
        config: VideoNormalizationConfig | None = None,
    ) -> tuple[str, VideoMetadata]:
        config = config or VideoNormalizationConfig()
        output_path = output_dir / "normalized.mp4"

        info = await self._ffmpeg.get_video_info(video_path)
        streams = info.get("streams") or []
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), streams[0] if streams else {})
        
        rotation = 0
        if "tags" in video_stream and "rotate" in video_stream["tags"]:
            rotation = int(video_stream["tags"]["rotate"])
        
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        vf_parts = [
            f"fps={config.target_fps}",
            f"scale={config.target_width}:{config.target_height}:flags=lanczos",
            f"format={config.pixel_format}",
        ]
        if rotation in (90, 270):
            vf_parts.append("transpose=1")
        elif rotation == 180:
            vf_parts.append("transpose=2,transpose=2")
        
        vf = ",".join(vf_parts)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise CustomException(message=f"Video normalization failed: {err}", code="NORMALIZATION_FAILED", status_code=500)

        metadata = VideoMetadata(
            width=config.target_width,
            height=config.target_height,
            fps=config.target_fps,
            duration=float(info.get("format", {}).get("duration", 0)),
            aspect_ratio=f"{config.target_width}:{config.target_height}",
        )
        
        return str(output_path), metadata

    async def get_video_metadata(self, video_path: str) -> VideoMetadata:
        info = await self._ffmpeg.get_video_info(video_path)
        streams = info.get("streams") or []
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), streams[0] if streams else {})
        
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        fps_str = video_stream.get("r_frame_rate", "30/1")
        num, den = map(int, fps_str.split("/"))
        fps = num / max(1, den)
        duration = float(info.get("format", {}).get("duration", 0))
        
        return VideoMetadata(
            width=width,
            height=height,
            fps=fps,
            duration=duration,
            aspect_ratio=f"{width}:{height}",
        )

    async def extract_proxy_frames(
        self,
        video_path: str,
        output_dir: Path,
        interval: float = 1.0,
        max_frames: int = 100,
    ) -> list[dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        
        info = await self._ffmpeg.get_video_info(video_path)
        duration = float(info.get("format", {}).get("duration", 0))
        
        for i in range(min(max_frames, int(duration / interval) + 1)):
            timestamp = i * interval
            frame_path = output_dir / f"frame_{i:06d}.jpg"
            
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                str(frame_path),
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            if frame_path.exists():
                frames.append({
                    "index": i,
                    "timestamp": timestamp,
                    "path": str(frame_path),
                })
        
        return frames


class TranscriptAnalyzer:
    @staticmethod
    def parse_whisperx_output(whisperx_result: dict) -> list[TranscriptSegment]:
        segments = []
        for seg in whisperx_result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                words.append(TranscriptWord(
                    start=float(w.get("start", 0)),
                    end=float(w.get("end", 0)),
                    text=w.get("word", "").strip(),
                    speaker=w.get("speaker"),
                ))
            
            segments.append(TranscriptSegment(
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
                text=seg.get("text", "").strip(),
                speaker=seg.get("speaker"),
                words=words,
            ))
        
        return segments

    @staticmethod
    def get_speaker_segments(segments: list[TranscriptSegment]) -> dict[str, list[TranscriptSegment]]:
        speaker_map = {}
        for seg in segments:
            speaker = seg.speaker or "unknown"
            if speaker not in speaker_map:
                speaker_map[speaker] = []
            speaker_map[speaker].append(seg)
        return speaker_map

    @staticmethod
    def find_primary_speaker(segments: list[TranscriptSegment]) -> str:
        speaker_durations = {}
        for seg in segments:
            speaker = seg.speaker or "unknown"
            duration = seg.end - seg.start
            speaker_durations[speaker] = speaker_durations.get(speaker, 0) + duration
        
        return max(speaker_durations, key=speaker_durations.get) if speaker_durations else "unknown"

    @staticmethod
    def align_transcript_to_video(
        segments: list[TranscriptSegment],
        video_duration: float,
    ) -> list[TranscriptSegment]:
        aligned = []
        for seg in segments:
            start = max(0, min(seg.start, video_duration))
            end = max(start, min(seg.end, video_duration))
            if end > start:
                aligned.append(TranscriptSegment(
                    start=start,
                    end=end,
                    text=seg.text,
                    speaker=seg.speaker,
                    words=seg.words,
                ))
        return aligned