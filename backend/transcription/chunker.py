from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)


class TranscriptionChunker:
    @staticmethod
    def estimate_chunks(duration_seconds: float, chunk_duration: int, overlap: int) -> list[dict[str, float]]:
        chunks = []
        step = max(1, chunk_duration - overlap)
        start = 0.0
        while start < duration_seconds:
            end = min(start + chunk_duration, duration_seconds)
            chunks.append({"start": start, "end": end})
            if end >= duration_seconds:
                break
            start += step
        return chunks

    @staticmethod
    def extract_chunk_audio(
        input_path: str,
        output_path: str,
        start_seconds: float,
        duration_seconds: float,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        import subprocess
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", str(start_seconds),
            "-i", input_path,
            "-t", str(duration_seconds),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg chunk extraction failed: {proc.stderr}")
        return output_path

    @staticmethod
    def is_video_file(path: str) -> bool:
        video_extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv", ".m4v"}
        return Path(path).suffix.lower() in video_extensions

    @staticmethod
    async def ensure_wav_audio(input_path: str, sample_rate: int = 16000, channels: int = 1) -> str:
        if not TranscriptionChunker.is_video_file(input_path):
            return input_path
        from audio.extraction.ffmpeg_runner import FFmpegRunner
        runner = FFmpegRunner()
        base, _ = os.path.splitext(input_path)
        wav_path = f"{base}_transcription.wav"
        await runner.run(
            input_path=input_path,
            output_path=wav_path,
            codec="pcm_s16le",
            sample_rate=sample_rate,
            channels="mono" if channels == 1 else "stereo",
            overwrite=True,
        )
        return wav_path

    @staticmethod
    def _estimate_duration(input_path: str) -> float:
        from audio.extraction.ffmpeg_runner import FFmpegRunner
        runner = FFmpegRunner()
        return runner.probe_duration(input_path)
