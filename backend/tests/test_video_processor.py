from __future__ import annotations

import pytest

from video_processor.ffmpeg_service import FFmpegService
from core.exceptions import CustomException


@pytest.mark.asyncio
async def test_probe_duration_missing_file():
    service = FFmpegService()
    result = await service.probe_duration("nonexistent_file.mp4")
    assert result == 0.0


@pytest.mark.asyncio
async def test_extract_frame_missing_file():
    service = FFmpegService()
    with pytest.raises(Exception):
        await service.extract_frame("nonexistent.mp4", 1.0, "/tmp/out.jpg")
