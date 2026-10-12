"""music.fit: cut a song to an exact length on its bar lines (BLUEPRINT §3B.3.3).

Bars come from the downbeats. A path through the bars either plays on (bar i → i+1) or jumps
back to a bar at the same place in a four-bar phrase, so a loop sounds musical. A DP finds
the path closest to the target in whole bars, with a penalty when the biggest drop misses
the frame it should land on; the remainder is absorbed by a stretch of at most ±3%, else by
fading out the last bar. The result is always exactly the target length.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MAX_STRETCH = 0.03
PHRASE_BARS = 4
DROP_MISS_COST_PER_FRAME = 0.05
JUMP_COST = 2.0


@dataclass(frozen=True)
class MusicSegment:
    """Play the track from src_t0 to src_t1 (seconds), placed one after another."""

    src_t0: float
    src_t1: float


@dataclass
class MusicFit:
    segments: list[MusicSegment]
    speed: float
    fade_out_frames: int
    total_frames: int


def fit(downbeats: Sequence[float], track_seconds: float, target_frames: int, fps: int, *,
        drop: float | None = None, drop_at_frame: int | None = None) -> MusicFit:
    bars = _bars(downbeats, track_seconds)
    if not bars:
        return MusicFit([MusicSegment(0.0, min(track_seconds, target_frames / fps))], 1.0, 0, target_frames)
    lengths = [round((b - a) * fps) for a, b in bars]
    # Paths as bar sequences, found by DP over (frames used, last bar).
    limit = target_frames + max(lengths) * 2
    best: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}
    frontier: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {(lengths[0], 0): (0.0, (0,))}
    while frontier:
        nxt: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}
        for (used, bar), (cost, path) in frontier.items():
            key = (used, bar)
            if key in best and best[key][0] <= cost:
                continue
            best[key] = (cost, path)
            for follow, extra in _next_bars(bar, len(bars)):
                total = used + lengths[follow]
                if total <= limit and len(path) < 4 * len(bars):
                    candidate = (cost + extra, path + (follow,))
                    if (total, follow) not in nxt or nxt[(total, follow)][0] > candidate[0]:
                        nxt[(total, follow)] = candidate
        frontier = nxt

    def total_cost(item: tuple[tuple[int, int], tuple[float, tuple[int, ...]]]) -> float:
        (used, _), (cost, path) = item
        stretch = abs(target_frames / used - 1)
        miss = _drop_miss(path, bars, lengths, fps, drop, drop_at_frame)
        return cost + abs(used - target_frames) * 0.01 + (0 if stretch <= MAX_STRETCH else 1.0) + miss

    (used, _), (_, path) = min(best.items(), key=total_cost)
    segments = _merge([MusicSegment(bars[i][0], bars[i][1]) for i in path])
    if abs(target_frames / used - 1) <= MAX_STRETCH:
        return MusicFit(segments, round(used / target_frames, 5), 0, target_frames)
    # Too far to stretch: play what fits and fade out the last bar.
    trimmed = _trim(segments, target_frames / fps)
    return MusicFit(trimmed, 1.0, min(target_frames, lengths[path[-1]]), target_frames)


def _bars(downbeats: Sequence[float], track_seconds: float) -> list[tuple[float, float]]:
    edges = [t for t in sorted(downbeats) if 0 <= t < track_seconds]
    return [(a, b) for a, b in zip(edges, edges[1:] + [track_seconds]) if b - a > 0.2]


def _next_bars(bar: int, count: int) -> list[tuple[int, float]]:
    options: list[tuple[int, float]] = []
    if bar + 1 < count:
        options.append((bar + 1, 0.0))
    # Jump back a whole number of phrases, landing on the same beat of the phrase.
    if (bar + 1) % PHRASE_BARS == 0:
        for back in range(PHRASE_BARS, bar + 1, PHRASE_BARS):
            options.append((bar + 1 - back, JUMP_COST))
    return options


def _drop_miss(path: Sequence[int], bars: Sequence[tuple[float, float]], lengths: Sequence[int], fps: int,
               drop: float | None, at_frame: int | None) -> float:
    if drop is None or at_frame is None:
        return 0.0
    used = 0
    for bar in path:
        start, end = bars[bar]
        if start <= drop < end:
            return abs(used + round((drop - start) * fps) - at_frame) * DROP_MISS_COST_PER_FRAME
        used += lengths[bar]
    return 50.0  # The drop never plays.


def _merge(segments: list[MusicSegment]) -> list[MusicSegment]:
    merged: list[MusicSegment] = []
    for segment in segments:
        if merged and abs(merged[-1].src_t1 - segment.src_t0) < 1e-6:
            merged[-1] = MusicSegment(merged[-1].src_t0, segment.src_t1)
        else:
            merged.append(segment)
    return merged


def _trim(segments: list[MusicSegment], seconds: float) -> list[MusicSegment]:
    out, left = [], seconds
    for segment in segments:
        length = segment.src_t1 - segment.src_t0
        if left <= 0:
            break
        out.append(MusicSegment(segment.src_t0, segment.src_t0 + min(length, left)))
        left -= length
    return out
