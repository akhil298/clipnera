from __future__ import annotations

import pytest

from video_processor.geometry import Box, crop_tracking_path

SRC_W, SRC_H = 1920, 1080
CROP_W, CROP_H = 608, 1080
MAX_X = SRC_W - CROP_W


def track(points: list[tuple[float, float]]) -> list[dict]:
    return [
        {"timestamp": ts, "bbox": Box(x, 0.0, CROP_W / SRC_W, 1.0).as_dict()}
        for ts, x in points
    ]


def x_at(path: list[tuple[float, int, int]], t: float) -> int:
    """The crop x FFmpeg holds at time t: the last command sent at or before it."""
    return [x for ts, x, _ in path if ts <= t + 1e-9][-1]


def build(points: list[tuple[float, float]], duration: float) -> list[tuple[float, int, int]]:
    return crop_tracking_path(track(points), SRC_W, SRC_H, CROP_W, CROP_H, duration)


class TestCropTrackingPath:
    def test_matches_linear_interpolation(self) -> None:
        path = build([(0.0, 0.0), (2.0, 0.5)], 2.0)
        assert x_at(path, 0.0) == 0
        assert x_at(path, 1.0) == pytest.approx(0.25 * SRC_W, abs=1)
        assert x_at(path, 2.0) == pytest.approx(min(0.5 * SRC_W, MAX_X), abs=1)

    def test_holds_value_after_last_point(self) -> None:
        path = build([(0.0, 0.0), (2.0, 0.4)], 10.0)
        assert x_at(path, 10.0) == x_at(path, 2.0)

    def test_holds_value_before_first_point(self) -> None:
        path = build([(1.0, 0.3), (3.0, 0.5)], 3.0)
        assert x_at(path, 0.0) == round(0.3 * SRC_W)

    def test_stays_inside_frame(self) -> None:
        path = build([(0.0, 0.0), (1.0, 0.95), (2.0, 0.0)], 2.0)
        assert all(0 <= x <= MAX_X for _, x, _ in path)

    def test_moves_every_frame_while_panning(self) -> None:
        path = build([(0.0, 0.0), (1.0, 0.5)], 1.0)
        assert len(path) >= 30

    def test_long_clip_keeps_every_tracking_point(self) -> None:
        """Regression: the expression renderer thinned any path to ~64 points,
        so on long clips the crop only moved about once a second."""
        points = [(i * 0.5, 0.1 if i % 2 else 0.4) for i in range(240)]  # 120s, zig-zag
        path = build(points, 120.0)
        for ts, x in points:
            assert x_at(path, ts) == pytest.approx(min(x * SRC_W, MAX_X), abs=1), f"at t={ts}"

    def test_static_when_no_tracking(self) -> None:
        path = crop_tracking_path([], SRC_W, SRC_H, CROP_W, CROP_H, 5.0)
        assert path == [(0.0, MAX_X // 2, 0)]

    def test_still_subject_is_a_single_entry(self) -> None:
        assert len(build([(0.0, 0.25), (5.0, 0.25)], 5.0)) == 1
