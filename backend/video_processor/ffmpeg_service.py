from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from video_processor.geometry import crop_tracking_path, target_crop_size

from core.logging_config import get_logger
from core.exceptions import CustomException

log = get_logger(__name__)

CROP_COMMANDS_FILE = "crop.cmd"


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
        """Cut [start_time, start_time+duration] and pan-crop to the target size.

        Emits one INFO line per render; the filter graph and full command are
        DEBUG, since a tracked crop expression runs to several thousand
        characters and drowns the rest of the pipeline log.
        """
        started = time.time()

        if duration is None:
            duration = await self.probe_duration(input_path)
        if duration <= 0 or target_width <= 0 or target_height <= 0:
            raise CustomException(message="Invalid crop render parameters", code="INVALID_CROP_RENDER", status_code=400)

        crop_tracking = crop_tracking or []

        if not source_width or not source_height:
            info = await self.get_video_info(input_path)
            streams = info.get("streams") or []
            stream = next((item for item in streams if item.get("codec_type") == "video"), streams[0] if streams else {})
            source_width = int(source_width or stream.get("width", 0) or 0)
            source_height = int(source_height or stream.get("height", 0) or 0)
        if not source_width or not source_height:
            raise CustomException(message="Source video dimensions are unavailable", code="VIDEO_DIMENSIONS_UNAVAILABLE", status_code=400)

        crop_width, crop_height = target_crop_size(source_width, source_height, f"{target_width}:{target_height}")

        # Tracking timestamps are absolute; the filter graph runs on the cut clip.
        relative_tracking = [
            {**point, "timestamp": max(0.0, float(point.get("timestamp", 0.0)) - start_time)}
            for point in crop_tracking
        ]
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        path = crop_tracking_path(
            relative_tracking, source_width, source_height, crop_width, crop_height, duration,
        )
        _, start_x, start_y = path[0]
        # The crop starts at the path's first position and sendcmd moves it
        # every frame after. The command file is referenced by bare name with
        # cwd set to its directory, which avoids escaping drive letters and
        # colons inside the filter string.
        video_filter = (
            f"sendcmd=f={CROP_COMMANDS_FILE},"
            f"crop={crop_width}:{crop_height}:{start_x}:{start_y},"
            f"scale={target_width}:{target_height}:flags=lanczos"
        )
        log.debug("Crop filter graph", extra={"video_filter": video_filter})

        # A crop that covers the whole frame at the source's own size changes
        # nothing, so re-encoding it only costs time -- a 39s 1080p clip took
        # 114s to produce a file identical in content to a stream copy. Copying
        # needs the output size to match the source too, since a copy cannot
        # scale.
        if (
            crop_width >= source_width
            and crop_height >= source_height
            and target_width == source_width
            and target_height == source_height
        ):
            returncode, stderr = await self._run_ffmpeg_copy(
                input_path, output_path, start_time, duration
            )
            if returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                size_mb = output_file.stat().st_size / (1024 * 1024)
                log.info(
                    "Copied %.2fs %dx%d in %.1fs (%.2fMB)",
                    duration, target_width, target_height, time.time() - started, size_mb,
                    extra={
                        "output_path": output_path,
                        "start_time": round(start_time, 3),
                        "end_time": round(start_time + duration, 3),
                        "crop": "none",
                        "tracking_points": len(crop_tracking),
                    },
                )
                return
            # Copying can fail on sources whose keyframes do not line up with
            # the cut; fall through and encode rather than lose the clip.
            log.warning(
                "Stream copy failed, re-encoding: %s",
                (stderr or "")[-200:],
                extra={"output_path": output_path},
            )
            output_file.unlink(missing_ok=True)

        encoder_args = await self._get_encoder_args()
        with tempfile.TemporaryDirectory() as workdir:
            Path(workdir, CROP_COMMANDS_FILE).write_text(
                "".join(f"{t:.3f} crop x {x}, crop y {y};\n" for t, x, y in path),
                encoding="utf-8",
            )
            # FFmpeg runs from workdir, so local paths must be absolute; URLs
            # (a presigned S3 source) are passed through untouched.
            source = input_path if "://" in input_path else str(Path(input_path).resolve())
            returncode, stderr = await self._run_ffmpeg(
                source, str(output_file.resolve()),
                start_time, duration, video_filter, encoder_args, cwd=workdir,
            )

        if returncode != 0:
            log.warning(
                "Tracked crop failed, retrying centred: %s",
                stderr[-200:],
                extra={"output_path": output_path},
            )
            output_file.unlink(missing_ok=True)
            fallback_filter = (
                f"crop={crop_width}:{crop_height}:(iw-{crop_width})/2:(ih-{crop_height})/2,"
                f"scale={target_width}:{target_height}:flags=lanczos"
            )
            returncode, fallback_stderr = await self._run_ffmpeg(
                input_path, output_path, start_time, duration, fallback_filter, encoder_args
            )
            if returncode != 0 or not output_file.exists() or output_file.stat().st_size == 0:
                raise CustomException(
                    message=f"Tracked crop and centred fallback failed: {(fallback_stderr or stderr)[-300:]}",
                    code="TRACKED_CROP_FAILED",
                    status_code=500,
                )

        size_mb = output_file.stat().st_size / (1024 * 1024) if output_file.exists() else 0.0
        log.info(
            "Rendered %.2fs %dx%d in %.1fs (%.2fMB)",
            duration, target_width, target_height, time.time() - started, size_mb,
            extra={
                "output_path": output_path,
                "start_time": round(start_time, 3),
                "end_time": round(start_time + duration, 3),
                "crop": f"{crop_width}x{crop_height}",
                "tracking_points": len(crop_tracking),
                "crop_positions": len(path),
            },
        )

    async def _run_ffmpeg_copy(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
    ) -> tuple[int, str]:
        """Cut without re-encoding, for when no crop or scale is needed.

        Seeking is done after ``-i`` so the cut lands on the requested second
        rather than the nearest preceding keyframe; with ``-c copy`` an input
        seek would silently shift the clip by up to a keyframe interval.
        """
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            output_path,
        ]
        log.debug("Running FFmpeg (stream copy)", extra={"cmd": " ".join(cmd)})
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        return proc.returncode, stderr.decode("utf-8", errors="ignore")

    async def _run_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        video_filter: str,
        encoder_args: list[str],
        cwd: str | None = None,
    ) -> tuple[int, str]:
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
        log.debug("Running FFmpeg", extra={"cmd": " ".join(cmd)})
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
        )
        _, stderr = await proc.communicate()
        return proc.returncode, stderr.decode("utf-8", errors="ignore")

    async def concat_segments(self, segment_paths: list[str], output_path: str) -> None:
        """Join segments end to end by stream copy.

        The segments must share codecs and encoding parameters, as renders from
        the same source and settings do; nothing is re-encoded.
        """
        list_file = output_path + ".concat.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for path in segment_paths:
                # The concat demuxer resolves relative entries against the list
                # file's own directory, not the cwd, so write absolute paths.
                safe_path = str(Path(path).resolve()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            "ffmpeg", "-y", "-nostdin", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, stderr = await proc.communicate()
        finally:
            Path(list_file).unlink(missing_ok=True)
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-200:]
            raise CustomException(message=f"Concat failed: {err}", code="CONCAT_FAILED", status_code=500)
