from __future__ import annotations

import pytest

from subtitle_styling.ass_generator import TITLE_SECONDS, ass_filter, AssGenerator, ass_time, burn_filter_args
from subtitle_styling.service import SubtitleStylingService


def dialogue_lines(ass: str) -> list[str]:
    return [line for line in ass.splitlines() if line.startswith("Dialogue")]


def caption_lines(ass: str) -> list[str]:
    return [line for line in dialogue_lines(ass) if ",Caption," in line]


def start_of(line: str) -> str:
    return line.split(",")[1]


@pytest.fixture
def offset_segments() -> list[dict]:
    """A clip covering source time 30s-40s, with absolute word timings."""
    return [{
        "start": 30.0, "end": 40.0, "text": "one two three four",
        "words": [
            {"start": 31.0, "end": 31.5, "word": "one"},
            {"start": 33.0, "end": 33.5, "word": "two"},
            {"start": 36.0, "end": 36.5, "word": "three"},
            {"start": 39.0, "end": 39.5, "word": "four"},
        ],
    }]


class TestAssTimebase:
    def test_words_are_relative_to_clip_start(self, offset_segments) -> None:
        """Regression: cue times must be clip-relative.

        The burn input is the already-cut clip, whose timeline starts at zero,
        so an absolute word time must be rebased or the captions drift by the
        clip's offset into the source.
        """
        words = SubtitleStylingService._extract_words_for_ass(offset_segments)
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, style_id="hormozi")
        first = caption_lines(ass)[0]
        assert start_of(first) == ass_time(1.0)

    def test_no_cue_starts_before_zero(self, offset_segments) -> None:
        words = SubtitleStylingService._extract_words_for_ass(offset_segments)
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, style_id="hormozi")
        for line in dialogue_lines(ass):
            assert not start_of(line).startswith("-")

    def test_no_cue_past_clip_end(self, offset_segments) -> None:
        words = SubtitleStylingService._extract_words_for_ass(offset_segments)
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, style_id="hormozi")
        for line in caption_lines(ass):
            end = line.split(",")[2]
            assert end <= ass_time(10.0)

    def test_words_outside_clip_are_excluded(self) -> None:
        segments = [{
            "start": 0.0, "end": 100.0, "text": "before inside after",
            "words": [
                {"start": 5.0, "end": 5.5, "word": "before"},
                {"start": 35.0, "end": 35.5, "word": "inside"},
                {"start": 80.0, "end": 80.5, "word": "after"},
            ],
        }]
        words = SubtitleStylingService._extract_words_for_ass(segments)
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, style_id="hormozi")
        assert "INSIDE" in ass.upper()
        assert "BEFORE" not in ass.upper()
        assert "AFTER" not in ass.upper()

    def test_zero_offset_clip_unchanged(self, offset_segments) -> None:
        segments = [{
            "start": 0.0, "end": 10.0, "text": "one",
            "words": [{"start": 1.0, "end": 1.5, "word": "one"}],
        }]
        words = SubtitleStylingService._extract_words_for_ass(segments)
        ass = AssGenerator().build_ass(words, clip_start=0.0, clip_end=10.0, style_id="hormozi")
        assert start_of(caption_lines(ass)[0]) == ass_time(1.0)


