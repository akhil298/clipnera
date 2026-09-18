from __future__ import annotations

import re

import pytest

from video_processor.geometry import Box, crop_tracking_expressions

SRC_W, SRC_H = 1920, 1080
CROP_W, CROP_H = 608, 1080
MAX_X = SRC_W - CROP_W


def evaluate(expression: str, t: float) -> float:
    """Evaluate an FFmpeg crop expression in Python, for verification."""
    py = re.sub(r"\bclip\(", "_clip(", expression)

    def _clip(value, low, high):
        return max(low, min(high, value))

    return eval(py, {"_clip": _clip, "t": t})  # noqa: S307 - test-only


def track(points: list[tuple[float, float]]) -> list[dict]:
    return [
        {"timestamp": ts, "bbox": Box(x, 0.0, CROP_W / SRC_W, 1.0).as_dict()}
        for ts, x in points
    ]


class TestFlatExpression:
    def test_has_no_nesting(self) -> None:
        """Regression: nested if() grew one level per point and FFmpeg failed to
        parse it past about a minute of tracking."""
        long_track = track([(i * 0.25, 0.1 + 0.001 * i) for i in range(240)])
        x, _ = crop_tracking_expressions(long_track, SRC_W, SRC_H, CROP_W, CROP_H)
        assert "if(" not in x

    def test_matches_linear_interpolation(self) -> None:
        points = track([(0.0, 0.0), (2.0, 0.5)])
        x, _ = crop_tracking_expressions(points, SRC_W, SRC_H, CROP_W, CROP_H)
        start, end = 0.0, 0.5 * SRC_W
        assert evaluate(x, 0.0) == pytest.approx(start, abs=1.0)
        assert evaluate(x, 1.0) == pytest.approx((start + end) / 2, abs=2.0)
        assert evaluate(x, 2.0) == pytest.approx(end, abs=1.0)

    def test_holds_value_after_last_point(self) -> None:
        points = track([(0.0, 0.0), (2.0, 0.4)])
        x, _ = crop_tracking_expressions(points, SRC_W, SRC_H, CROP_W, CROP_H)
        assert evaluate(x, 10.0) == pytest.approx(evaluate(x, 2.0), abs=0.5)

    def test_holds_value_before_first_point(self) -> None:
        points = track([(1.0, 0.3), (3.0, 0.5)])
        x, _ = crop_tracking_expressions(points, SRC_W, SRC_H, CROP_W, CROP_H)
        assert evaluate(x, 0.0) == pytest.approx(0.3 * SRC_W, abs=1.0)

    def test_stays_inside_frame(self) -> None:
        points = track([(0.0, 0.0), (1.0, 0.95), (2.0, 0.0)])
        x, _ = crop_tracking_expressions(points, SRC_W, SRC_H, CROP_W, CROP_H)
        for t in [i * 0.1 for i in range(30)]:
            assert 0.0 <= evaluate(x, t) <= MAX_X

    def test_multi_segment_path_is_accurate(self) -> None:
        points = track([(0.0, 0.0), (1.0, 0.2), (2.0, 0.6), (3.0, 0.3)])
        x, _ = crop_tracking_expressions(points, SRC_W, SRC_H, CROP_W, CROP_H)
        for ts, expected in [(0.0, 0.0), (1.0, 0.2), (2.0, 0.6), (3.0, 0.3)]:
            want = min(expected * SRC_W, MAX_X)
            assert evaluate(x, ts) == pytest.approx(want, abs=2.0), f"at t={ts}"

    def test_static_when_no_tracking(self) -> None:
        x, y = crop_tracking_expressions([], SRC_W, SRC_H, CROP_W, CROP_H)
        assert x == str(MAX_X // 2) and y == "0"

    def test_single_point_is_constant(self) -> None:
        x, _ = crop_tracking_expressions(track([(0.0, 0.25)]), SRC_W, SRC_H, CROP_W, CROP_H)
        assert evaluate(x, 0.0) == pytest.approx(evaluate(x, 99.0))

    def test_expression_size_is_linear(self) -> None:
        short = track([(i * 0.25, 0.1 + 0.001 * i) for i in range(40)])
        long = track([(i * 0.25, 0.1 + 0.001 * i) for i in range(240)])
        x_short, _ = crop_tracking_expressions(short, SRC_W, SRC_H, CROP_W, CROP_H)
        x_long, _ = crop_tracking_expressions(long, SRC_W, SRC_H, CROP_W, CROP_H)
        assert len(x_long) < len(x_short) * 8
