from __future__ import annotations

import cv2
import numpy as np
import pytest

from video_processor.clip_cutter import ClipCutter
from video_processor.face_detection import Face
from video_processor.geometry import Box
from video_processor.speaker_tracking import (
    SILENT_MOTION_THRESHOLD,
    FaceSample,
    SpeakerTrack,
    active_speaker_at,
    build_tracks,
    is_speaking_at,
    match_labels_to_tracks,
    speaker_timeline,
    speech_intervals,
    visible_tracks,
)


def face_at(x: float, y: float, size: float = 0.2) -> Face:
    box = Box(x, y, size, size)
    return Face(box=box, confidence=0.9, mouth=Box(x + size / 4, y + size * 0.62, size / 2, size / 4))


@pytest.fixture(scope="module")
def cutter() -> ClipCutter:
    return ClipCutter()


def track_with(
    track_id: int, box: Box, motions: list[float], start: float = 0.0, step: float = 1.0
) -> SpeakerTrack:
    face = Face(box=box, confidence=0.9, mouth=box)
    return SpeakerTrack(
        track_id=track_id,
        samples=[
            FaceSample(timestamp=start + i * step, face=face, mouth_motion=m)
            for i, m in enumerate(motions)
        ],
    )


class TestBuildTracks:
    def test_links_same_face_across_frames(self) -> None:
        frames = [(float(i), np.zeros((64, 64, 3), dtype=np.uint8)) for i in range(4)]
        # Same position each frame => one track, not four.
        faces = [[face_at(0.4, 0.4)] for _ in range(4)]
        tracks = build_tracks(frames, faces)
        assert len(tracks) == 1
        assert len(tracks[0].samples) == 4

    def test_separates_two_people(self) -> None:
        frames = [(float(i), np.zeros((64, 64, 3), dtype=np.uint8)) for i in range(4)]
        faces = [[face_at(0.1, 0.4), face_at(0.7, 0.4)] for _ in range(4)]
        tracks = build_tracks(frames, faces)
        assert len(tracks) == 2

    def test_nobody_carries_over_a_camera_cut(self) -> None:
        """A two-shot cuts to a close-up: only the close-up's face is on screen after it."""
        frames = [(i * 0.5, np.zeros((64, 64, 3), dtype=np.uint8)) for i in range(20)]
        close_up = face_at(0.45, 0.4, 0.1)
        faces = [[face_at(0.25, 0.4, 0.1), face_at(0.74, 0.4, 0.1)] for _ in range(10)] + [[close_up] for _ in range(10)]
        tracks = build_tracks(frames, faces, cuts=[5.0])
        on_screen = visible_tracks(5.5, tracks)
        assert [track.box_at(5.5).center for track in on_screen] == [close_up.box.center]
        assert all(track.box_at(4.5).center != close_up.box.center for track in visible_tracks(4.5, tracks))

    def test_drops_transient_detections(self) -> None:
        frames = [(float(i), np.zeros((64, 64, 3), dtype=np.uint8)) for i in range(10)]
        faces: list[list[Face]] = [[face_at(0.4, 0.4)] for _ in range(10)]
        faces[3] = faces[3] + [face_at(0.85, 0.85, 0.05)]  # one-frame blip
        tracks = build_tracks(frames, faces)
        assert len(tracks) == 1


class TestSpeechIntervals:
    def test_merges_overlapping(self) -> None:
        merged = speech_intervals([
            {"start": 0.0, "end": 2.0, "text": "a"},
            {"start": 1.5, "end": 4.0, "text": "b"},
            {"start": 9.0, "end": 10.0, "text": "c"},
        ])
        assert merged == [(0.0, 4.0), (9.0, 10.0)]

    def test_ignores_empty_text(self) -> None:
        assert speech_intervals([{"start": 0.0, "end": 2.0, "text": "  "}]) == []

    def test_membership(self) -> None:
        intervals = [(0.0, 4.0)]
        assert is_speaking_at(2.0, intervals)
        assert not is_speaking_at(6.0, intervals)


