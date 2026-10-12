"""beat.snap: move each cut onto a nearby beat, all cuts at once (BLUEPRINT §3B.3.2).

Every cut may move to any beat within half a beat of it, or stay. A Viterbi pass picks the
whole sequence so that strong beats win (drop > downbeat > beat), cuts stay in order, and
no shot gets shorter than the minimum. Beats are placed on the timeline through the music
item's position, so every snapped cut sits within a frame of its beat.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

WEIGHTS = {"drop": 1.2, "downbeat": 1.0, "beat": 0.6}
MIN_SHOT_FRAMES = 8
# Cost of each frame moved, so a near beat beats a far one of the same kind.
MOVE_COST = 0.02
STAY_COST = 0.0


@dataclass(frozen=True)
class BeatMark:
    frame: int
    kind: str  # drop | downbeat | beat


def beats_on_timeline(times: Sequence[float], downbeats: set[float], drops: Sequence[float], *, fps: int,
                      music_at: int, music_src_in: int, speed: float = 1.0) -> list[BeatMark]:
    """Music beats (seconds of the track) as timeline frames, given where the music item sits."""
    marks: dict[int, BeatMark] = {}
    for t in times:
        kind = "downbeat" if t in downbeats else "beat"
        frame = music_at + round((round(t * fps) - music_src_in) / speed)
        if frame >= music_at:
            marks[frame] = BeatMark(frame, kind)
    for t in drops:
        frame = music_at + round((round(t * fps) - music_src_in) / speed)
        if frame >= music_at:
            marks[frame] = BeatMark(frame, "drop")
    return sorted(marks.values(), key=lambda m: m.frame)


def snap(cuts: Sequence[int], beats: Sequence[BeatMark], *, start: int = 0, end: int | None = None,
         min_shot: int = MIN_SHOT_FRAMES) -> list[int]:
    """New positions for ``cuts`` (sorted timeline frames), each a beat frame or unchanged."""
    if not cuts or not beats:
        return list(cuts)
    interval = _median_gap(beats)
    reach = max(1, interval // 2)
    options: list[list[tuple[int, float]]] = []
    for cut in cuts:
        near = [(b.frame, -WEIGHTS[b.kind] + MOVE_COST * abs(b.frame - cut)) for b in beats if abs(b.frame - cut) <= reach]
        # Staying put costs nothing; any beat in reach is worth more, unless moving breaks a shot.
        stay = [] if any(frame == cut for frame, _ in near) else [(cut, STAY_COST)]
        options.append(near + stay)

    # Viterbi: cost[i][j] = best total cost with cut i at option j.
    costs: list[list[float]] = []
    back: list[list[int]] = []
    for i, opts in enumerate(options):
        row, prev = [], []
        for frame, cost in opts:
            if i == 0:
                ok = frame - start >= min_shot
                row.append(cost if ok else float("inf"))
                prev.append(-1)
                continue
            best, arg = float("inf"), -1
            for k, (prev_frame, _) in enumerate(options[i - 1]):
                if frame - prev_frame >= min_shot and costs[i - 1][k] + cost < best:
                    best, arg = costs[i - 1][k] + cost, k
            row.append(best)
            prev.append(arg)
        costs.append(row)
        back.append(prev)
    last = [c if end is None or end - options[-1][j][0] >= min_shot else float("inf") for j, c in enumerate(costs[-1])]
    if min(last) == float("inf"):
        return list(cuts)  # No legal snapping: leave the cuts where they are.
    j = last.index(min(last))
    chosen = []
    for i in range(len(options) - 1, -1, -1):
        chosen.append(options[i][j][0])
        j = back[i][j]
    return chosen[::-1]


def _median_gap(beats: Sequence[BeatMark]) -> int:
    gaps = sorted(b.frame - a.frame for a, b in zip(beats, beats[1:]) if b.frame > a.frame)
    return gaps[len(gaps) // 2] if gaps else 15
