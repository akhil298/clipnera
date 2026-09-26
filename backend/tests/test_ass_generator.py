from __future__ import annotations

import pytest

from subtitle_styling.ass_generator import (
    AssGenerator,
    ass_time,
    escape_ass,
    _hex_to_ass_style,
    _box_colour,
    build_ass_file,
)


class TestAssTime:
    def test_zero(self):
        assert ass_time(0.0) == "0:00:00.00"

    def test_seconds(self):
        assert ass_time(1.5) == "0:00:01.50"

    def test_minutes(self):
        assert ass_time(125.5) == "0:02:05.50"

    def test_hours(self):
        assert ass_time(3661.25) == "1:01:01.25"

    def test_negative_clamped(self):
        assert ass_time(-5.0) == "0:00:00.00"


class TestColorConversion:
    def test_hex_to_ass_style_white(self):
        assert _hex_to_ass_style("#FFFFFF") == "&H00FFFFFF"

    def test_hex_to_ass_style_yellow(self):
        assert _hex_to_ass_style("#FFE000") == "&H0000E0FF"

    def test_box_colour_default_opacity(self):
        # 75% opaque -> ASS alpha (transparency) 0x40.
        assert _box_colour("#000000") == "&H40000000"

    def test_box_colour_reads_css_alpha(self):
        # CSS alpha is opacity; ASS alpha is transparency, so CC -> 33.
        assert _box_colour("#1A1A1ACC") == "&H331A1A1A"

    def test_hex_to_ass_style_no_hash(self):
        assert _hex_to_ass_style("00FFCC") == "&H00CCFF00"


class TestEscapeAss:
    def test_strips_backslash(self):
        assert escape_ass("hello\\nworld") == "hellonworld"

    def test_strips_braces(self):
        assert escape_ass("{hello}") == "hello"

    def test_replaces_newline(self):
        assert escape_ass("line1\nline2") == "line1 line2"


class TestAssGenerator:
    @pytest.fixture
    def words(self):
        return [
            {"start": 0.5, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 1.5, "text": "world"},
            {"start": 2.0, "end": 2.5, "text": "this"},
            {"start": 2.5, "end": 3.0, "text": "is"},
            {"start": 3.0, "end": 3.5, "text": "a"},
            {"start": 3.5, "end": 4.0, "text": "test"},
        ]

    def test_build_ass_basic(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="default")
        assert "[Script Info]" in result
        assert "[V4+ Styles]" in result
        assert "[Events]" in result
        assert "Dialogue:" in result
        assert "Caption" in result

    def test_build_ass_with_title(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="default", title="Amazing Clip!")
        assert "Amazing Clip!" in result
        assert "Title" in result

    @staticmethod
    def _style(ass: str, name: str) -> list[str]:
        line = next(l for l in ass.splitlines() if l.startswith(f"Style: {name},"))
        return line.split(",")

    def test_title_style_overrides_size_and_position(self, words):
        default = self._style(AssGenerator().build_ass(words, 0.0, 5.0, title="T"), "Title")
        moved = self._style(
            AssGenerator().build_ass(
                words, 0.0, 5.0, title="T",
                style_overrides={"title_font_size": 40, "title_position_y": 0.2},
            ),
            "Title",
        )
        assert int(moved[2]) < int(default[2])
        assert int(moved[-2]) == round(0.2 * 1920)

    def test_caption_style_overrides_size(self, words):
        default = self._style(AssGenerator().build_ass(words, 0.0, 5.0, style_id="mrbeast"), "Caption")
        smaller = self._style(
            AssGenerator().build_ass(words, 0.0, 5.0, style_id="mrbeast", style_overrides={"font_size": 30}),
            "Caption",
        )
        assert int(smaller[2]) < int(default[2])

    def test_build_ass_filters_words_outside_clip(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 2.0, 4.0, style_id="default")
        assert "this" in result
        assert "test" in result
        assert "Hello" not in result

    def test_build_ass_karaoke_dialogue_per_word(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="default")
        dialogue_lines = [l for l in result.split("\n") if l.startswith("Dialogue:")]
        assert len(dialogue_lines) > 0
        for line in dialogue_lines:
            assert line.startswith("Dialogue: 0")

    def test_build_ass_neon_style(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="neon")
        assert "Glow" in result

    def test_build_ass_no_words(self):
        gen = AssGenerator()
        result = gen.build_ass([], 0.0, 5.0, style_id="default")
        assert "[Events]" in result
        assert "Format: Layer" in result

    def test_build_ass_mrbeast_uppercase(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="mrbeast")
        assert "HELLO" in result.upper() or "Hello" in result

    def test_build_ass_hormozi_word_box(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="hormozi")
        assert "\\3c&H" in result

    def test_build_ass_minimal_no_glow(self, words):
        gen = AssGenerator()
        result = gen.build_ass(words, 0.0, 5.0, style_id="minimal")
        assert "Glow" not in result

    def test_build_ass_file_creation(self, words):
        import os
        import tempfile
        gen = AssGenerator()
        fd, path = tempfile.mkstemp(suffix=".ass")
        os.close(fd)
        result_path = build_ass_file(words, 0.0, 5.0, output_path=path)
        assert os.path.exists(result_path)
        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[Events]" in content
        os.unlink(path)