class TestActiveSpeaker:
    def test_picks_the_moving_mouth(self) -> None:
        quiet = track_with(0, Box(0.1, 0.4, 0.2, 0.2), [0.1, 0.1, 0.1])
        talking = track_with(1, Box(0.7, 0.4, 0.2, 0.2), [8.0, 9.0, 7.5])
        speaker = active_speaker_at(1.0, [quiet, talking], [(0.0, 3.0)])
        assert speaker is talking

    def test_falls_back_to_largest_face_when_silent(self) -> None:
        small = track_with(0, Box(0.1, 0.4, 0.1, 0.1), [0.0, 0.0, 0.0])
        large = track_with(1, Box(0.5, 0.3, 0.4, 0.4), [0.0, 0.0, 0.0])
        speaker = active_speaker_at(1.0, [small, large], [])
        assert speaker is large

    def test_single_track_always_wins(self) -> None:
        only = track_with(0, Box(0.4, 0.4, 0.2, 0.2), [0.0])
        assert active_speaker_at(0.0, [only], []) is only

    def test_none_without_tracks(self) -> None:
        assert active_speaker_at(0.0, [], []) is None


class TestLayoutClassification:
    def test_no_faces_is_no_subject(self, cutter: ClipCutter) -> None:
        assert cutter._classify_layout([], "podcast_interview") == "no_subject"

    def test_single_face(self, cutter: ClipCutter) -> None:
        tracks = [track_with(0, Box(0.4, 0.3, 0.2, 0.3), [1.0])]
        assert cutter._classify_layout(tracks, "podcast_interview") == "single_subject"

    def test_two_faces_side_by_side(self, cutter: ClipCutter) -> None:
        tracks = [
            track_with(0, Box(0.05, 0.35, 0.25, 0.3), [1.0]),
            track_with(1, Box(0.70, 0.35, 0.25, 0.3), [1.0]),
        ]
        assert cutter._classify_layout(tracks, "podcast_interview") == "two_subjects_left_right"

    def test_two_faces_stacked(self, cutter: ClipCutter) -> None:
        tracks = [
            track_with(0, Box(0.4, 0.05, 0.25, 0.3), [1.0]),
            track_with(1, Box(0.4, 0.60, 0.25, 0.3), [1.0]),
        ]
        assert cutter._classify_layout(tracks, "podcast_interview") == "two_subjects_top_bottom"

    def test_three_faces_is_grid(self, cutter: ClipCutter) -> None:
        tracks = [
            track_with(0, Box(0.05, 0.3, 0.2, 0.25), [1.0]),
            track_with(1, Box(0.40, 0.3, 0.2, 0.25), [1.0]),
            track_with(2, Box(0.75, 0.3, 0.2, 0.25), [1.0]),
        ]
        assert cutter._classify_layout(tracks, "podcast_interview") == "multi_subject_grid"

    def test_gaming_with_facecam(self, cutter: ClipCutter) -> None:
        tracks = [track_with(0, Box(0.8, 0.7, 0.15, 0.2), [1.0])]
        assert cutter._classify_layout(tracks, "gaming") == "gaming_with_facecam"

    def test_gameplay_without_face(self, cutter: ClipCutter) -> None:
        assert cutter._classify_layout([], "gaming") == "gameplay_only"

    def test_every_layout_maps_to_a_strategy(self, cutter: ClipCutter) -> None:
        layouts = [
            "single_subject", "two_subjects_left_right", "two_subjects_top_bottom",
            "multi_subject_grid", "gaming_with_facecam", "gameplay_only",
            "speaker_plus_screen", "no_subject",
        ]
        for layout in layouts:
            assert cutter._strategy_for(layout) in {"follow_speaker", "cover_subjects", "center"}


class TestFragmentationRecovery:
    """Regression: a flickering detector produced many short tracks, every one
    fell below the presence threshold, and the clip reported no subject at all
    then fell back to a centre crop."""

    def frames(self, n: int):
        return [(float(i) * 0.5, np.zeros((64, 64, 3), dtype=np.uint8)) for i in range(n)]

    def test_drifting_speaker_stays_one_track(self) -> None:
        """A speaker who drifts between samples must not split into many tracks."""
        n = 40
        # Moves steadily right; consecutive boxes barely overlap.
        faces = [[face_at(0.30 + 0.004 * i, 0.4, 0.18)] for i in range(n)]
        tracks = build_tracks(self.frames(n), faces)
        assert len(tracks) == 1
        assert len(tracks[0].samples) == n

    def test_flickering_detection_is_merged(self) -> None:
        n = 40
        faces = []
        for i in range(n):
            # Detector drops the face every third frame and jitters otherwise.
            if i % 3 == 0:
                faces.append([])
            else:
                jitter = 0.01 if i % 2 else -0.01
                faces.append([face_at(0.40 + jitter, 0.40 + jitter, 0.18)])
        tracks = build_tracks(self.frames(n), faces)
        assert len(tracks) == 1, f"expected one speaker, got {len(tracks)}"

    def test_two_separated_people_stay_separate(self) -> None:
        n = 30
        faces = [[face_at(0.05, 0.4, 0.15), face_at(0.75, 0.4, 0.15)] for _ in range(n)]
        tracks = build_tracks(self.frames(n), faces)
        assert len(tracks) == 2

    def test_never_returns_empty_when_faces_were_seen(self) -> None:
        """Even a brief detection beats reporting no subject and centre-cropping."""
        n = 40
        faces: list[list[Face]] = [[] for _ in range(n)]
        for i in (10, 11):
            faces[i] = [face_at(0.4, 0.4, 0.18)]
        tracks = build_tracks(self.frames(n), faces)
        assert len(tracks) == 1

    def test_genuinely_no_faces_returns_nothing(self) -> None:
        n = 20
        tracks = build_tracks(self.frames(n), [[] for _ in range(n)])
        assert tracks == []