class TestBurnCommand:
    @staticmethod
    def _cmd(tmp_path, duration: float = 5.0, timeline=None) -> list[str]:
        return SubtitleStylingService._encode_cmd(
            video_path="clip.mp4",
            output_path=str(tmp_path / "out.mp4"),
            video_filters=[ass_filter(str(tmp_path / "captions.ass"))],
            duration=duration,
            timeline=timeline,
        )

    def test_command_does_not_seek_the_cut_clip(self, tmp_path) -> None:
        """Regression: -ss on an already-cut clip seeks past its end."""
        cmd = self._cmd(tmp_path, duration=10.0)
        assert "-ss" not in cmd
        assert cmd[cmd.index("-t") + 1] == "10.0"

    def test_ass_referenced_by_bare_filename(self, tmp_path) -> None:
        """libass resolves the path against cwd, which is the work dir."""
        cmd = self._cmd(tmp_path)
        graph = cmd[cmd.index("-vf") + 1]
        assert "ass=captions.ass" in graph
        assert str(tmp_path) not in graph

    def test_burn_reads_only_the_clip(self, tmp_path) -> None:
        """The watermark is added by the branding pass, not burned here."""
        cmd = self._cmd(tmp_path)
        assert cmd.count("-i") == 1 and cmd[cmd.index("-i") + 1] == "clip.mp4"

    def test_captions_ride_on_the_bridge_timeline(self, tmp_path) -> None:
        """With a hook transition the captions apply to the re-laid clip and
        its rebuilt audio is mapped, not the input's."""
        timeline = (["[0:v]null[vcat]", "[0:a]anull[acat]"], "vcat", "acat")
        cmd = self._cmd(tmp_path, timeline=timeline)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert graph.startswith("[0:v]null[vcat];[0:a]anull[acat];[vcat]ass=captions.ass") and graph.endswith("[v]")
        assert cmd[cmd.index("-map") + 1] == "[v]" and "[acat]" in cmd

    def test_plain_burn_is_a_simple_filter(self) -> None:
        assert burn_filter_args(["ass=captions.ass"]) == ["-vf", "ass=captions.ass"]


class TestStaticTitle:
    """The title is a headline, not a caption: one sentence, pinned on top."""

    def _title_line(self, ass: str) -> str:
        """The title's first line; every line of it shares that line's timing."""
        titles = [line for line in dialogue_lines(ass) if ",Title," in line]
        assert titles and len({start_of(line) + line.split(",")[2] for line in titles}) == 1
        return titles[0]

    def test_title_holds_for_the_opening_seconds(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=40.0, title="One sentence headline",
        )
        line = self._title_line(ass)
        assert start_of(line) == ass_time(0)
        assert line.split(",")[2] == ass_time(TITLE_SECONDS)

    def test_title_never_outlasts_a_short_clip(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=33.0, title="One sentence headline",
        )
        assert self._title_line(ass).split(",")[2] == ass_time(3.0)

    def test_title_sits_on_a_card_behind_it(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=40.0, title="One sentence headline",
        )
        card = next(line for line in dialogue_lines(ass) if ",TitleCard," in line)
        assert "\\p1}m " in card
        assert int(card.split(",")[0].split(": ")[1]) < int(self._title_line(ass).split(",")[0].split(": ")[1])

    def test_title_is_top_aligned(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=40.0, title="One sentence headline",
        )
        style = next(line for line in ass.splitlines() if line.startswith("Style: Title,"))
        # Field 18 of an ASS style is Alignment; 8 is top-centre.
        assert style.split(",")[18] == "8"

    def test_captions_sit_on_the_seam_while_two_people_are_stacked(self, offset_segments) -> None:
        words = SubtitleStylingService._extract_words_for_ass(offset_segments)
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, seams=[(0.0, 2.0, 0.5)])
        captions = [line for line in dialogue_lines(ass) if ",Caption," in line]
        on_seam = [line for line in captions if "\\pos(540,960)" in line]
        assert on_seam and all(float(start_of(line).split(":")[-1]) < 2.0 for line in on_seam)
        assert any("\\pos(540,960)" not in line for line in captions)

    def test_no_caption_line_runs_out_of_a_stack(self) -> None:
        words = [{"start": 30.0 + i * 0.3, "end": 30.25 + i * 0.3, "text": w} for i, w in enumerate("a b c d e f".split())]
        ass = AssGenerator().build_ass(words, clip_start=30.0, clip_end=40.0, seams=[(0.0, 0.8, 0.5)])
        for line in (line for line in dialogue_lines(ass) if ",Caption," in line):
            on_seam = "\\pos(540,960)" in line
            assert on_seam == (float(start_of(line).split(":")[-1]) < 0.8)
            # Words after the stack ends are never drawn on a line placed on its seam.
            assert not (on_seam and any(word in line for word in ("}D{", "}E{", "}F{")))

    def test_no_title_cue_without_a_title(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=40.0, title=None,
        )
        assert not [line for line in dialogue_lines(ass) if ",Title," in line]

    def test_captions_still_render_alongside_the_title(self, offset_segments) -> None:
        ass = AssGenerator().build_ass(
            SubtitleStylingService._extract_words_for_ass(offset_segments),
            clip_start=30.0, clip_end=40.0, title="One sentence headline",
        )
        assert caption_lines(ass)
