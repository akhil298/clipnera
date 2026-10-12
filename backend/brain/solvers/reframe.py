"""reframe.path: where a vertical crop of a wide shot should centre, over time (BLUEPRINT §3B.3.4).

Input is the face position the analysis found per shot (understanding: Shot.face_x), like
video_processor.speaker_tracking's per-sample centres but from the MUD. The crop follows one
subject, switching only when another leads by 0.15 for 0.8 s; it holds still inside a dead
zone, glides otherwise, and is reduced to 2–8 keyframes (Ramer-Douglas-Peucker).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SWITCH_LEAD = 0.15
SWITCH_SECONDS = 0.8
DEAD_ZONE = 0.04
SMOOTHING = 0.35
MIN_KEYFRAMES, MAX_KEYFRAMES = 2, 8


@dataclass(frozen=True)
class Sample:
    """At ``t`` seconds, candidate subjects as (subject id, x centre 0..1, salience 0..1)."""

    t: float
    subjects: tuple[tuple[str, float, float], ...]


def path(samples: Sequence[Sample], default_x: float = 0.5) -> list[tuple[float, float]]:
    """(t, crop centre x) keyframes, 2 to 8 of them."""
    if not samples:
        return [(0.0, default_x), (0.0, default_x)]
    chosen = _choose_subjects(samples)
    xs: list[tuple[float, float]] = []
    current = chosen[0][1]
    for t, x in chosen:
        if abs(x - current) > DEAD_ZONE:
            current = current + (x - current) * (1 - SMOOTHING)
        xs.append((t, round(current, 4)))
    return _reduce(xs)


def _choose_subjects(samples: Sequence[Sample]) -> list[tuple[float, float]]:
    """The followed subject's x per sample, with hysteresis against flicking between people."""
    out: list[tuple[float, float]] = []
    following: str | None = None
    challenger: tuple[str, float] | None = None  # (id, since t)
    for sample in samples:
        if not sample.subjects:
            out.append((sample.t, out[-1][1] if out else 0.5))
            continue
        ranked = sorted(sample.subjects, key=lambda s: -s[2])
        top = ranked[0]
        current = next((s for s in sample.subjects if s[0] == following), None)
        if current is None:
            following, challenger = top[0], None
            current = top
        elif top[0] != following and top[2] - current[2] >= SWITCH_LEAD:
            if challenger is None or challenger[0] != top[0]:
                challenger = (top[0], sample.t)
            elif sample.t - challenger[1] >= SWITCH_SECONDS:
                following, challenger, current = top[0], None, top
        else:
            challenger = None
        out.append((sample.t, current[1]))
    return out


def _reduce(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= MIN_KEYFRAMES:
        return points + [points[-1]] * (MIN_KEYFRAMES - len(points))
    epsilon = 0.01
    reduced = _rdp(points, epsilon)
    while len(reduced) > MAX_KEYFRAMES:
        epsilon *= 1.6
        reduced = _rdp(points, epsilon)
    return reduced


def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    (t0, x0), (t1, x1) = points[0], points[-1]
    span = (t1 - t0) or 1e-9
    distances = [abs(x - (x0 + (x1 - x0) * (t - t0) / span)) for t, x in points[1:-1]]
    index = max(range(len(distances)), key=distances.__getitem__) + 1
    if distances[index - 1] <= epsilon:
        return [points[0], points[-1]]
    return _rdp(points[:index + 1], epsilon)[:-1] + _rdp(points[index:], epsilon)


def samples_from_shots(shots: Sequence[object], t0: float, t1: float) -> list[Sample]:
    """One sample at the middle of each shot in [t0, t1] that found a face."""
    found = []
    for shot in shots:
        start, end = getattr(shot, "t0"), getattr(shot, "t1")
        face_x = getattr(shot, "face_x")
        if end <= t0 or start >= t1:
            continue
        middle = (max(start, t0) + min(end, t1)) / 2
        found.append(Sample(middle, (("face", face_x, 1.0),) if face_x is not None else ()))
    return found
