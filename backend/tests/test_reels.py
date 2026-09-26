from __future__ import annotations

import json
import subprocess
import pytest

from reels import planner
from reels.jobs import spoken_language
from reels.planner import Scene, scenes_from_json, scenes_to_json, split_scenes, validate_visuals
from reels.service import render_credits
from reels.voice import chunks, reading_timings


def words_for(text: str, gap: float = 0.4) -> list[dict]:
    return [{"start": round(i * gap, 3), "end": round(i * gap + 0.35, 3), "word": w} for i, w in enumerate(text.split())]


class TestScenes:
    def test_scenes_cut_at_sentence_ends_and_play_back_to_back(self):
        # 0.6 s a word: every sentence is over the 2 s minimum, so each is its own scene.
        scenes = split_scenes(words_for("This habit changed my mornings. I wake at five every single day. Coffee first, then a walk.", gap=0.6))
        assert [s.text.split()[0] for s in scenes] == ["This", "I", "Coffee"]
        assert scenes[0].start == 0.0
        assert all(a.end == b.start for a, b in zip(scenes, scenes[1:]))

    def test_long_sentences_split_under_eight_seconds(self):
        scenes = split_scenes(words_for(" ".join(["word"] * 60) + "."))
        assert all(s.duration <= planner.MAX_SCENE_SECONDS + 0.5 for s in scenes)

    def test_a_short_tail_joins_the_last_scene(self):
        scenes = split_scenes(words_for("One two three four five six. Yes."))
        assert len(scenes) == 1 and scenes[0].text.endswith("Yes.")

    def test_json_round_trip(self):
        scenes = [Scene(0.0, 2.0, "hi", kind="broll", query="city", alternates=["a"])]
        assert scenes_from_json(scenes_to_json(scenes)) == scenes
        assert scenes_from_json("not json") == []


class TestVisuals:
    images = [{"description": "red sneaker"}, {"description": "founder smiling"}]

    def scenes(self, n):
        return [Scene(i * 3.0, (i + 1) * 3.0, f"s{i}") for i in range(n)]

    def test_valid_choices_are_kept(self):
        raw = {0: {"kind": "image", "image": 0}, 1: {"kind": "broll", "query": "city run", "subject": "city"},
               2: {"kind": "text", "headline": "3x sales"}}
        out = validate_visuals(self.scenes(3), self.images, raw)
        assert [(s.kind, s.image_index, s.query, s.headline) for s in out] == [
            ("image", 0, "", ""), ("broll", None, "city run", ""), ("text", None, "", "3x sales")]

    def test_bad_choices_fall_back_to_unused_images(self):
        raw = {0: {"kind": "image", "image": 1}, 1: {"kind": "image", "image": 1}, 2: {"kind": "image", "image": 9}}
        out = validate_visuals(self.scenes(3), self.images, raw)
        # Never the same image twice in a row; the unused image comes in first.
        assert [s.image_index for s in out] == [1, 0, 1]

    def test_no_images_means_text_cards(self):
        out = validate_visuals(self.scenes(1), [], {})
        assert out[0].kind == "text" and out[0].headline == "s0"

    @pytest.mark.asyncio
    async def test_an_unreadable_answer_still_gives_a_plan(self):
        class Client:
            async def chat(self, messages, **kwargs):
                return "sorry"

        out = await planner.assign_visuals(self.scenes(2), self.images, Client())
        assert [s.kind for s in out] == ["image", "image"]


class TestVoice:
    def test_chunks_respect_the_limit_and_keep_every_word(self):
        script = "Short one. " + "word " * 80 + "end."
        pieces = chunks(script, limit=60)
        assert all(len(p) <= 60 for p in pieces)
        assert " ".join(pieces).split() == script.split()

    def test_reading_timings_pause_at_sentence_ends(self):
        timed = reading_timings("Hello there. Next")
        assert timed[1]["end"] < timed[2]["start"] - 0.3
        assert all(w["end"] > w["start"] for w in timed)

    @pytest.mark.parametrize(("language", "spoken"), [("hinglish", "hi"), ("tenglish", "te"), ("Telugu", "te"), ("en", "en"), ("xx-yy", "en")])
    def test_spoken_language(self, language, spoken):
        assert spoken_language(language.lower()) == spoken


class TestPricing:
    @pytest.mark.parametrize(("seconds", "credits"), [(15, 18), (30, 25), (60, 40), (90, 55)])
    def test_matches_the_published_table(self, seconds, credits):
        assert render_credits(seconds) == credits


