from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Optional

from core.logging_config import get_logger
from core.exceptions import CustomException

log = get_logger(__name__)


class FFmpegService:
    async def probe_duration(self, input_path: str) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            return float(stdout.decode().strip() or 0)
        except Exception as exc:
            raise CustomException(message=f"FFprobe failed: {exc}", code="FFPROBE_ERROR", status_code=500)

    async def get_video_info(self, input_path: str) -> dict:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,codec_name,duration:stream_index=0",
            "-show_entries", "format=duration,bit_rate",
            "-of", "json",
            input_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            return __import__("json").loads(stdout.decode())
        except Exception as exc:
            raise CustomException(message=f"FFprobe failed: {exc}", code="FFPROBE_ERROR", status_code=500)

    async def extract_frame(self, input_path: str, timestamp: float, output_path: str) -> None:
        cmd = [
            "ffmpeg", "-y", "-ss", str(timestamp), "-i", input_path,
            "-vframes", "1", "-q:v", "2",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Frame extraction failed: {err}", code="FRAME_EXTRACT_FAILED", status_code=500)

    async def cut_segment(self, input_path: str, start: float, duration: float, output_path: str, reencode: bool = True) -> None:
        if reencode:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start), "-i", input_path,
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start), "-i", input_path,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_path,
            ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Cut segment failed: {err}", code="CUT_FAILED", status_code=500)

    async def vertical_reframe(self, input_path: str, output_path: str, target_width: int = 1080, target_height: int = 1920) -> None:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale=iw*min({target_width}/iw\\,{target_height}/ih):ih*min({target_width}/iw\\,{target_height}/ih),"
                    f"crop={target_width}:{target_height}:(iw-{target_width})/2:(ih-{target_height})/2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Reframe failed: {err}", code="REFAME_FAILED", status_code=500)

    async def concat_segments(self, segment_paths: list[str], output_path: str) -> None:
        list_file = output_path + ".concat.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for path in segment_paths:
                safe_path = path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Concat failed: {err}", code="CONCAT_FAILED", status_code=500)
