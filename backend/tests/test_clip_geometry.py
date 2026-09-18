from __future__ import annotations

import pytest

from video_processor.geometry import (
    Box,
    crop_around,
    crop_covering,
    crop_tracking_expressions,
    normalize_box,
    target_crop_size,
)


class TestTargetCropSize:
    def test_vertical_crop_of_landscape_keeps_full_height(self) -> None:
        width, height = target_crop_size(1920, 1080, "9:16")
        assert height == 1080
        assert width == pytest.approx(1080 * 9 / 16, abs=2)

    def test_never_exceeds_source(self) -> None:
        width, height = target_crop_size(640, 480, "16:9")
        assert width <= 640 and height <= 480

    def test_dimensions_are_even(self) -> None:
        for ratio in ("9:16", "1:1", "4:5", "16:9"):
            width, height = target_crop_size(1921, 1081, ratio)
            assert width % 2 == 0 and height % 2 == 0


class TestCropAround:
    def test_returns_top_left_origin_not_centre(self) -> None:
        """Regression: five strategies used to assign the centre to x/y, which
        FFmpeg reads as the top-left corner, offsetting every crop by half a
        window."""
        crop = crop_around(0.5, 0.5, 1920, 1080, "9:16")
        crop_w, _ = target_crop_size(1920, 1080, "9:16")
        expected_left = (1920 - crop_w) / 2 / 1920
        assert crop.x == pytest.approx(expected_left, abs=1e-6)
        assert crop.center[0] == pytest.approx(0.5, abs=1e-6)

    def test_clamps_at_left_edge(self) -> None:
        crop = crop_around(0.0, 0.5, 1920, 1080, "9:16")
        assert crop.x == 0.0

    def test_clamps_at_right_edge(self) -> None:
        crop = crop_around(1.0, 0.5, 1920, 1080, "9:16")
        assert crop.x + crop.width == pytest.approx(1.0, abs=1e-6)

    def test_follows_subject_position(self) -> None:
        left = crop_around(0.25, 0.5, 1920, 1080, "9:16")
        right = crop_around(0.75, 0.5, 1920, 1080, "9:16")
        assert left.x < right.x


class TestCropCovering:
    def test_centres_between_two_subjects(self) -> None:
        boxes = [Box(0.05, 0.4, 0.2, 0.3), Box(0.75, 0.4, 0.2, 0.3)]
        crop = crop_covering(boxes, 1920, 1080, "9:16")
        assert crop.center[0] == pytest.approx(0.5, abs=0.02)


class TestNormalizeBox:
    def test_converts_pixels_using_frame_size(self) -> None:
        box = normalize_box({"x": 960, "y": 540, "width": 192, "height": 108}, 1920, 1080)
        assert box is not None
        assert box.x == pytest.approx(0.5) and box.y == pytest.approx(0.5)

    def test_passes_through_normalised(self) -> None:
        box = normalize_box({"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4})
        assert box is not None and box.width == pytest.approx(0.3)

    def test_rejects_degenerate(self) -> None:
        assert normalize_box({"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}) is None
        assert normalize_box(None) is None


class TestCropTrackingExpressions:
    def test_static_when_no_tracking(self) -> None:
        x, y = crop_tracking_expressions([], 1920, 1080, 608, 1080)
        assert x == str((1920 - 608) // 2) and y == "0"

    def test_interpolates_between_points(self) -> None:
        tracking = [
            {"timestamp": 0.0, "bbox": Box(0.0, 0.0, 0.3, 1.0).as_dict()},
            {"timestamp": 2.0, "bbox": Box(0.5, 0.0, 0.3, 1.0).as_dict()},
        ]
        x, _ = crop_tracking_expressions(tracking, 1920, 1080, 608, 1080)
        assert "if(lt(t," in x and "clip(" in x

    def test_clamps_within_frame(self) -> None:
        tracking = [{"timestamp": 0.0, "bbox": Box(0.99, 0.0, 0.3, 1.0).as_dict()}]
        x, _ = crop_tracking_expressions(tracking, 1920, 1080, 608, 1080)
        assert f",0,{1920 - 608})" in x
