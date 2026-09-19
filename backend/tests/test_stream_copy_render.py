"""A crop that changes nothing is copied, not re-encoded.

A full-frame crop at the source's own size produces a file identical to a stream
copy, so re-encoding it only costs time -- a 39s 1080p clip took 114s to render
what ``-c copy`` produces in about a second. Copying is skipped whenever the
frame actually changes, and falls back to encoding if the copy fails.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from video_processor.ffmpeg_service import FFmpegService


@pytest.fixture
def service():
    return FFmpegService()


@pytest.fixture
def written_output(tmp_path):
    """Stand-in for FFmpeg writing a non-empty file."""
    path = tmp_path / "out.mp4"

    async def _write(*_args, **_kwargs):
        path.write_bytes(b"\x00" * 2048)
        return 0, ""

    return path, _write


async def _render(service, output_path, **overrides):
    kwargs = {
        "input_path": "source.mp4",
        "output_path": str(output_path),
        "start_time": 10.0,
        "duration": 5.0,
        "crop_tracking": [],
        "target_width": 1920,
        "target_height": 1080,
        "source_width": 1920,
        "source_height": 1080,
    }
    kwargs.update(overrides)
    await service.crop_with_tracking(**kwargs)


class TestStreamCopySelection:
    @pytest.mark.asyncio
    async def test_full_frame_same_size_is_copied(self, service, written_output):
        path, write = written_output
        with patch.object(service, "_run_ffmpeg_copy", side_effect=write) as copy, \
             patch.object(service, "_run_ffmpeg", new=AsyncMock()) as encode:
            await _render(service, path)

        copy.assert_awaited_once()
        encode.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_downscale_is_encoded(self, service, written_output):
        """Same crop, smaller output: a copy cannot scale."""
        path, write = written_output
        with patch.object(service, "_run_ffmpeg_copy", new=AsyncMock()) as copy, \
             patch.object(service, "_run_ffmpeg", side_effect=write) as encode, \
             patch.object(service, "_get_encoder_args", new=AsyncMock(return_value=[])):
            await _render(service, path, target_width=1280, target_height=720)

        copy.assert_not_awaited()
        encode.assert_awaited()

    @pytest.mark.asyncio
    async def test_vertical_crop_is_encoded(self, service, written_output):
        """The ordinary 9:16 path must not be diverted into a copy."""
        path, write = written_output
        with patch.object(service, "_run_ffmpeg_copy", new=AsyncMock()) as copy, \
             patch.object(service, "_run_ffmpeg", side_effect=write) as encode, \
             patch.object(service, "_get_encoder_args", new=AsyncMock(return_value=[])):
            await _render(service, path, target_width=1080, target_height=1920)

        copy.assert_not_awaited()
        encode.assert_awaited()

    @pytest.mark.asyncio
    async def test_copy_failure_falls_back_to_encoding(self, service, written_output):
        """Keyframes need not align with the cut; losing the clip is not an option."""
        path, write = written_output
        with patch.object(
            service, "_run_ffmpeg_copy", new=AsyncMock(return_value=(1, "copy failed"))
        ) as copy, \
             patch.object(service, "_run_ffmpeg", side_effect=write) as encode, \
             patch.object(service, "_get_encoder_args", new=AsyncMock(return_value=[])):
            await _render(service, path)

        copy.assert_awaited_once()
        encode.assert_awaited()
        assert path.exists() and path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_empty_copy_output_falls_back_to_encoding(self, service, tmp_path):
        """A zero-byte file means the copy silently produced nothing."""
        path = tmp_path / "out.mp4"

        async def empty_copy(*_args, **_kwargs):
            path.write_bytes(b"")
            return 0, ""

        async def real_write(*_args, **_kwargs):
            path.write_bytes(b"\x00" * 2048)
            return 0, ""

        with patch.object(service, "_run_ffmpeg_copy", side_effect=empty_copy), \
             patch.object(service, "_run_ffmpeg", side_effect=real_write) as encode, \
             patch.object(service, "_get_encoder_args", new=AsyncMock(return_value=[])):
            await _render(service, path)

        encode.assert_awaited()
        assert path.stat().st_size > 0


class TestCopyCommand:
    @pytest.mark.asyncio
    async def test_seek_is_after_input_so_the_cut_is_accurate(self, service, tmp_path):
        """An input seek with -c copy shifts the clip to the nearest keyframe."""
        captured = {}

        class _Proc:
            returncode = 0

            async def communicate(self):
                return b"", b""

        async def _spawn(*cmd, **_kwargs):
            captured["cmd"] = list(cmd)
            return _Proc()

        with patch("asyncio.create_subprocess_exec", new=_spawn):
            await service._run_ffmpeg_copy("in.mp4", str(tmp_path / "o.mp4"), 12.5, 4.0)

        cmd = captured["cmd"]
        assert cmd.index("-ss") > cmd.index("-i"), "output seek keeps the cut exact"
        assert "copy" in cmd
        assert cmd[cmd.index("-t") + 1] == "4.0"