def textured_frame(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 255, (100, 100, 3), dtype=np.uint8)


class TestLipMotion:
    FACE = face_at(0.2, 0.2, 0.6)

    def test_mouth_change_scores_motion(self) -> None:
        still = textured_frame(1)
        talking = still.copy()
        # Only the mouth band changes.
        talking[60:80, 40:65] = textured_frame(2)[60:80, 40:65]
        frames = [(0.0, still), (0.17, talking)]
        tracks = build_tracks(frames, [[self.FACE], [self.FACE]])
        assert tracks[0].samples[1].mouth_motion > 5.0

    def test_whole_face_change_is_not_lip_motion(self) -> None:
        """A head nod or camera move shifts eyes and mouth alike."""
        face = cv2.GaussianBlur(textured_frame(1), (9, 9), 3)
        frames = [(0.0, face), (0.17, np.roll(face, 3, axis=0))]
        tracks = build_tracks(frames, [[self.FACE], [self.FACE]])
        assert tracks[0].samples[1].mouth_motion < SILENT_MOTION_THRESHOLD

    def test_no_comparison_across_long_gaps(self) -> None:
        still = textured_frame(1)
        changed = still.copy()
        changed[60:80, 40:65] = 0
        frames = [(0.0, still), (3.0, changed)]
        tracks = build_tracks(frames, [[self.FACE], [self.FACE]])
        assert tracks[0].samples[1].mouth_motion == 0.0


