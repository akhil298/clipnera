from __future__ import annotations

import numpy as np
import pytest

from video_processor.editing import CONTENT_MAX_SHARE, CONTENT_MIN_SHARE, choose_layout
from video_processor.face_detection import Face
from video_processor.focus import PEOPLE, decide_focus
from video_processor.geometry import Box
from video_processor.regions import Region, content_regions, frame_rectangles, main_content, person_tracks
from video_processor.speaker_tracking import FaceSample, SpeakerTrack

W, H = 640, 360


def _screen(art: tuple[int, int, int, int] | None = (160, 88, 480, 260), bleed: bool = False, noise: int = 0) -> np.ndarray:
    """A dimmed screen share, optionally with a white picture on it."""
    rng = np.random.default_rng(noise)
    frame = np.full((H, W, 3), 112, np.uint8)
    # Some UI: a sidebar and a chat column the detector must not take for content.
    frame[:, :60] = 70
    frame[:, 560:] = 80
    if art:
        x0, y0, x1, y1 = art
        frame[y0:y1, x0:x1] = 250
        # A drawing inside it; with ``bleed`` it runs off the bottom-left corner.
        frame[y0 + 30:y1 - 30, x0 + 60:x0 + 120] = (40, 60, 120)
        frame[y0 + 40:y0 + 70, x0 + 180:x1 - 40] = (30, 30, 200)
        if bleed:
            frame[y1 - 40:y1, x0:x0 + 200] = (40, 200, 40)
    if noise:
        frame = np.clip(frame.astype(np.int16) + rng.integers(-3, 4, frame.shape), 0, 255).astype(np.uint8)
    return frame


def _track(track_id: int, box: Box, samples: int = 10, start: float = 0.0) -> SpeakerTrack:
    face = Face(box=box, confidence=0.9, mouth=box)
    return SpeakerTrack(
        track_id=track_id, samples=[FaceSample(timestamp=start + i * 0.5, face=face) for i in range(samples)],
    )


def _region(box: Box, presence: float = 1.0, motion: float = 0.0, first_seen: float = 0.0) -> Region:
    return Region(box=box, presence=presence, detail=0.1, motion=motion, first_seen=first_seen)


class TestRegions:
    def test_finds_a_picture_on_a_screen(self):
        boxes = frame_rectangles(_screen())
        assert boxes, "the picture was not found"
        best = boxes[0]
        assert best.x == pytest.approx(160 / W, abs=0.02)
        assert best.width == pytest.approx(320 / W, abs=0.03)
        assert best.height == pytest.approx(172 / H, abs=0.03)

    def test_drawing_running_off_the_edge_still_yields_the_whole_picture(self):
        best = frame_rectangles(_screen(bleed=True))[0]
        assert best.width == pytest.approx(320 / W, abs=0.03)
        assert best.height == pytest.approx(172 / H, abs=0.03)

    def test_side_panels_and_empty_screens_are_not_content(self):
        assert frame_rectangles(_screen(art=None)) == []

    def test_regions_persist_across_samples_and_are_still(self):
        samples = [(i / 3, _screen(noise=i + 1)) for i in range(9)]
        regions = content_regions(samples)
        assert regions and regions[0].presence == 1.0
        assert not regions[0].moving

    def test_a_flash_of_content_is_not_a_region(self):
        samples = [(i / 3, _screen() if i == 4 else _screen(art=None)) for i in range(9)]
        assert content_regions(samples) == []


class TestFaceRoles:
    art = _region(Box(0.25, 0.25, 0.5, 0.5))

    def test_a_face_drawn_in_a_still_picture_is_not_a_person(self):
        drawn = _track(1, Box(0.45, 0.35, 0.08, 0.14))
        streamer = _track(2, Box(0.02, 0.6, 0.08, 0.18))
        assert person_tracks([drawn, streamer], [self.art]) == [streamer]

    def test_a_small_moving_window_holding_a_face_is_a_webcam(self):
        cam = _region(Box(0.75, 0.7, 0.2, 0.25), motion=12.0)
        guest = _track(1, Box(0.82, 0.75, 0.05, 0.1))
        assert person_tracks([guest], [cam]) == [guest]
        assert main_content([cam], [guest]) is None

    def test_without_regions_every_face_is_a_person(self):
        tracks = [_track(1, Box(0.4, 0.4, 0.1, 0.1))]
        assert person_tracks(tracks, []) == tracks


class TestFocus:
    art = _region(Box(0.25, 0.25, 0.5, 0.5))
    streamer = _track(1, Box(0.02, 0.6, 0.08, 0.18))

    def test_reaction_video_shows_the_picture_with_the_audience(self):
        focus = decide_focus([self.art], [self.streamer], 0.0, category="reaction")
        assert focus.kind == "content_reaction" and focus.content is self.art

    def test_pointing_at_it_is_enough(self):
        focus = decide_focus([self.art], [self.streamer], 0.0, category="podcast_interview",
                             spoken="bro look at this drawing")
        assert focus.shows_content

    def test_a_picture_that_pops_up_is_enough(self):
        late = _region(self.art.box, first_seen=2.0)
        assert decide_focus([late], [self.streamer], 0.0, category="vlog").shows_content

    def test_a_poster_with_no_reason_leaves_the_framing_alone(self):
        assert decide_focus([self.art], [self.streamer], 0.0, category="podcast_interview",
                            spoken="that is what I believe") is PEOPLE

    def test_a_rectangle_around_a_person_is_never_content(self):
        behind = _track(2, Box(0.45, 0.4, 0.08, 0.14))
        assert decide_focus([self.art], [behind], 0.0, category="reaction") is PEOPLE

    def test_weak_regions_leave_the_framing_alone(self):
        brief = _region(self.art.box, presence=0.45)
        tiny = _region(Box(0.4, 0.4, 0.15, 0.15))
        assert decide_focus([brief], [self.streamer], 0.0, category="reaction") is PEOPLE
        assert decide_focus([tiny], [self.streamer], 0.0, category="reaction") is PEOPLE

    def test_content_alone(self):
        assert decide_focus([self.art], [], 0.0, category="reaction").kind == "content"


