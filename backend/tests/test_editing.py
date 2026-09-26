from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from video_processor.editing import (
    PUNCH_IN_ZOOM,
    Layout,
    Part,
    choose_layout,
    plan_parts,
    region_around,
    shot_cuts,
    shot_windows,
    tracks_in_shot,
)
from video_processor.face_detection import Face
from video_processor.geometry import Box
from video_processor.speaker_tracking import FaceSample, SpeakerTrack

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _track(track_id: int, box: Box, samples: int = 10) -> SpeakerTrack:
    face = Face(box=box, confidence=0.9, mouth=box)
    return SpeakerTrack(track_id=track_id, samples=[FaceSample(timestamp=i * 0.5, face=face) for i in range(samples)])


class TestLayout:
    def test_gaming_facecam_becomes_a_split(self):
        facecam = _track(1, Box(0.82, 0.05, 0.1, 0.15))
        layout = choose_layout("split_gameplay", "gaming_with_facecam", [facecam], "9:16", 1920, 1080, 1080, 1920)
        assert layout.kind == "split_gameplay"
        assert sum(cell.height for cell in layout.cells) == 1920
        top = layout.cells[0].box
        # The facecam region surrounds the face and stays in frame.
        assert top.x <= 0.82 and top.x + top.width >= 0.92 and top.x + top.width <= 1.0 + 1e-9

    def test_moving_face_is_not_a_facecam(self):
        samples = [FaceSample(timestamp=i, face=_track(1, Box(0.1 + i * 0.05, 0.1, 0.1, 0.15)).samples[0].face) for i in range(10)]
        track = SpeakerTrack(track_id=1, samples=samples)
        layout = choose_layout("split_gameplay", "gaming_with_facecam", [track], "9:16", 1920, 1080, 1080, 1920)
        assert layout.kind == "follow"

    def test_two_speakers_stack_left_on_top(self):
        left, right = _track(1, Box(0.15, 0.3, 0.12, 0.2)), _track(2, Box(0.7, 0.3, 0.12, 0.2))
        layout = choose_layout("two_speaker_stack", "two_subjects_left_right", [right, left], "9:16", 1920, 1080, 1080, 1920)
        assert layout.kind == "two_speaker_stack"
        assert layout.cells[0].box.center[0] < layout.cells[1].box.center[0]

    def test_other_shapes_always_follow(self):
        facecam = _track(1, Box(0.82, 0.05, 0.1, 0.15))
        assert choose_layout("split_gameplay", "gaming_with_facecam", [facecam], "1:1", 1920, 1080, 1080, 1080).kind == "follow"

    def test_missing_faces_fall_back_to_follow(self):
        assert choose_layout("two_speaker_stack", "single_subject", [_track(1, Box(0.4, 0.3, 0.2, 0.3))],
                             "9:16", 1920, 1080, 1080, 1920).kind == "follow"

    def test_a_shot_with_nobody_is_shown_whole(self):
        assert choose_layout("two_speaker_stack", "two_subjects_left_right", [], "9:16", 1920, 1080, 1080, 1920).kind == "fit"

    def test_a_faceless_shot_already_in_shape_is_cropped(self):
        assert choose_layout("auto", "no_subject", [], "16:9", 1920, 1080, 1920, 1080).kind == "follow"

    def test_stacked_speaker_sits_above_the_cell_centre(self):
        left, right = _track(1, Box(0.15, 0.3, 0.12, 0.2)), _track(2, Box(0.7, 0.3, 0.12, 0.2))
        top = choose_layout("two_speaker_stack", "two_subjects_left_right", [left, right],
                            "9:16", 1920, 1080, 1080, 1920).cells[0].box
        face_cy = 0.3 + 0.1
        assert top.x < 0.21 < top.x + top.width
        assert face_cy < top.y + top.height / 2

    def test_region_keeps_the_cell_shape(self):
        region = region_around(Box(0.45, 0.4, 0.1, 0.2), 2.0, 1080 / 960, 1920, 1080)
        assert region.width * 1920 / (region.height * 1080) == pytest.approx(1080 / 960, rel=1e-3)


class TestShots:
    def test_windows_split_at_cuts_and_absorb_slivers(self):
        assert shot_windows(10.0, 30.0, [5.0, 15.0, 15.4, 22.0, 40.0]) == [(10.0, 15.4), (15.4, 22.0), (22.0, 30.0)]

    def test_a_leading_sliver_joins_the_next_shot(self):
        assert shot_windows(0.0, 10.0, [0.3, 6.0]) == [(0.0, 6.0), (6.0, 10.0)]

    def test_people_are_counted_per_shot(self):
        """Two speakers in a wide shot, then a close-up of one, then B-roll."""
        face = lambda box: Face(box=box, confidence=0.9, mouth=box)
        wide_left = [FaceSample(t / 10, face(Box(0.15, 0.3, 0.1, 0.18))) for t in range(0, 40)]
        close_left = [FaceSample(t / 10, face(Box(0.4, 0.2, 0.25, 0.4))) for t in range(40, 80)]
        wide_right = [FaceSample(t / 10, face(Box(0.75, 0.3, 0.1, 0.18))) for t in range(0, 40)]
        left = SpeakerTrack(1, wide_left + close_left)
        right = SpeakerTrack(2, wide_right)
        kinds = []
        for start, end in shot_windows(0.0, 12.0, [4.0, 8.0]):
            present = tracks_in_shot([left, right], start, end, 0.1)
            kinds.append(choose_layout("two_speaker_stack", "two_subjects_left_right", present,
                                       "9:16", 1920, 1080, 1080, 1920).kind)
        assert kinds == ["two_speaker_stack", "follow", "fit"]

    def test_the_stack_frames_the_shot_not_the_clip_average(self):
        face = lambda box: Face(box=box, confidence=0.9, mouth=box)
        # The same person on the right of a wide shot, then centred in a close-up.
        samples = [FaceSample(t / 10, face(Box(0.8, 0.3, 0.1, 0.18))) for t in range(0, 40)]
        samples += [FaceSample(t / 10, face(Box(0.4, 0.2, 0.25, 0.4))) for t in range(40, 80)]
        right = SpeakerTrack(2, samples)
        left = _track(1, Box(0.15, 0.3, 0.1, 0.18), samples=40)
        left.samples = [FaceSample(t / 10, left.samples[0].face) for t in range(0, 40)]
        present = tracks_in_shot([left, right], 0.0, 4.0, 0.1)
        bottom = choose_layout("two_speaker_stack", "two_subjects_left_right", present,
                               "9:16", 1920, 1080, 1080, 1920).cells[1].box
        assert bottom.x < 0.85 < bottom.x + bottom.width


