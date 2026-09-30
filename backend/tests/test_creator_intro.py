from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from creator_intro.copy import TAGLINE_MAX, clean_tagline, parse, user_prompt
from creator_intro.platforms import PLATFORM_LOOKS, look_for
from creator_intro.render import (
    DURATION_S, HEART, THUMB, IntroSpec, Layout, _font, draw_frame, path_polygons, prepend_cmd, render, wrap,
)
from hook_transitions.graph import MediaInfo
from subscription.entitlements import entitlements_for
from subscription.model import PlanSlug


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _spec(platform: str = "youtube", **changes) -> IntroSpec:
    base = dict(name="Sreekanth Go", tagline="Travel, temples and waterfalls across Andhra Pradesh",
                look=look_for(platform))
    return IntroSpec(**{**base, **changes})


class TestPlans:
    def test_free_is_locked_out(self):
        free = entitlements_for(PlanSlug.FREE.value)
        assert free.allows("creator_intro") is False
        assert free.daily_limit("intro_renders") == 0

    @pytest.mark.parametrize("plan", [PlanSlug.PRO.value, PlanSlug.PRO_PLUS.value])
    def test_paid_plans_get_it(self, plan):
        paid = entitlements_for(plan)
        assert paid.allows("creator_intro") is True
        assert paid.daily_limit("intro_renders") == 5


class TestPlatforms:
    def test_youtube_is_red_subscribe(self):
        look = look_for("youtube")
        assert (look.action, look.done, look.accent, look.like_icon) == ("Subscribe", "Subscribed", "#FF0000", "thumb")

    def test_other_wears_the_brand_colour_with_readable_text(self):
        assert look_for("other", "#FFE066").accent_text == "#0B0B0B"
        assert look_for("other", "#1E1B4B").accent_text == "#FFFFFF"

    def test_brand_colour_never_overrides_a_real_platform(self):
        assert look_for("tiktok", "#123456").accent == PLATFORM_LOOKS["tiktok"].accent


class TestCopy:
    def test_valid_answer(self):
        copy = parse('{"tagline": "Late-night Valorant clutches", "theme": "dark"}', "", "gaming")
        assert (copy.tagline, copy.theme) == ("Late-night Valorant clutches", "dark")

    def test_unknown_theme_falls_back_to_light(self):
        assert parse('{"tagline": "x", "theme": "neon"}', "", None).theme == "light"

    def test_unreadable_answer_uses_the_creators_words(self):
        copy = parse("sorry, I can't", "Street food tours in Hyderabad. New videos weekly", "food")
        assert copy.tagline == "Street food tours in Hyderabad"

    def test_long_line_is_cut_at_a_word(self):
        line = clean_tagline("word " * 40)
        assert len(line) <= TAGLINE_MAX + 1 and line.endswith("…") and "  " not in line

    def test_prompt_names_the_platform(self):
        assert "Platform: TikTok" in user_prompt("tiktok", None, "NightOwl", "valorant")


class TestDrawing:
    @pytest.mark.parametrize("path", [THUMB, HEART])
    def test_icon_paths_stay_in_the_box(self, path):
        points = [p for shape in path_polygons(path) for p in shape]
        assert points and all(-0.5 <= x <= 24.5 and -0.5 <= y <= 24.5 for x, y in points)

    def test_wrap_keeps_two_lines(self):
        font = _font("a", "Regular", 38)
        lines = wrap("one two three four five six seven eight nine ten " * 4, font, 400)
        assert len(lines) == 2 and lines[-1].endswith("…")

    @pytest.mark.parametrize("platform", list(PLATFORM_LOOKS))
    @pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (1080, 1080)])
    def test_every_platform_and_size_draws(self, platform, size):
        layout = Layout.build(_spec(platform, handle="@sreekanthgo"), *size)
        for t in (0.0, 1.0, 2.7, 3.7, 5.9):
            assert draw_frame(t, layout).size == size

    def test_buttons_fit_inside_the_frame(self):
        layout = Layout.build(_spec(name="A very long channel name that keeps going"), 1080, 1920)
        width = layout.size[0]
        assert 0 < layout.like_center[0] < layout.action_center[0] < width

    def test_dark_x_button_stays_visible(self):
        """X's near-black Follow would vanish on the dark page, so it takes the page's text colour."""
        assert Layout.build(_spec("x", theme="dark"), 1080, 1080).accent == "#F1F1F1"

    def test_non_latin_names_render(self):
        layout = Layout.build(_spec(name="శ్రీకాంత్ గో", tagline="ప్రయాణాలు, దేవాలయాలు"), 1080, 1920)
        assert draw_frame(1.5, layout).getbbox()


class TestVideo:
    def test_render_makes_a_six_second_clip_with_sound(self, tmp_path):
        out = render(_spec(), "9x16", tmp_path / "intro.mp4", tmp_path)
        info = _probe(out)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == (1080, 1920)
        assert any(s["codec_type"] == "audio" for s in info["streams"])
        assert abs(float(info["format"]["duration"]) - DURATION_S) < 0.15

    @pytest.mark.parametrize("has_audio", [True, False])
    def test_prepend_puts_the_intro_first_at_the_clips_size(self, tmp_path, has_audio):
        intro = render(_spec(), "16x9", tmp_path / "intro.mp4", tmp_path)
        clip = tmp_path / "clip.mp4"
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=720x1280:r=25:d=2"]
        if has_audio:
            cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:a", "aac"]
        subprocess.run([*cmd, "-pix_fmt", "yuv420p", str(clip)], check=True)
        media = MediaInfo(width=720, height=1280, fps=25.0, duration=2.0, has_audio=has_audio)
        out = tmp_path / "out.mp4"
        subprocess.run(prepend_cmd(str(intro), clip, out, media), check=True)
        info = _probe(out)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == (720, 1280)
        assert abs(float(info["format"]["duration"]) - (DURATION_S + 2.0)) < 0.2
