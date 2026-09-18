from __future__ import annotations

import pytest

from video_processor.clip_cutter import (
    MAX_PAN_PER_SECOND,
    _limit_velocity,
    _median_filter,
    _smooth_series,
)


class TestMedianFilter:
    def test_removes_single_sample_spike(self) -> None:
        values = [0.3, 0.3, 0.9, 0.3, 0.3, 0.3, 0.3]
        assert max(_median_filter(values, 5)) == pytest.approx(0.3)

    def test_preserves_sustained_change(self) -> None:
        values = [0.2] * 6 + [0.8] * 6
        out = _median_filter(values, 5)
        assert out[0] == pytest.approx(0.2)
        assert out[-1] == pytest.approx(0.8)


class TestVelocityLimit:
    def test_caps_step_size(self) -> None:
        step = 0.25
        out = _limit_velocity([0.0, 1.0], step, MAX_PAN_PER_SECOND)
        assert out[1] - out[0] <= MAX_PAN_PER_SECOND * step + 1e-9


class TestSmoothSeries:
    def test_speaker_switch_is_gradual_not_instant(self) -> None:
        """A hard cut between two speakers must become a glide."""
        step = 0.25
        raw = [0.2] * 12 + [0.8] * 12
        out = _smooth_series(raw, step)
        jumps = [abs(b - a) for a, b in zip(out, out[1:])]
        assert max(jumps) <= MAX_PAN_PER_SECOND * step + 1e-6
        # and it must actually get there
        assert out[-1] > out[0]

    def test_no_phase_lag_on_steady_input(self) -> None:
        out = _smooth_series([0.5] * 20, 0.25)
        assert all(v == pytest.approx(0.5) for v in out)

    def test_monotonic_pan_stays_monotonic(self) -> None:
        raw = [i / 40 for i in range(20)]
        out = _smooth_series(raw, 0.25)
        assert all(b >= a - 1e-9 for a, b in zip(out, out[1:]))

    def test_short_series_passthrough(self) -> None:
        assert _smooth_series([0.1, 0.9], 0.25) == [0.1, 0.9]

    def test_jitter_is_damped(self) -> None:
        raw = [0.5 + (0.05 if i % 2 else -0.05) for i in range(20)]
        out = _smooth_series(raw, 0.25)
        raw_swing = max(raw) - min(raw)
        out_swing = max(out) - min(out)
        assert out_swing < raw_swing / 2
