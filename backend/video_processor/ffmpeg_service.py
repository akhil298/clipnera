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
# A crop enlarged more than this (a 1080p source cropped to 9:16 is enlarged
# 1.78x) is sharpened after scaling, to restore the edge detail upscaling softens.
SHARPEN_ABOVE_SCALE = 1.2
UPSCALE_SHARPEN = "unsharp=5:5:0.6:5:5:0.0"
# The blurred backdrop behind a fitted frame is blurred at this fraction of the
# output size, which is several times cheaper than blurring at full size.
BACKDROP_SCALE = 4


# A punch-in eases to full zoom over this long (ease-out cubic), then holds.
# A hard jump read as a glitch; a slow drift reads as a camera move.
PUNCH_IN_RAMP_SECONDS = 0.25


def punch_in_filter(zoom: float, width: int, height: int, fps: float) -> str:
    """Centred zoom from 1x to ``zoom`` at a fixed ``width``x``height``.

    zoompan keeps the frame size constant (a per-frame ``scale`` resized the
    stream and reset crop's centring); ``d=1`` with the source ``fps`` maps
    frames one to one, so audio stays in sync.
    """
    eased = f"1+{zoom - 1:.4f}*(1-pow(1-min(1,it/{PUNCH_IN_RAMP_SECONDS}),3))"
    return (
        f"zoompan=z='{eased}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d=1:s={width}x{height}:fps={fps:.3f}"
    )


def upscale_filter(width: int, height: int, factor: float, fit: str = "") -> str:
    """Lanczos scale to ``width``x``height``, sharpened when ``factor`` enlarges noticeably.

    ``fit`` is an optional ``force_original_aspect_ratio`` mode; with it the
    caller crops or pads the result to size.
    """
    fit_option = f":force_original_aspect_ratio={fit}" if fit else ""
    chain = f"scale={width}:{height}{fit_option}:flags=lanczos"
    return f"{chain},{UPSCALE_SHARPEN}" if factor > SHARPEN_ABOVE_SCALE else chain


