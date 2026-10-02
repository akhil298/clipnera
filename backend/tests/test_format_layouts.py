"""Layouts chosen per short-form format, their fallbacks, and their renders."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from formats.taxonomy import VisualEvidence
from video_processor.clip_cutter import ClipCutter, CutRequest, _roam, _stack_seams
from video_processor.editing import (
    FOCUS_MIN_WIDTH,
    RHYTHM_MIN_SECONDS,
    Cell,
    FormatContext,
    Layout,
    Part,
    choose_layout,
    framing_stretches,
    plan_parts,
    rhythm_seconds,
    speaker_turns,
)
from video_processor.face_detection import Face
from video_processor.focus import activity_boxes, key_colour, salient_boxes
from video_processor.geometry import Box
from video_processor.speaker_tracking import FaceSample, SpeakerTrack

HAS_FFMPEG = shutil.which("ffmpeg") is not None
SIZE = ("9:16", 1920, 1080, 1080, 1920)


def _track(track_id: int, box: Box, samples: int = 30, step: float = 0.1) -> SpeakerTrack:
    face = Face(box=box, confidence=0.9, mouth=box)
    return SpeakerTrack(track_id, [FaceSample(round(i * step, 3), face) for i in range(samples)])


def _layout(fmt: str, tracks: list[SpeakerTrack], evidence: VisualEvidence | None = None,
            focus: list[tuple[float, Box | None]] | None = None, pair=None, aspect: str = "9:16",
            hint: str = "auto") -> Layout:
    context = FormatContext(content_format=fmt, evidence=evidence, focus=tuple(focus or ()))
    width, height = (1080, 1920) if aspect == "9:16" else (1080, 1080)
    return choose_layout(hint, "single_subject", tracks, aspect, 1920, 1080, width, height,
                         pair=pair, context=context)


FACECAM = Box(0.82, 0.72, 0.08, 0.14)
PRESENTER = Box(0.4, 0.2, 0.2, 0.35)


class TestReaction:
    def test_content_on_top_of_the_reactor(self):
        evidence = VisualEvidence(facecam=0.8, content_box=(0.0, 0.0, 0.78, 1.0))
        layout = _layout("reaction", [_track(1, FACECAM)], evidence)
        assert layout.kind == "reaction_stack"
        content, face = layout.cells
        assert content.fill == "fit" and content.box == Box(0.0, 0.0, 0.78, 1.0)
        assert face.box.x <= FACECAM.x and face.box.x + face.box.width >= FACECAM.x + FACECAM.width
        assert content.height + face.height == 1920

    def test_without_a_content_box_the_largest_clear_region_is_shown(self):
        layout = _layout("reaction", [_track(1, Box(0.1, 0.2, 0.15, 0.3))])
        assert layout.kind == "reaction_stack"
        content = layout.cells[0].box
        assert content.x >= 0.4 and content.x + content.width == pytest.approx(1.0)

    def test_nobody_reacting_shows_the_frame_whole(self):
        assert _layout("reaction", [], VisualEvidence(content_box=(0, 0, 1, 1))).kind == "fit"

    def test_a_face_filling_the_frame_is_followed(self):
        assert _layout("reaction", [_track(1, Box(0.3, 0.05, 0.4, 0.6))]).kind == "follow"

    def test_talking_head_ignores_the_evidence(self):
        evidence = VisualEvidence(facecam=0.8, content_box=(0.0, 0.0, 0.78, 1.0))
        assert _layout("talking_head", [_track(1, FACECAM)], evidence).kind == "follow"

    def test_other_shapes_follow(self):
        evidence = VisualEvidence(facecam=0.8, content_box=(0.0, 0.0, 0.78, 1.0))
        assert _layout("reaction", [_track(1, FACECAM)], evidence, aspect="1:1").kind == "follow"


def _typing(centre: tuple[float, float], size: float = 0.06, samples: int = 30) -> list[tuple[float, Box | None]]:
    """Activity samples: a small box changing around ``centre``, with still gaps."""
    box = Box(centre[0] - size / 2, centre[1] - size / 4, size, size / 2)
    return [(round(i / 6, 3), box if i % 3 else None) for i in range(samples)]


class TestScreenFocus:
    def test_zooms_on_what_changes(self):
        layout = _layout("screen_share", [], VisualEvidence(screen=0.9), _typing((0.3, 0.6)))
        assert layout.kind == "screen_focus" and len(layout.cells) == 1
        cell = layout.cells[0]
        assert cell.roam == Box() and cell.height == 1920
        assert cell.box.x < 0.3 < cell.box.x + cell.box.width
        assert cell.box.width >= FOCUS_MIN_WIDTH - 1e-9
        assert cell.box.width * 1920 / (cell.box.height * 1080) == pytest.approx(1080 / 1920, rel=1e-3)

    def test_webcam_sits_below_the_screen(self):
        evidence = VisualEvidence(screen=0.9, facecam=0.9, content_box=(0.0, 0.0, 0.8, 1.0))
        layout = _layout("screen_share", [_track(1, FACECAM)], evidence, _typing((0.3, 0.4)))
        assert layout.kind == "screen_focus"
        screen, webcam = layout.cells
        assert screen.roam == Box(0.0, 0.0, 0.8, 1.0)
        assert screen.box.x + screen.box.width <= 0.8 + 1e-9
        assert screen.height > webcam.height and screen.height + webcam.height == 1920
        assert layout.seam == pytest.approx(screen.height / 1920)

    def test_a_whole_slide_changing_shows_the_whole_screen(self):
        slides = [(i / 6, Box(0.05, 0.05, 0.9, 0.9)) for i in range(30)]
        cell = _layout("screen_share", [], VisualEvidence(screen=0.9), slides).cells[0]
        assert cell.fill == "fit" and cell.roam is None

    def test_a_still_screen_is_shown_whole(self):
        cell = _layout("screen_share", [], VisualEvidence(screen=0.9), [(0.0, None), (0.2, None)]).cells[0]
        assert cell.fill == "fit"

    def test_a_presenter_filling_the_shot_is_followed(self):
        assert _layout("screen_share", [_track(1, PRESENTER)], VisualEvidence(screen=0.9),
                       _typing((0.3, 0.6))).kind == "follow"

    def test_the_window_holds_still_while_nothing_changes(self):
        layout = _layout("screen_share", [], VisualEvidence(screen=0.9), _typing((0.3, 0.6)))
        focus = [(i / 6, Box(0.25, 0.55, 0.05, 0.03) if i < 6 else None) for i in range(30)]
        cell = _roam(layout.cells[0], tuple(focus), 1920, 1080)
        later = [(x, y) for t, x, y in cell.path if t >= 2.0]
        assert len(set(later)) == 1
        assert all(0.0 <= x <= 1.0 - cell.box.width + 1e-9 for _, x, _ in cell.path)


class TestGreenScreen:
    def test_a_green_screen_is_keyed_over_a_neutral_backdrop(self):
        layout = _layout("green_screen", [_track(1, PRESENTER)], VisualEvidence(green=0.7))
        assert layout.kind == "green_screen" and layout.key
        backdrop, person = layout.cells
        assert backdrop.fill == "blur" and backdrop.height == 1920
        assert person.fill == "key" and person.box.x < 0.5 < person.box.x + person.box.width
        assert layout.seam is None

    def test_the_graphic_behind_is_the_backdrop(self):
        evidence = VisualEvidence(green=0.7, graphic_backdrop=0.6, content_box=(0.0, 0.0, 0.6, 0.6))
        backdrop = _layout("green_screen", [_track(1, PRESENTER)], evidence).cells[0]
        assert backdrop.fill == "fit" and backdrop.box == Box(0.0, 0.0, 0.6, 0.6)

    def test_an_already_composited_screen_is_stacked(self):
        evidence = VisualEvidence(graphic_backdrop=0.8, content_box=(0.0, 0.0, 0.65, 1.0))
        layout = _layout("green_screen", [_track(1, Box(0.75, 0.3, 0.12, 0.2))], evidence)
        assert layout.kind == "green_screen" and layout.cells[0].fill == "fit" and layout.seam is not None

    @pytest.mark.parametrize("evidence", [None, VisualEvidence(green=0.05, graphic_backdrop=0.1)])
    def test_without_evidence_the_speaker_is_followed(self, evidence):
        assert _layout("green_screen", [_track(1, PRESENTER)], evidence).kind == "follow"

    def test_no_green_in_the_frames_is_never_keyed(self):
        context = FormatContext("green_screen", VisualEvidence(green=0.7), key_colour="")
        layout = choose_layout("auto", "single_subject", [_track(1, PRESENTER)], *SIZE, context=context)
        assert layout.kind == "follow"


class TestVoiceOver:
    def test_footage_is_cropped_on_what_stands_out(self):
        focus = [(i / 6, Box(0.65, 0.3, 0.12, 0.3)) for i in range(30)]
        layout = _layout("voice_over", [], VisualEvidence(face=0.0), focus)
        assert layout.kind == "voice_over"
        cell = layout.cells[0]
        assert cell.roam == Box() and cell.box.x < 0.71 < cell.box.x + cell.box.width

    def test_a_wide_subject_is_shown_whole(self):
        focus = [(i / 6, Box(0.1, 0.3, 0.7, 0.3)) for i in range(30)]
        assert _layout("voice_over", [], None, focus).kind == "fit"

    def test_someone_on_screen_is_followed(self):
        focus = [(i / 6, Box(0.65, 0.3, 0.12, 0.3)) for i in range(30)]
        assert _layout("voice_over", [_track(1, PRESENTER)], None, focus).kind == "follow"


class TestPairs:
    LEFT, RIGHT = Box(0.15, 0.3, 0.12, 0.2), Box(0.7, 0.3, 0.12, 0.2)

    def test_split_screen_stacks_a_pair(self):
        pair = [_track(1, self.LEFT), _track(2, self.RIGHT)]
        assert _layout("split_screen", pair, VisualEvidence(two_faces=0.8), pair=pair).kind == "two_speaker_stack"

    def test_split_screen_falls_back_to_facecam_over_gameplay(self):
        facecam = _track(1, Box(0.82, 0.05, 0.1, 0.15))
        assert _layout("split_screen", [facecam], VisualEvidence(facecam=0.9)).kind == "split_gameplay"
        # A small, still face with no facecam seen by the probe is just a wide shot.
        assert _layout("split_screen", [facecam], VisualEvidence(facecam=0.1)).kind == "follow"

    def test_a_pair_format_stacks_with_a_third_face_present(self):
        pair = [_track(1, self.LEFT, 40), _track(2, self.RIGHT, 40)]
        poster = _track(3, Box(0.45, 0.1, 0.05, 0.08), 20)
        turns = speaker_turns([0.0, 2.0, 3.9], [pair[0], pair[1], pair[1]])
        assert framing_stretches(0.0, 4.0, turns, 0.1, [], present=pair + [poster])[0][2] == []
        assert len(framing_stretches(0.0, 4.0, turns, 0.1, [], present=pair + [poster], any_pair=True)[0][2]) == 2

    def test_a_clone_exchange_needs_no_second_voice(self):
        """One creator playing both sides: one diarized voice, quick replies, two places."""
        a, b = _track(1, self.LEFT, 120), _track(2, self.RIGHT, 120)
        stamps = [i * 0.25 for i in range(49)]
        speakers = [a if int(t // 2) % 2 == 0 else b for t in stamps]
        turns = speaker_turns(stamps, speakers)
        one_voice = [{"start": 0.0, "end": 12.0, "text": "x", "speaker": "SPEAKER_00"}]
        present = [a, b, _track(3, Box(0.45, 0.1, 0.05, 0.08), 120)]  # a third face: no two-shot
        plain = framing_stretches(0.0, 12.0, turns, 0.1, one_voice, present=present)
        clone = framing_stretches(0.0, 12.0, turns, 0.1, one_voice, present=present, any_pair=True)
        assert not any(pair for _, _, pair in plain)
        assert any(pair for _, _, pair in clone)


class TestSeams:
    def test_every_stack_reports_its_seam(self):
        stack = Layout("reaction_stack", [Cell(Box(), 768, fill="fit"), Cell(Box(), 1152)])
        keyed = Layout("green_screen", [Cell(Box(), 1920, fill="blur"), Cell(Box(), 1190, fill="key")], key="0x00FF00")
        single = Layout("screen_focus", [Cell(Box(), 1920, roam=Box())])
        two = Layout("two_speaker_stack", [Cell(Box(), 960), Cell(Box(), 960)])
        shots = [(Part(0.0, 2.0), stack), (Part(5.0, 6.0), keyed), (Part(6.0, 7.0), single),
                 (Part(7.0, 8.0), Layout("follow")), (Part(8.0, 9.5), two)]
        assert _stack_seams(shots) == [(0.0, 2.0, 0.4), (5.0, 6.5, 0.5)]


class TestRhythm:
    def test_rhythm_per_format(self):
        assert rhythm_seconds("talking_head") == RHYTHM_MIN_SECONDS
        assert rhythm_seconds(None) == RHYTHM_MIN_SECONDS
        assert rhythm_seconds("yap") < RHYTHM_MIN_SECONDS
        assert rhythm_seconds("reaction") is None

    def test_no_rhythm_holds_one_framing_but_keeps_beats(self):
        starts = [2.0, 5.0, 9.0, 13.0, 16.0]
        beats = [{"t": 10.0, "fx": "punch_in"}]
        parts = plan_parts(0.0, 20.0, beats, lambda _t: None, starts, None)
        assert [p.zoom for p in parts] == [1.0, pytest.approx(1.2), 1.0]

    def test_yap_cuts_more_often(self):
        starts = [i * 2.0 for i in range(1, 10)]
        talking = plan_parts(0.0, 20.0, [], lambda _t: None, starts, rhythm_seconds("talking_head"))
        yap = plan_parts(0.0, 20.0, [], lambda _t: None, starts, rhythm_seconds("yap"))
        assert len(yap) > len(talking)


def _frame(draw=None, colour=(255, 255, 255)) -> np.ndarray:
    frame = np.full((360, 640, 3), colour, np.uint8)
    if draw:
        draw(frame)
    return frame


class TestFocusMeasurement:
    def test_activity_is_what_changed(self):
        frames = [(i / 6, _frame(lambda f, i=i: cv2.rectangle(f, (100 + 8 * i, 200), (130 + 8 * i, 215), (0, 0, 0), -1)))
                  for i in range(6)]
        samples = activity_boxes(frames, [])
        assert samples[0][1] is None
        box = samples[3][1]
        assert box is not None and 0.15 < box.center[0] < 0.25 and 0.5 < box.center[1] < 0.65

    def test_a_masked_face_and_a_cut_are_not_activity(self):
        frames = [(i / 6, _frame(lambda f, i=i: cv2.circle(f, (550, 300), 20 + 5 * (i % 2), (0, 0, 0), -1)))
                  for i in range(6)]
        assert all(box is None for _, box in activity_boxes(frames, [], lambda _t: [Box(0.8, 0.7, 0.12, 0.25)]))
        cut = [(0.0, _frame()), (0.2, _frame(colour=(0, 0, 0)))]
        assert activity_boxes(cut, [0.1])[1][1] is None

    def test_saliency_finds_the_subject(self):
        def subject(f, i=0):
            f[:] = (40, 60, 40)
            cv2.circle(f, (480 + 4 * i, 180), 30, (0, 220, 255), -1)
        samples = salient_boxes([(i / 6, _frame(lambda f, i=i: subject(f, i))) for i in range(4)], [])
        box = samples[-1][1]
        assert box is not None and box.center[0] > 0.6

    def test_key_colour_reads_the_screen(self):
        colour = key_colour([(0.0, _frame(colour=(60, 200, 40)))])
        assert colour is not None and colour.startswith("0x") and int(colour[4:6], 16) > 150
        assert key_colour([(0.0, _frame())]) is None


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
class TestFormatRenders:
    @staticmethod
    def _source(path: Path, video: str) -> Path:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", video,
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
        ], check=True)
        return path

    @pytest.fixture
    def source(self, tmp_path):
        return self._source(tmp_path / "src.mp4", "testsrc=size=640x360:rate=25:duration=2")

    @pytest.fixture
    def green(self, tmp_path):
        # A green screen with a "person" standing in the middle.
        return self._source(tmp_path / "green.mp4",
                            "color=c=0x30C040:size=640x360:rate=25:duration=2,"
                            "drawbox=x=270:y=80:w=100:h=280:color=0xC08060:t=fill")

    @staticmethod
    def _size(path) -> str:
        return subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, check=True,
        ).stdout.strip()

    @staticmethod
    def _cells(layout: Layout):
        from video_processor.clip_cutter import _path_tracking
        return [(cell.box.as_dict(), cell.height, cell.fill, _path_tracking(cell)) for cell in layout.cells]

    @pytest.mark.asyncio
    async def test_reaction_stack(self, source, tmp_path):
        from video_processor.ffmpeg_service import FFmpegService

        layout = choose_layout("auto", "single_subject", [_track(1, FACECAM)], "9:16", 640, 360, 1080, 1920,
                               context=FormatContext("reaction", VisualEvidence(facecam=0.9, content_box=(0, 0, 0.78, 1))))
        out = tmp_path / "reaction.mp4"
        await FFmpegService().render_stack(str(source), str(out), 0.2, 1.5, self._cells(layout), 1080, 640, 360)
        assert layout.kind == "reaction_stack" and self._size(out) == "1080x1920"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fmt,tracks,evidence", [
        ("screen_share", [], VisualEvidence(screen=0.9)),
        ("screen_share", [_track(1, FACECAM)], VisualEvidence(screen=0.9, facecam=0.9)),
        ("voice_over", [], None),
    ])
    async def test_roaming_window(self, source, tmp_path, fmt, tracks, evidence):
        from video_processor.ffmpeg_service import FFmpegService

        focus = tuple((0.2 + i / 6, Box(0.2 + i * 0.03, 0.4, 0.06, 0.05)) for i in range(9))
        layout = choose_layout("auto", "single_subject", tracks, "9:16", 640, 360, 1080, 1920,
                               context=FormatContext(fmt, evidence, focus))
        layout.cells = [_roam(cell, focus, 640, 360) for cell in layout.cells]
        assert layout.cells[0].path, layout
        out = tmp_path / f"{fmt}.mp4"
        await FFmpegService().render_stack(str(source), str(out), 0.2, 1.5, self._cells(layout), 1080, 640, 360)
        assert self._size(out) == "1080x1920"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("evidence", [
        VisualEvidence(green=0.8),
        VisualEvidence(green=0.8, graphic_backdrop=0.6, content_box=(0.0, 0.0, 0.4, 0.5)),
    ])
    async def test_keyed_green_screen(self, green, tmp_path, evidence):
        from video_processor.ffmpeg_service import FFmpegService

        colour = key_colour([(0.0, cv2.imread(str(self._still(green, tmp_path))))])
        layout = choose_layout("auto", "single_subject", [_track(1, Box(0.44, 0.25, 0.12, 0.2))], "9:16",
                               640, 360, 1080, 1920, context=FormatContext("green_screen", evidence, key_colour=colour))
        backdrop, person = layout.cells
        out = tmp_path / "keyed.mp4"
        await FFmpegService().render_keyed(
            str(green), str(out), 0.2, 1.5, (backdrop.box.as_dict(), backdrop.fill),
            (person.box.as_dict(), person.height), layout.key, 1080, 1920, 640, 360,
        )
        assert self._size(out) == "1080x1920"
        frame = cv2.imread(str(self._still(out, tmp_path)))
        # The person stands at the bottom, keyed out of the green around them.
        assert frame[1800, 540][2] > frame[1800, 540][1]
        if backdrop.fill == "blur":
            b, g, r = (int(v) for v in frame[1800, 60])
            assert g < max(r, b) + 20

    @staticmethod
    def _still(video: Path, tmp_path: Path) -> Path:
        still = tmp_path / f"{video.stem}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
                        str(still)], check=True)
        return still

    @pytest.mark.asyncio
    async def test_a_screen_share_cut_end_to_end(self, tmp_path):
        """Typing on a still screen, cut as a screen share with nobody on camera."""

        class NoFaces:
            backend = "none"

            def detect_clip(self, frames):
                return [[] for _ in frames()], self.backend

        screen = self._source(tmp_path / "screen.mp4",
                              "color=c=white:size=1280x720:rate=25:duration=3[bg];"
                              "testsrc=size=80x40:rate=25:duration=3[fg];[bg][fg]overlay=x='300+t*60':y=400")
        request = CutRequest(source_path=str(screen), output_dir=tmp_path, clip_id="screen", start=0.0, end=2.0,
                             aspect_ratios=["9:16"], content_format="screen_share",
                             format_evidence=VisualEvidence(screen=0.9).as_dict())
        result = await ClipCutter(face_detector=NoFaces()).cut(request)
        assert result.layout == "screen_focus" and not result.errors
        assert self._size(result.output_files["9:16"]) == "1080x1920"