class TestContentLayout:
    def test_content_on_top_audience_below(self):
        art = _region(Box(0.25, 0.24, 0.5, 0.48))
        speed, friend = _track(1, Box(0.02, 0.6, 0.08, 0.18)), _track(2, Box(0.21, 0.66, 0.06, 0.13))
        focus = decide_focus([art], [speed, friend], 0.0, category="reaction")
        layout = choose_layout("auto", "two_subjects_left_right", [speed, friend], "9:16", 1920, 1080, 1080, 1920,
                               pair=[speed, friend], focus=focus)
        assert layout.kind == "screen_with_speaker"
        top, bottom = layout.cells
        assert top.fit and top.box == art.box
        assert top.height + bottom.height == 1920
        assert CONTENT_MIN_SHARE * 1920 - 2 <= top.height <= CONTENT_MAX_SHARE * 1920 + 2
        # Both people are in the audience cell.
        for face in (speed, friend):
            box = face.samples[0].face.box
            assert bottom.box.x <= box.x and box.x + box.width <= bottom.box.x + bottom.box.width

    def test_wide_content_gives_the_people_more_room(self):
        wide = decide_focus([_region(Box(0.1, 0.3, 0.8, 0.3))], [_track(1, Box(0.02, 0.6, 0.08, 0.18))], 0.0,
                            category="reaction")
        tall = decide_focus([_region(Box(0.35, 0.1, 0.3, 0.8))], [_track(1, Box(0.02, 0.6, 0.08, 0.18))], 0.0,
                            category="reaction")
        wide_top = choose_layout("auto", "single_subject", [], "9:16", 1920, 1080, 1080, 1920, focus=wide).cells[0]
        tall_top = choose_layout("auto", "single_subject", [], "9:16", 1920, 1080, 1080, 1920, focus=tall).cells[0]
        assert wide_top.height < tall_top.height

    def test_content_without_people_is_fitted_whole(self):
        art = _region(Box(0.25, 0.25, 0.5, 0.5))
        layout = choose_layout("auto", "no_subject", [], "9:16", 1920, 1080, 1080, 1920,
                               focus=decide_focus([art], [], 0.0, category="reaction"))
        assert layout.kind == "content" and layout.content == art.box and not layout.composite

    def test_people_focus_keeps_the_old_behaviour(self):
        left, right = _track(1, Box(0.15, 0.3, 0.12, 0.2)), _track(2, Box(0.7, 0.3, 0.12, 0.2))
        layout = choose_layout("auto", "two_subjects_left_right", [left, right], "9:16", 1920, 1080, 1080, 1920,
                               pair=[left, right], focus=PEOPLE)
        assert layout.kind == "two_speaker_stack"

    def test_other_shapes_ignore_content(self):
        focus = decide_focus([_region(Box(0.25, 0.25, 0.5, 0.5))], [], 0.0, category="reaction")
        assert choose_layout("auto", "no_subject", [], "16:9", 1920, 1080, 1920, 1080, focus=focus).kind != "content"


class TestWebcamBubble:
    art = _region(Box(0.25, 0.25, 0.5, 0.5))

    def test_a_small_webcam_becomes_a_bubble_over_the_content(self):
        cam = _track(1, Box(0.9, 0.05, 0.03, 0.05))
        focus = decide_focus([self.art], [cam], 0.0, category="reaction")
        layout = choose_layout("auto", "single_subject", [cam], "9:16", 1920, 1080, 1080, 1920, focus=focus)
        assert layout.kind == "content" and layout.content == self.art.box
        assert layout.bubble is not None and layout.bubble.width * 1920 == pytest.approx(layout.bubble.height * 1080, rel=0.02)

    def test_a_big_enough_face_keeps_the_stack(self):
        streamer = _track(1, Box(0.02, 0.6, 0.08, 0.18))
        focus = decide_focus([self.art], [streamer], 0.0, category="reaction")
        layout = choose_layout("auto", "single_subject", [streamer], "9:16", 1920, 1080, 1080, 1920, focus=focus)
        assert layout.kind == "screen_with_speaker" and layout.bubble is None


class TestBubblePlacement:
    def test_wide_content_moves_up_and_the_bubble_sits_clear_under_it(self):
        from video_processor.ffmpeg_service import bubble_layout

        top, x, y, d = bubble_layout(1080, 1920, 576)
        assert y >= top + 576 and y + d <= 0.7 * 1920 and x == (1080 - d) // 2

    def test_tall_content_puts_the_bubble_in_the_corner(self):
        from video_processor.ffmpeg_service import bubble_layout

        top, x, y, d = bubble_layout(1080, 1920, 1500)
        assert y < top + 1500 and x > 1080 / 2
