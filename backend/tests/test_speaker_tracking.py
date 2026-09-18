from __future__ import annotations

import numpy as np
import pytest

from video_processor.clip_cutter import ClipCutter
from video_processor.face_detection import Face
from video_processor.geometry import Box
from video_processor.speaker_tracking import (
    FaceSample,
    SpeakerTrack,
    active_speaker_at,
    build_tracks,
    is_speaking_at,
    speech_intervals,
)


def face_at(x: float, y: float, size: float = 0.2) -> Face:
    box = Box(x, y, size, size)
    return Face(box=box, confidence=0.9, mouth=Box(x + size / 4, y + size * 0.62, size / 2, size / 4))


@pytest.fixture(scope="module")
def cutter() -> ClipCutter:
    return ClipCutter()


def track_with(track_id: int, box: Box, motions: list[float], start: float = 0.0) -> SpeakerTrack:
    face = Face(box=box, confidence=0.9, mouth=box)
    return SpeakerTrack(
        track_id=track_id,
        samples=[FaceSample(timestamp=start + i, face=face, mouth_motion=m) for i, m in enumerate(motions)],
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