class TestBeats:
    def test_punch_in_splits_the_span(self):
        parts = plan_parts(10.0, 30.0, [{"t": 15.0, "fx": "punch_in"}], lambda t: None)
        assert parts == [Part(10.0, 15.0), Part(15.0, 17.0, zoom=PUNCH_IN_ZOOM), Part(17.0, 30.0)]

    def test_react_cut_needs_a_listener(self):
        assert plan_parts(0.0, 10.0, [{"t": 4.0, "fx": "react_cut"}], lambda t: None) == [Part(0.0, 10.0)]
        parts = plan_parts(0.0, 10.0, [{"t": 4.0, "fx": "react_cut"}], lambda t: (0.7, 0.3))
        assert parts[1].hold == (0.7, 0.3)

    def test_beats_are_spaced_and_bounded(self):
        beats = [{"t": 1.0, "fx": "punch_in"}, {"t": 2.0, "fx": "punch_in"}, {"t": 50.0, "fx": "punch_in"}]
        parts = plan_parts(0.0, 10.0, beats, lambda t: None)
        assert sum(1 for p in parts if p.zoom > 1) == 1
        assert parts[0].start == 0.0 and parts[-1].end == 10.0

    def test_parts_tile_the_span_without_gaps(self):
        parts = plan_parts(0.0, 12.0, [{"t": 0.1, "fx": "punch_in"}, {"t": 11.8, "fx": "punch_in"}], lambda t: None)
        assert parts[0].start == 0.0 and parts[-1].end == 12.0
        for a, b in zip(parts, parts[1:]):
            assert a.end == pytest.approx(b.start)


class TestShotCuts:
    def test_a_colour_change_is_a_cut(self):
        red = np.zeros((90, 160, 3), np.uint8)
        red[:, :, 2] = 220
        blue = np.zeros((90, 160, 3), np.uint8)
        blue[:, :, 0] = 220
        frames = [(0.0, red), (0.5, red), (1.0, blue), (1.5, blue)]
        assert shot_cuts(frames) == [1.0]


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
class TestRenders:
    @pytest.fixture
    def source(self, tmp_path):
        path = tmp_path / "src.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
        ], check=True)
        return path

    @staticmethod
    def _size(path) -> str:
        return subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, check=True,
        ).stdout.strip()

    @pytest.mark.asyncio
    async def test_stacked_render_has_the_output_size(self, source, tmp_path):
        from video_processor.ffmpeg_service import FFmpegService

        out = tmp_path / "stack.mp4"
        await FFmpegService().render_stack(
            str(source), str(out), 0.5, 2.0,
            [({"x": 0.7, "y": 0.0, "width": 0.3, "height": 0.4}, 256), ({"x": 0.3, "y": 0.0, "width": 0.4, "height": 1.0}, 384)],
            360, 640, 360,
        )
        assert self._size(out) == "360x640"

    @pytest.mark.asyncio
    async def test_fitted_and_cropped_parts_join_by_copy(self, source, tmp_path):
        from video_processor.ffmpeg_service import FFmpegService

        ffmpeg = FFmpegService()
        fitted, cropped, joined = tmp_path / "fit.mp4", tmp_path / "crop.mp4", tmp_path / "joined.mp4"
        await ffmpeg.render_fit(str(source), str(fitted), 0.0, 1.5, 360, 640, 640)
        await ffmpeg.crop_with_tracking(input_path=str(source), output_path=str(cropped), start_time=1.5,
                                        duration=1.5, crop_tracking=[], target_width=360, target_height=640,
                                        source_width=640, source_height=360)
        await ffmpeg.concat_segments([str(fitted), str(cropped)], str(joined))
        assert self._size(fitted) == "360x640"
        assert self._size(joined) == "360x640"

    @pytest.mark.asyncio
    async def test_zoomed_and_plain_parts_join_by_copy(self, source, tmp_path):
        from video_processor.ffmpeg_service import FFmpegService

        ffmpeg = FFmpegService()
        plain, zoomed, joined = tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "ab.mp4"
        common = dict(input_path=str(source), crop_tracking=[], target_width=360, target_height=640,
                      source_width=640, source_height=360)
        await ffmpeg.crop_with_tracking(output_path=str(plain), start_time=0.0, duration=1.5, **common)
        await ffmpeg.crop_with_tracking(output_path=str(zoomed), start_time=1.5, duration=1.5, zoom=1.2, **common)
        await ffmpeg.concat_segments([str(plain), str(zoomed)], str(joined))
        assert self._size(joined) == "360x640"
        duration = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(joined)],
            capture_output=True, text=True, check=True,
        ).stdout)
        assert duration == pytest.approx(3.0, abs=0.2)