class TestRender:
    def _frames(self, path) -> int:
        out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                              "stream=nb_read_frames,width,height", "-of", "json", str(path)], capture_output=True, text=True).stdout
        stream = json.loads(out)["streams"][0]
        return int(stream["nb_read_frames"]), stream["width"], stream["height"]

    def test_text_card_in_every_script(self, tmp_path):
        from PIL import Image

        from reels.render import STYLES, text_card

        for index, headline in enumerate(["3x more sales", "బాగున్నాను", "नमस्ते दोस्तों"]):
            card = text_card(headline, STYLES["bold"], tmp_path / f"c{index}.png")
            image = Image.open(card)
            assert image.size == (1080, 1920)
            # Something was drawn: the card is not a flat background.
            assert len(set(image.convert("L").getdata())) > 2

    @pytest.mark.asyncio
    async def test_scene_parts_have_exact_length_and_join(self, tmp_path):
        from PIL import Image

        from reels.render import FPS, footage_cmd, join, still_cmd
        from broll.renditions import run

        photo = tmp_path / "p.jpg"
        Image.new("RGB", (800, 600), "orange").save(photo)
        clip = tmp_path / "shot.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=1080x1920:r=30:d=1",
                        "-pix_fmt", "yuv420p", str(clip)], check=True)
        a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
        await run(still_cmd(photo, 2.0, a, blur_fill=True))
        await run(footage_cmd(clip, 2.5, b))  # a 1 s shot looped to 2.5 s
        assert self._frames(a) == (2 * FPS, 1080, 1920)
        assert self._frames(b)[0] == pytest.approx(2.5 * FPS, abs=1)
        out = tmp_path / "reel.mp4"
        await join([a, b], None, out)
        frames, width, height = self._frames(out)
        assert (width, height) == (1080, 1920) and frames == pytest.approx(4.5 * FPS, abs=2)
        audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name",
                                "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
        assert audio == "aac"

    @pytest.mark.asyncio
    async def test_finish_without_captions_or_watermark_is_a_no_op(self, tmp_path):
        from reels.render import finish

        video = tmp_path / "v.mp4"
        assert await finish(video, None, False, tmp_path / "out.mp4") == video


class TestCaptionFontSwitchUsesCaptionWords:
    def test_reel_words_are_converted_for_captions(self):
        from subtitle_styling.ass_generator import AssGenerator

        ass = AssGenerator().build_ass([{"start": 0.0, "end": 1.0, "text": "नमस्ते"}], 0.0, 1.0, width=1080, height=1920)
        assert "Noto Sans Devanagari" in ass and "Dialogue:" in ass



class TestRepeats:
    def test_a_repeat_after_a_footage_fallback_is_replaced(self):
        from reels.planner import avoid_repeats

        scenes = [Scene(0, 3, "a", kind="image", image_index=0), Scene(3, 6, "b", kind="image", image_index=0)]
        avoid_repeats(scenes, [{"d": 1}, {"d": 2}])
        assert [s.image_index for s in scenes] == [0, 1]

    def test_one_image_repeat_becomes_a_text_card(self):
        from reels.planner import avoid_repeats

        scenes = [Scene(0, 3, "a", kind="image", image_index=0), Scene(3, 6, "big news here", kind="image", image_index=0)]
        avoid_repeats(scenes, [{"d": 1}])
        assert scenes[1].kind == "text" and scenes[1].headline == "big news here"


class TestSceneColours:
    @pytest.mark.asyncio
    async def test_every_part_is_tagged_the_same(self, tmp_path):
        from PIL import Image

        from broll.renditions import run
        from reels.render import STYLES, still_cmd, text_card

        Image.new("RGB", (640, 480), "orange").save(tmp_path / "p.jpg")
        await run(still_cmd(tmp_path / "p.jpg", 1.0, tmp_path / "a.mp4", blur_fill=True))
        await run(still_cmd(text_card("hi", STYLES["clean"], tmp_path / "c.png"), 1.0, tmp_path / "b.mp4", blur_fill=False))
        tags = {
            subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=pix_fmt,color_range,color_space", "-of", "csv=p=0",
                            str(tmp_path / name)], capture_output=True, text=True).stdout.strip()
            for name in ("a.mp4", "b.mp4")
        }
        assert tags == {"yuv420p,tv,bt709"}
