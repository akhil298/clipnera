from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from branding.service import STATIC_DIR, Assets, apply_branding, branding_cmd, nearest
from branding.watermark import SparkOverlay, loudness
from hook_transitions.graph import MediaInfo

FILES = {"9x16": "a.mp4", "16x9": "b.mp4", "1x1": "c.mp4"}


def _clip(path: Path, size: str, seconds: float, audio: str | None) -> Path:
    """A test clip; ``audio`` is an lavfi source, or None for no audio track."""
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:r=30:d={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", audio, "-shortest", "-c:a", "aac"]
    subprocess.run([*cmd, "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class TestRenditions:
    @pytest.mark.parametrize(("size", "expected"), [
        ((1080, 1920), "a.mp4"), ((720, 1280), "a.mp4"), ((1920, 1080), "b.mp4"),
        ((1080, 1080), "c.mp4"), ((1080, 1350), "c.mp4"),
    ])
    def test_nearest_shape_wins(self, size, expected):
        assert nearest(FILES, *size) == expected

    def test_missing_manifest_means_unbranded(self, tmp_path):
        assert Assets.load(tmp_path) is None

    def test_shipped_assets_are_complete(self):
        found = Assets.load()
        assert found is not None, "run branding/motion/source/render.mjs production"
        for path in [*found.intro.values(), *found.outro.values(), found.layout]:
            assert Path(path).exists(), path
        assert 4 < found.intro_s < 7 and 4 < found.outro_s < 6


class TestBrandingCommand:
    @staticmethod
    def _cmd(has_audio: bool) -> list[str]:
        media = MediaInfo(width=1080, height=1920, fps=30.0, duration=12.0, has_audio=has_audio)
        found = Assets(intro=FILES, intro_s=5.3, outro=FILES, outro_s=4.9, blur_in_s=0.9, layout=Path("l.json"))
        return branding_cmd(Path("clip.mp4"), Path("out.mp4"), media, found, Path("wm.mov"), (700, 40), Path("last.png"))

    def test_intro_clip_and_end_card_are_joined_in_order(self):
        cmd = self._cmd(True)
        inputs = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-i"]
        assert inputs == ["clip.mp4", "wm.mov", "a.mp4", "a.mp4", "last.png"]
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "[intro][ia][main][ma][outro][oa]concat=n=3:v=1:a=1[v][a]" in graph
        assert "overlay=x=700:y=40:eof_action=pass" in graph
        assert "[0:a]asetpts=PTS-STARTPTS[ma]" in graph

    def test_clip_without_sound_gets_silence(self):
        graph = self._cmd(False)[self._cmd(False).index("-filter_complex") + 1]
        assert "atrim=duration=12.000[ma]" in graph and "[0:a]" not in graph


class TestListeningSpark:
    def test_loudness_follows_the_voice(self, tmp_path):
        clip = _clip(tmp_path / "v.mp4", "320x240", 2, "sine=f=440:d=1")
        levels = loudness(clip, 30.0, 60, True)
        assert levels.shape == (60,)
        assert levels[10:28].min() > 0.5 and levels[-5:].max() < 0.1

    def test_no_audio_is_silence(self, tmp_path):
        assert not loudness(tmp_path / "missing.mp4", 30.0, 10, False).any()

    def test_overlay_scales_to_the_frame(self):
        big = SparkOverlay(STATIC_DIR / "watermark" / "listening-spark" / "layout.json", 1080)
        small = SparkOverlay(STATIC_DIR / "watermark" / "listening-spark" / "layout.json", 540)
        assert small.size[0] == pytest.approx(big.size[0] / 2, abs=1)
        # The glow's padding may run past the frame edge; FFmpeg clips it.
        x, y = big.position(1080)
        assert 540 > x > 0 and x + big.size[0] > 1080 and -big.size[1] / 4 < y < 60
        quiet, loud = big.frame(0, [0, 0, 0]), big.frame(15, [15, 15, 15])
        assert len(quiet) == big.size[0] * big.size[1] * 4 and quiet != loud


@pytest.mark.asyncio
async def test_branded_export_plays_intro_clip_and_end_card(tmp_path):
    found = Assets.load()
    clip = _clip(tmp_path / "clip.mp4", "360x640", 2, "sine=f=440:d=2")
    out = await apply_branding(clip, tmp_path / "branded.mp4")
    probe = _probe(out)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (360, 640)
    assert any(s["codec_type"] == "audio" for s in probe["streams"])
    assert float(probe["format"]["duration"]) == pytest.approx(found.intro_s + 2 + found.outro_s, abs=0.3)
    assert np.isfinite(float(probe["format"]["duration"]))