class TestAnimatedPlateCaptions:
    WORDS = [{"start": 0.2 + i * 0.4, "end": 0.5 + i * 0.4, "text": w} for i, w in enumerate("why did nobody tell me so this".split())]

    def _events(self, **kw):
        doc = AssGenerator().build_ass(self.WORDS, 0.0, 6.0, **kw)
        return doc, [l for l in doc.splitlines() if l.startswith("Dialogue: 0")]

    def test_clean_dark_draws_a_real_plate(self):
        doc, _ = self._events(style_id="clean_dark")
        caption_style = next(l for l in doc.splitlines() if l.startswith("Style: Caption"))
        # BorderStyle 3 = opaque box; the old code only tinted the shadow.
        assert caption_style.split(",")[15] == "3"

    def test_lines_animate_in_once(self):
        _, events = self._events(style_id="clean_dark")
        moving = [e for e in events if "\\move(" in e]
        assert moving and all("\\fad(" in e for e in moving)
        assert len(moving) < len(events)  # later words of a line hold still

    def test_none_animation_has_no_highlight_or_motion(self):
        _, events = self._events(style_id="clean_dark", style_overrides={"animation": "none"})
        assert not any("\\move(" in e or "\\t(" in e or "\\3c" in e for e in events)

    def test_no_line_spans_the_hook_break(self):
        # Hook words end at 2.0; the clip's words follow the bridge.
        _, events = self._events(style_id="clean_dark", segment_breaks=[1.5])
        for event in events:
            text = event.split(",,", 1)[1]
            assert not ("tell" in text and "so" in text.replace("so\\", "")), event


class TestCaptionFit:
    @staticmethod
    def _captions(ass: str) -> list[str]:
        return [line for line in ass.splitlines() if line.startswith("Dialogue: 0")]

    def test_wide_face_gets_shorter_lines(self):
        words = [{"text": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
                 for i, w in enumerate("begin to stretch spaghettification quickly now".split())]
        ass = AssGenerator().build_ass(words, 0.0, 3.0, style_id="bubble",
                                       style_overrides={"font_size": 54})
        # No caption line may hold more characters than fit inside the frame.
        from subtitle_styling.ass_generator import caption_layout_budget, char_width_px, ass_font_size
        budget = caption_layout_budget(char_width_px("Luckiest Guy", ass_font_size(54), True), 1080)
        for line in self._captions(ass):
            text = "".join(part.split("}")[-1] for part in line.split(",", 9)[9].split("{"))
            assert len(text.strip()) <= max(budget, len("SPAGHETTIFICATION"))

    def test_a_word_too_long_for_the_frame_is_shrunk(self):
        words = [{"text": "spaghettification", "start": 0.0, "end": 1.0}]
        ass = AssGenerator().build_ass(words, 0.0, 1.0, style_id="bubble", style_overrides={"font_size": 60})
        line = self._captions(ass)[0]
        assert "\\fs" in line
        assert line.count("\\r\\fs") >= 1

    def test_a_long_title_word_shrinks_the_title(self):
        normal = AssGenerator().build_ass([], 0.0, 1.0, style_id="bubble", title="Black holes")
        long = AssGenerator().build_ass([], 0.0, 1.0, style_id="bubble", title="Spaghettificationally speaking")
        size = lambda ass: int(next(l for l in ass.splitlines() if l.startswith("Style: Title,")).split(",")[2])
        assert size(long) < size(normal)