class TestSpeakerTimeline:
    LEFT = Box(0.1, 0.4, 0.2, 0.2)
    RIGHT = Box(0.7, 0.4, 0.2, 0.2)
    STEP = 1.0 / 6.0

    def timestamps(self, seconds: float) -> list[float]:
        return [i * 0.25 for i in range(int(seconds / 0.25) + 1)]

    def test_follows_the_talker_and_switches(self) -> None:
        n = 60  # 10s at 6fps: left talks for 5s, then right.
        left = track_with(0, self.LEFT, [8.0] * 30 + [0.2] * 30, step=self.STEP)
        right = track_with(1, self.RIGHT, [0.2] * 30 + [8.0] * 30, step=self.STEP)
        segments = [{"start": 0.0, "end": 10.0, "text": "talk"}]
        ts = self.timestamps(n * self.STEP - self.STEP)
        timeline = speaker_timeline(ts, [left, right], segments)
        assert timeline[4] is left
        assert timeline[-1] is right
        switches = sum(1 for a, b in zip(timeline, timeline[1:]) if a is not b)
        assert switches == 1
        # The cut lands as the right-hand speaker starts (5s), within one
        # tracking step, not SWITCH_HOLD_SECONDS later.
        first_right = ts[timeline.index(right)]
        assert 4.5 <= first_right <= 5.25

    def test_a_switch_across_the_room_is_a_cut_in_the_crop(self, cutter: ClipCutter) -> None:
        from video_processor.clip_cutter import CutRequest

        left = track_with(0, self.LEFT, [8.0] * 30 + [0.2] * 30, step=self.STEP)
        right = track_with(1, self.RIGHT, [0.2] * 30 + [8.0] * 30, step=self.STEP)
        ts = self.timestamps(9.75)
        speakers = speaker_timeline(ts, [left, right], [{"start": 0.0, "end": 10.0, "text": "talk"}])
        request = CutRequest(source_path="", output_dir=None, clip_id="c", start=0.0, end=10.0, aspect_ratios=["9:16"])
        points = cutter._build_tracking(request, [left, right], ts, speakers, "two_subjects_left_right",
                                        "9:16", 1920, 1080, [])
        jumps = [(a["timestamp"], b["timestamp"]) for a, b in zip(points, points[1:])
                 if abs(a["bbox"]["x"] - b["bbox"]["x"]) > 0.2]
        assert len(jumps) == 1
        assert jumps[0][1] - jumps[0][0] <= 0.011

    def test_ignores_a_brief_burst_from_the_listener(self) -> None:
        left = track_with(0, self.LEFT, [8.0] * 60, step=self.STEP)
        motions = [0.2] * 60
        motions[30:32] = [30.0, 30.0]  # a one-third-second laugh
        right = track_with(1, self.RIGHT, motions, step=self.STEP)
        timeline = speaker_timeline(self.timestamps(9.8), [left, right], [{"start": 0.0, "end": 10.0, "text": "x"}])
        assert all(t is left for t in timeline)

    def test_holds_speaker_through_pauses(self) -> None:
        """Pauses used to jump to the largest face; now the framing holds."""
        small_talker = track_with(0, Box(0.1, 0.4, 0.15, 0.15), [8.0] * 60, step=self.STEP)
        big_listener = track_with(1, Box(0.6, 0.3, 0.35, 0.35), [0.2] * 60, step=self.STEP)
        segments = [{"start": 0.0, "end": 4.0, "text": "a"}, {"start": 5.0, "end": 9.8, "text": "b"}]
        timeline = speaker_timeline(self.timestamps(9.8), [small_talker, big_listener], segments)
        assert all(t is small_talker for t in timeline[2:])

    def test_does_not_frame_someone_who_left(self) -> None:
        left = track_with(0, self.LEFT, [8.0] * 12, step=self.STEP)  # gone after 2s
        late = track_with(1, self.RIGHT, [0.2] * 12, start=8.0, step=self.STEP)
        ts = self.timestamps(9.8)
        timeline = speaker_timeline(ts, [left, late], [{"start": 0.0, "end": 10.0, "text": "x"}])
        assert timeline[ts.index(9.0)] is late

    def test_diarization_label_decides_speaker(self) -> None:
        # Lip motion is weak and ambiguous, but each label lines up with one track.
        left = track_with(0, self.LEFT, [3.0] * 30 + [1.6] * 30, step=self.STEP)
        right = track_with(1, self.RIGHT, [1.6] * 30 + [2.0] * 30, step=self.STEP)
        segments = [
            {"start": 0.0, "end": 5.0, "text": "a", "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "text": "b", "speaker": "SPEAKER_01"},
        ]
        timeline = speaker_timeline(self.timestamps(9.8), [left, right], segments)
        assert timeline[2] is left
        assert timeline[-1] is right

    def test_ambiguous_label_is_not_mapped(self) -> None:
        a = track_with(0, self.LEFT, [2.0] * 10)
        b = track_with(1, self.RIGHT, [2.0] * 10)
        assert match_labels_to_tracks([(0.0, 9.0, "SPEAKER_00")], [a, b]) == {}

    def test_empty_inputs(self) -> None:
        assert speaker_timeline([0.0, 1.0], [], []) == [None, None]


class TestCoverSubjects:
    """Regression: a panel spread across a wide stage was 'covered' by centring
    on the group's middle, which framed empty stage for the whole clip."""

    SRC_W, SRC_H = 1920, 1080

    def target(self, cutter: ClipCutter, tracks: list[SpeakerTrack], speaker: SpeakerTrack):
        return cutter._target_center(
            1.0, tracks, speaker, "cover_subjects", self.SRC_W, self.SRC_H, "9:16",
        )

    def test_group_that_fits_is_framed_together(self, cutter: ClipCutter) -> None:
        tracks = [
            track_with(0, Box(0.40, 0.3, 0.06, 0.1), [1.0, 1.0, 1.0]),
            track_with(1, Box(0.52, 0.3, 0.06, 0.1), [1.0, 1.0, 1.0]),
        ]
        x, _ = self.target(cutter, tracks, tracks[0])
        assert x == pytest.approx(0.49, abs=0.01)

    def test_wide_panel_follows_the_speaker(self, cutter: ClipCutter) -> None:
        tracks = [
            track_with(0, Box(0.05, 0.3, 0.08, 0.12), [1.0, 1.0, 1.0]),
            track_with(1, Box(0.45, 0.3, 0.08, 0.12), [1.0, 1.0, 1.0]),
            track_with(2, Box(0.85, 0.3, 0.08, 0.12), [1.0, 1.0, 1.0]),
        ]
        x, _ = self.target(cutter, tracks, tracks[2])
        assert x == pytest.approx(0.89, abs=0.01)
