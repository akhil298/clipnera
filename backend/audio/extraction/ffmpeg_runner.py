from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.exceptions import CustomException
from core.logging_config import get_logger

log = get_logger(__name__)

PROGRESS_PATTERN = re.compile(
    r"(?:frame|fps|bitrate|total_size|out_time_us|speed|progress)\s*=\s*(\S+)"
)


@dataclass
class FFmpegProgress:
    percent: float = 0.0
    frame: int = 0
    fps: float = 0.0
    bitrate: str = ""
    total_size: int = 0
    out_time_us: int = 0
    speed: str = ""
    status: str = "idle"


class FFmpegRunner:
    """Subprocess wrapper for FFmpeg with streaming progress."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary
        self._verify_binary()

    def _verify_binary(self) -> None:
        if not shutil.which(self.ffmpeg_binary):
            raise CustomException(
                message=f"FFmpeg binary not found: {self.ffmpeg_binary}. Install FFmpeg and ensure it is in PATH.",
                code="FFMPEG_NOT_FOUND",
                status_code=500,
            )

    def _build_command(
        self,
        input_path: str,
        output_path: str,
        codec: str,
        sample_rate: int,
        channels: str,
        overwrite: bool = False,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        cmd = [self.ffmpeg_binary, "-hide_banner", "-loglevel", "error"]
        if overwrite:
            cmd.append("-y")
        else:
            cmd.append("-n")
        cmd.extend(["-i", input_path])
        cmd.extend(["-vn"])
        cmd.extend(["-acodec", codec])
        cmd.extend(["-ar", str(sample_rate)])
        cmd.extend(["-ac", "1" if channels == "mono" else "2"])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(output_path)
        return cmd

    @staticmethod
    def _parse_progress_line(line: str) -> dict[str, str]:
        result = {}
        for key, value in PROGRESS_PATTERN.findall(line):
            result[key] = value
        return result

    async def run(
        self,
        input_path: str,
        output_path: str,
        codec: str = "pcm_s16le",
        sample_rate: int = 16000,
        channels: str = "mono",
        overwrite: bool = False,
        extra_args: list[str] | None = None,
        timeout: int = 0,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> tuple[int, str, str]:
        cmd = self._build_command(input_path, output_path, codec, sample_rate, channels, overwrite, extra_args)
        log.debug(f"FFmpeg command: {' '.join(cmd)}")

        kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.DEVNULL,
        }
        if timeout > 0:
            kwargs["timeout"] = timeout

        proc = subprocess.Popen(cmd, **kwargs)

        stdout_data = []
        stderr_data = []

        try:
            if progress_callback:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        stdout_data.append(decoded)
                        parsed = self._parse_progress_line(decoded)
                        if parsed:
                            prog = FFmpegProgress(
                                percent=float(parsed.get("percent", "0").rstrip("%") or "0"),
                                frame=int(parsed.get("frame", "0") or "0"),
                                fps=float(parsed.get("fps", "0") or "0"),
                                bitrate=parsed.get("bitrate", ""),
                                total_size=int(parsed.get("total_size", "0") or "0"),
                                out_time_us=int(parsed.get("out_time_us", "0") or "0"),
                                speed=parsed.get("speed", ""),
                                status=parsed.get("progress", "idle"),
                            )
                            progress_callback(prog)

            returncode = proc.wait(timeout if timeout > 0 else None)
            stdout_bytes = b"".join(proc.stdout.readlines()) if proc.stdout else b""
            stderr_bytes = b"".join(proc.stderr.readlines()) if proc.stderr else b""
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")
            return returncode, stdout_str, stderr_str
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise CustomException(
                message=f"FFmpeg timed out after {timeout}s",
                code="FFMPEG_TIMEOUT",
                status_code=408,
            )
        except Exception as exc:
            proc.kill()
            proc.wait()
            raise CustomException(
                message=f"FFmpeg execution failed: {exc}",
                code="FFMPEG_EXECUTION_ERROR",
                status_code=500,
            ) from exc

    def probe_duration(self, input_path: str) -> float:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        stdout = proc.stdout or ""
        try:
            return float(stdout.strip())
        except ValueError:
            return 0.0

    def probe_streams(self, input_path: str) -> list[dict]:
        cmd = [
            self.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-i",
            input_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.warning(f"FFprobe streams failed: {proc.stderr}")
            return []
        try:
            info = json.loads(proc.stdout)
            return info.get("streams", [])
        except json.JSONDecodeError:
            return []

    def get_output_duration(self, output_path: str) -> float:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        stdout = proc.stdout or ""
        try:
            return float(stdout.strip())
        except ValueError:
            return 0.0