class FFmpegService:
    _encoder_args: list[str] | None = None
    _has_libass: bool | None = None

    @classmethod
    async def require_caption_support(cls) -> None:
        """Raise unless FFmpeg can burn captions and titles.

        Builds without libass (Homebrew's plain ``ffmpeg`` since 2025) lack the
        ``ass`` filter, and every burn then fails deep inside the render.
        """
        if cls._has_libass is None:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-hide_banner", "-filters",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            cls._has_libass = any(
                line.split()[1:2] == ["ass"] for line in stdout.decode("utf-8", errors="ignore").splitlines()
            )
        if not cls._has_libass:
            raise CustomException(
                message="FFmpeg on this server was built without libass, so captions and titles cannot be burned in.",
                code="CAPTIONS_UNAVAILABLE",
                status_code=500,
            )

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

        # veryfast encodes a 60s 1080x1920 cut ~2.6x faster than fast (4.6s vs
        # 12.0s on 2 threads) at SSIM 0.993 vs 0.994 against a near-lossless
        # reference; the difference is invisible and the files are smaller.
        # CRF 18 because this cut is encoded again when captions are burned,
        # and each generation loses detail. yuv420p keeps every part of a clip
        # (crop, stack, fit) in one pixel format, so they join by stream copy.
        candidates = [
            ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]),
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

    async def probe_fps(self, input_path: str) -> float:
        """Frame rate of the first video stream; 30 when it cannot be read."""
        info = await self.get_video_info(input_path)
        stream = next((s for s in info.get("streams") or [] if s.get("codec_type") == "video"), {})
        rate = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "")
        try:
            num, _, den = rate.partition("/")
            fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        return fps if fps > 0 else 30.0

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
        zoom: float = 1.0,
    ) -> None:
        """Cut [start_time, start_time+duration] and pan-crop to the target size.

        ``zoom`` above 1 is a punch-in: the tracked crop is rendered as usual
        and then eased in to ``zoom`` over the first quarter second, centred on
        the tracked subject; the output size is unchanged.

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
        scale = upscale_filter(target_width, target_height, target_height / crop_height)
        video_filter = (
            f"sendcmd=f={CROP_COMMANDS_FILE},"
            f"crop={crop_width}:{crop_height}:{start_x}:{start_y},"
            f"{scale},setsar=1"
        )
        if zoom > 1.0:
            fps = await self.probe_fps(input_path)
            video_filter += "," + punch_in_filter(zoom, target_width, target_height, fps)
        log.debug("Crop filter graph", extra={"video_filter": video_filter})

        # A crop that covers the whole frame at the source's own size changes
        # nothing, so re-encoding it only costs time -- a 39s 1080p clip took
        # 114s to produce a file identical in content to a stream copy. Copying
        # needs the output size to match the source too, since a copy cannot
        # scale.
        if (
            zoom <= 1.0
            and crop_width >= source_width
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
                f"{scale},setsar=1"
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

    async def render_stack(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        cells: list[tuple[dict, int]],
        target_width: int,
        source_width: int,
        source_height: int,
    ) -> None:
        """Render regions of the source stacked top to bottom into one frame.

        ``cells`` are ``(normalised box, output height)`` pairs; each region is
        scaled to cover its cell and centre-cropped, so nothing is letterboxed.
        Uses the same encoder settings as tracked crops, so the two join by
        stream copy.
        """
        chains = []
        labels = []
        for index, (box, height) in enumerate(cells):
            w = max(2, int(box["width"] * source_width) // 2 * 2)
            h = max(2, int(box["height"] * source_height) // 2 * 2)
            x = min(max(0, int(box["x"] * source_width)), source_width - w)
            y = min(max(0, int(box["y"] * source_height)), source_height - h)
            scale = upscale_filter(target_width, height, max(target_width / w, height / h), fit="increase")
            chains.append(
                f"[s{index}]crop={w}:{h}:{x}:{y},{scale},"
                f"crop={target_width}:{height},setsar=1[c{index}]"
            )
            labels.append(f"[c{index}]")
        graph = (
            f"[0:v]split={len(cells)}" + "".join(f"[s{i}]" for i in range(len(cells))) + ";"
            + ";".join(chains) + ";"
            + "".join(labels) + f"vstack=inputs={len(cells)}[v]"
        )
        await self._render_graph(input_path, output_path, start_time, duration, graph, "STACK_RENDER_FAILED")

    async def render_fit(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        target_width: int,
        target_height: int,
        source_width: int,
    ) -> None:
        """Render the whole source frame, fitted to the output width over a
        blurred, dimmed copy of itself.

        For shots with nobody in them (animation, B-roll, slides), where any
        crop would cut an arbitrary slice out of the picture.
        """
        back_w = target_width // BACKDROP_SCALE // 2 * 2
        back_h = target_height // BACKDROP_SCALE // 2 * 2
        graph = (
            "[0:v]split=2[bg][fg];"
            f"[bg]scale={back_w}:{back_h}:force_original_aspect_ratio=increase,crop={back_w}:{back_h},"
            f"boxblur=16:3,eq=brightness=-0.12,scale={target_width}:{target_height},setsar=1[back];"
            f"[fg]{upscale_filter(target_width, -2, target_width / source_width)},setsar=1[front];"
            "[back][front]overlay=(W-w)/2:(H-h)/2[v]"
        )
        await self._render_graph(input_path, output_path, start_time, duration, graph, "FIT_RENDER_FAILED")

    async def _render_graph(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        graph: str,
        error_code: str,
    ) -> None:
        """Encode ``graph`` (ending in ``[v]``) over a stretch of the source, with
        the same encoder settings as tracked crops so the parts join by stream copy."""
        encoder_args = await self._get_encoder_args()
        source = input_path if "://" in input_path else str(Path(input_path).resolve())
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", str(start_time), "-i", source,
            "-t", str(duration),
            "-filter_complex", graph,
            "-map", "[v]", "-map", "0:a?",
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not Path(output_path).exists():
            raise CustomException(
                message=f"Composite render failed: {stderr.decode('utf-8', errors='ignore')[-300:]}",
                code=error_code,
                status_code=500,
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
