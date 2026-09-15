from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from content_intelligence.reframing import crop_tracking_expressions

from core.logging_config import get_logger
from core.exceptions import CustomException

log = get_logger(__name__)


class FFmpegService:
    _encoder_args: list[str] | None = None

    @classmethod
    async def _get_encoder_args(cls) -> list[str]:
        if cls._encoder_args is not None:
            return cls._encoder_args

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-encoders",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        available = stdout.decode("utf-8", errors="ignore")

        if proc.returncode != 0:
            raise CustomException(
                message=f"Unable to inspect FFmpeg encoders (exit code {proc.returncode}).",
                code="VIDEO_ENCODER_CHECK_FAILED",
                status_code=500,
            )

        candidates = [
            ("libx264", ["-c:v", "libx264", "-preset", "fast", "-crf", "20"]),
            ("libopenh264", ["-c:v", "libopenh264", "-b:v", "2M"]),
            ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "fast", "-cq", "23"]),
            ("mpeg4", ["-c:v", "mpeg4", "-q:v", "5"]),
        ]
        for encoder, args in candidates:
            if encoder not in available:
                continue
            probe = await asyncio.create_subprocess_exec(
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=16x16:d=0.1",
                "-frames:v", "1", *args, "-f", "null", "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, probe_stderr = await probe.communicate()
            if probe.returncode == 0:
                cls._encoder_args = args
                log.info("Selected FFmpeg video encoder: %s", encoder)
                return cls._encoder_args
            log.warning(
                "FFmpeg encoder unavailable at runtime: %s error=%s",
                encoder,
                probe_stderr.decode("utf-8", errors="ignore").strip()[-300:],
            )

        else:
            raise CustomException(
                message="FFmpeg has no usable supported video encoder. Install libx264, libopenh264, or enable mpeg4 encoding.",
                code="VIDEO_ENCODER_UNAVAILABLE",
                status_code=500,
            )

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
            "-show_streams", "-show_format",
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
        end = start + duration
        segment_cut_start = time.time()
        log.info(
            ">>> [CUT START] video segment | start=%ss end=%ss duration=%ss reencode=%s",
            round(start, 3), round(end, 3), round(duration, 3), reencode,
            extra={
                "input_path": input_path,
                "output_path": output_path,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "reencode": reencode,
            },
        )
        if reencode:
            encoder_args = await self._get_encoder_args()
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start), "-i", input_path,
                "-t", str(duration),
                *encoder_args,
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
        file_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
        segment_cut_elapsed = time.time() - segment_cut_start
        log.info(
            "<<< [CUT OK] video segment | start=%ss end=%ss duration=%ss size=%sMB elapsed=%ss",
            round(start, 3), round(end, 3), round(duration, 3),
            round(file_size / (1024 * 1024), 2), round(segment_cut_elapsed, 2),
            extra={
                "input_path": input_path,
                "output_path": output_path,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "elapsed_seconds": round(segment_cut_elapsed, 2),
            },
        )

    async def vertical_reframe(self, input_path: str, output_path: str, target_width: int = 1080, target_height: int = 1920) -> None:
        encoder_args = await self._get_encoder_args()
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale=iw*min({target_width}/iw\\,{target_height}/ih):ih*min({target_width}/iw\\,{target_height}/ih),"
                    f"crop={target_width}:{target_height}:(iw-{target_width})/2:(ih-{target_height})/2",
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Reframe failed: {err}", code="REFAME_FAILED", status_code=500)

    async def crop_with_tracking(
        self,
        input_path: str,
        output_path: str,
        start_time: float = 0.0,
        duration: float | None = None,
        crop_tracking: list[dict] | None = None,
        target_width: int = 1080,
        target_height: int = 1920,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> None:
        crop_start_time = time.time()
        
        log.info(
            "FFmpeg crop_with_tracking STARTED",
            extra={
                "input_path": input_path,
                "output_path": output_path,
                "start_time": start_time,
                "duration": duration,
                "target_width": target_width,
                "target_height": target_height,
                "source_width": source_width,
                "source_height": source_height,
                "crop_tracking_points": len(crop_tracking) if crop_tracking else 0,
            },
        )

        if duration is None:
            duration = await self.probe_duration(input_path)
            log.info("Probed video duration", extra={"duration": duration, "input_path": input_path})
        
        crop_tracking = crop_tracking or []
        if duration <= 0 or target_width <= 0 or target_height <= 0:
            raise CustomException(message="Invalid crop render parameters", code="INVALID_CROP_RENDER", status_code=400)

        info = await self.get_video_info(input_path)
        streams = info.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type") == "video"), streams[0] if streams else {})
        source_width = int(source_width or stream.get("width", 0) or 0)
        source_height = int(source_height or stream.get("height", 0) or 0)
        if not source_width or not source_height:
            raise CustomException(message="Source video dimensions are unavailable", code="VIDEO_DIMENSIONS_UNAVAILABLE", status_code=400)

        log.info(
            "Source video info",
            extra={
                "source_width": source_width,
                "source_height": source_height,
                "source_aspect_ratio": round(source_width / source_height, 3),
                "target_width": target_width,
                "target_height": target_height,
                "target_aspect_ratio": round(target_width / target_height, 3),
            },
        )

        target_ratio = target_width / target_height
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            crop_height = source_height
            crop_width = int(round(crop_height * target_ratio))
        else:
            crop_width = source_width
            crop_height = int(round(crop_width / target_ratio))
        crop_width -= crop_width % 2
        crop_height -= crop_height % 2
        crop_width = max(2, crop_width)
        crop_height = max(2, crop_height)

        log.info(
            "Crop dimensions calculated",
            extra={
                "crop_width": crop_width,
                "crop_height": crop_height,
                "crop_area_ratio": round((crop_width * crop_height) / (source_width * source_height), 3),
            },
        )

        relative_tracking = [
            {**point, "timestamp": max(0.0, float(point.get("timestamp", 0.0)) - start_time)}
            for point in crop_tracking
        ]
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        x_expression, y_expression = crop_tracking_expressions(
            relative_tracking,
            source_width,
            source_height,
            crop_width,
            crop_height,
        )
        x_expression = x_expression.replace(",", "\\,")
        y_expression = y_expression.replace(",", "\\,")
        video_filter = (
            f"crop={crop_width}:{crop_height}:{x_expression}:{y_expression},"
            f"scale={target_width}:{target_height}:flags=lanczos"
        )
        
        log.info(
            "FFmpeg filter graph built",
            extra={
                "video_filter": video_filter,
                "x_expression": x_expression[:200] + "..." if len(x_expression) > 200 else x_expression,
                "y_expression": y_expression[:200] + "..." if len(y_expression) > 200 else y_expression,
            },
        )

        end_time = start_time + duration
        log.info(
            ">>> [CUT START] video clip | start=%ss end=%ss duration=%ss target=%sx%s source=%sx%s tracking_points=%s",
            round(start_time, 3), round(end_time, 3), round(duration, 3),
            target_width, target_height, source_width, source_height,
            len(crop_tracking) if crop_tracking else 0,
            extra={
                "input_path": input_path,
                "output_path": output_path,
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
                "duration": round(duration, 3),
                "target_width": target_width,
                "target_height": target_height,
                "source_width": source_width,
                "source_height": source_height,
                "crop_tracking_points": len(crop_tracking) if crop_tracking else 0,
            },
        )

        encoder_args = await self._get_encoder_args()
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time), "-i", input_path,
            "-t", str(duration),
            "-vf", video_filter,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

        log.info(
            "Executing FFmpeg command (tracked crop)",
            extra={
                "cmd": " ".join(cmd[:4]) + " ... " + " ".join(cmd[-3:]),
                "full_cmd": " ".join(cmd),
                "start_time": start_time,
                "duration": duration,
            },
        )

        ffmpeg_start = time.time()
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        ffmpeg_elapsed = time.time() - ffmpeg_start

        if proc.returncode != 0:
            tracked_error = stderr.decode("utf-8", errors="ignore")[-500:]
            log.warning(
                "Tracked crop failed, retrying with centered crop",
                extra={
                    "error": tracked_error,
                    "ffmpeg_elapsed_seconds": round(ffmpeg_elapsed, 2),
                    "return_code": proc.returncode,
                },
            )
            try:
                output_file.unlink(missing_ok=True)
            except OSError:
                pass

            fallback_filter = (
                f"crop={crop_width}:{crop_height}:(iw-{crop_width})/2:(ih-{crop_height})/2,"
                f"scale={target_width}:{target_height}:flags=lanczos"
            )
            fallback_cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time), "-i", input_path,
                "-t", str(duration),
                "-vf", fallback_filter,
                *encoder_args,
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ]
            
            log.info(
                "Executing FFmpeg fallback command (centered crop)",
                extra={
                    "fallback_filter": fallback_filter,
                    "cmd": " ".join(fallback_cmd[:4]) + " ... " + " ".join(fallback_cmd[-3:]),
                },
            )
            
            fallback_start = time.time()
            fallback_proc = await asyncio.create_subprocess_exec(
                *fallback_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, fallback_stderr = await fallback_proc.communicate()
            fallback_elapsed = time.time() - fallback_start
            
            if fallback_proc.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                total_elapsed = time.time() - crop_start_time
                log.info(
                    "<<< [CUT OK] video clip (centered crop fallback) | start=%ss end=%ss duration=%ss size=%sMB ffmpeg=%ss total=%ss",
                    round(start_time, 3), round(end_time, 3), round(duration, 3),
                    round(output_file.stat().st_size / (1024 * 1024), 2),
                    round(fallback_elapsed, 2), round(total_elapsed, 2),
                    extra={
                        "input_path": input_path,
                        "output_path": output_path,
                        "start_time": round(start_time, 3),
                        "end_time": round(end_time, 3),
                        "duration": round(duration, 3),
                        "fallback_elapsed_seconds": round(fallback_elapsed, 2),
                        "total_elapsed_seconds": round(total_elapsed, 2),
                        "file_size_bytes": output_file.stat().st_size,
                        "file_size_mb": round(output_file.stat().st_size / (1024 * 1024), 2),
                    },
                )
                return

            fallback_error = fallback_stderr.decode("utf-8", errors="ignore")[-500:]
            total_elapsed = time.time() - crop_start_time
            log.error(
                "Both tracked crop and centered fallback FAILED",
                extra={
                    "tracked_error": tracked_error,
                    "fallback_error": fallback_error,
                    "total_elapsed_seconds": round(total_elapsed, 2),
                },
            )
            raise CustomException(
                message=f"Tracked crop and centered fallback failed: {fallback_error or tracked_error}",
                code="TRACKED_CROP_FAILED",
                status_code=500,
            )
        
        total_elapsed = time.time() - crop_start_time
        file_size = output_file.stat().st_size if output_file.exists() else 0
        log.info(
            "<<< [CUT OK] video clip | start=%ss end=%ss duration=%ss size=%sMB ffmpeg=%ss total=%ss",
            round(start_time, 3), round(end_time, 3), round(duration, 3),
            round(file_size / (1024 * 1024), 2), round(ffmpeg_elapsed, 2), round(total_elapsed, 2),
            extra={
                "input_path": input_path,
                "output_path": output_path,
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
                "duration": round(duration, 3),
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "ffmpeg_elapsed_seconds": round(ffmpeg_elapsed, 2),
                "total_elapsed_seconds": round(total_elapsed, 2),
            },
        )

    async def concat_segments(self, segment_paths: list[str], output_path: str) -> None:
        list_file = output_path + ".concat.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for path in segment_paths:
                safe_path = path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        encoder_args = await self._get_encoder_args()
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Concat failed: {err}", code="CONCAT_FAILED", status_code=500)
