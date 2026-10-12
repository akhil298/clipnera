"""timing.fit: choose and trim moments so the cut lands on a target length (BLUEPRINT §3B.3.1).

Each moment offers up to four trims (whole, tight to its words, its core, its first
sentence), each snapped to word or shot edges so a cut never lands mid-word. A group
knapsack over frames then picks at most one trim per moment for the best total value whose
length is within tolerance of the target. The hook is reserved first; a must-include moment
is never dropped, even when that means missing the target (which is reported).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from understanding.mud import MUD

MAX_VARIANTS = 4
# Value of a moment: score, length (diminishing), minus quality trouble, plus a must-include bonus.
LENGTH_EXPONENT = 0.6
MUST_INCLUDE_BONUS = 1_000.0
QUALITY_PENALTY_PER_SECOND = 0.4
# DP resolution: at most this many buckets across the target.
DP_BUCKETS = 2_400
MIN_PIECE_SECONDS = 0.6


@dataclass(frozen=True)
class Candidate:
    """A moment to maybe use: a source range of one asset, how good it is, and how sure we must keep it."""

    asset: str
    t0: float
    t1: float
    score: float
    must_include: bool = False
    hook: bool = False
    ref: str = ""


@dataclass(frozen=True)
class Variant:
    asset: str
    t0: float
    t1: float
    value: float
    ref: str
    label: str

    def frames(self, fps: int) -> int:
        return max(1, round((self.t1 - self.t0) * fps))


@dataclass
class TimingResult:
    pieces: list[Variant]
    total_frames: int
    target_frames: int
    warnings: list[str] = field(default_factory=list)

    @property
    def error_frames(self) -> int:
        return self.total_frames - self.target_frames


def variants(candidate: Candidate, mud: MUD | None) -> list[Variant]:
    """Up to four trims of a moment, edges snapped to words (else shots)."""
    full = (candidate.t0, candidate.t1)
    words = [w for w in (mud.words if mud else []) if w.t0 >= full[0] - 0.05 and w.t1 <= full[1] + 0.05]
    options: list[tuple[str, float, float]] = [("whole", *full)]
    if words:
        options.append(("tight", words[0].t0, words[-1].t1))
        middle = len(words) // 2
        half = max(1, len(words) // 4)
        core = words[max(0, middle - half):middle + half + 1]
        options.append(("core", core[0].t0, core[-1].t1))
        first_end = next((w for w in words if w.text.rstrip().endswith((".", "?", "!"))), None)
        if first_end is not None:
            options.append(("first line", words[0].t0, first_end.t1))
    elif mud and mud.shots:
        inside = [s for s in mud.shots if s.t0 >= full[0] - 0.05 and s.t1 <= full[1] + 0.05]
        if len(inside) > 1:
            options.append(("first shot", inside[0].t0, inside[0].t1))
            best = max(inside, key=lambda s: (s.usable, -len(s.flags), s.motion))
            options.append(("best shot", best.t0, best.t1))
    whole = max(MIN_PIECE_SECONDS, full[1] - full[0])
    unique: dict[tuple[float, float], Variant] = {}
    for label, t0, t1 in options:
        t0, t1 = round(t0, 3), round(t1, 3)
        if t1 - t0 < MIN_PIECE_SECONDS or (t0, t1) in unique:
            continue
        penalty = QUALITY_PENALTY_PER_SECOND * _flagged_seconds(mud, t0, t1)
        value = candidate.score * 100 * ((t1 - t0) / whole) ** LENGTH_EXPONENT - penalty
        if candidate.must_include or candidate.hook:
            value += MUST_INCLUDE_BONUS
        unique[(t0, t1)] = Variant(candidate.asset, t0, t1, value, candidate.ref, label)
    return list(unique.values())[:MAX_VARIANTS]


def _flagged_seconds(mud: MUD | None, t0: float, t1: float) -> float:
    if mud is None:
        return 0.0
    return sum(max(0.0, min(t1, q.t1) - max(t0, q.t0)) for q in mud.quality)


def fit(candidates: Sequence[Candidate], muds: dict[str, MUD], target_seconds: float, fps: int,
        tolerance_seconds: float | None = None) -> TimingResult:
    """The best set of trims, in the candidates' order, totalling target ± tolerance frames."""
    target = round(target_seconds * fps)
    tolerance = round((tolerance_seconds if tolerance_seconds is not None else max(0.5, target_seconds * 0.03)) * fps)
    groups = [variants(c, muds.get(c.asset)) for c in candidates]
    required = [c.must_include or c.hook for c in candidates]
    warnings: list[str] = []

    # Reserve the hook and must-includes at their shortest trims if even those overshoot.
    floor = sum(min(v.frames(fps) for v in g) for g, need in zip(groups, required) if need and g)
    if floor > target + tolerance:
        warnings.append(f"The moments that must stay already run {floor / fps:.1f}s, past the {target_seconds:.1f}s "
                        "target; kept them all at their shortest.")
        pieces = [min(g, key=lambda v: v.frames(fps)) for g, need in zip(groups, required) if need and g]
        return TimingResult(pieces, sum(p.frames(fps) for p in pieces), target, warnings)

    step = max(1, (target + tolerance) // DP_BUCKETS)
    cap = (target + tolerance) // step
    neg = float("-inf")
    best = [neg] * (cap + 1)
    best[0] = 0.0
    choice: list[list[int]] = []  # choice[g][w] = variant index taken at group g to reach weight w, -1 = skipped
    for g, (group, need) in enumerate(zip(groups, required)):
        nxt = [neg] * (cap + 1) if need else best[:]
        took = [-1] * (cap + 1)
        for w, value in enumerate(best):
            if value == neg:
                continue
            for index, variant in enumerate(group):
                w2 = w + -(-variant.frames(fps) // step)
                if w2 <= cap and value + variant.value > nxt[w2]:
                    nxt[w2] = value + variant.value
                    took[w2] = index
        best = nxt
        choice.append(took)

    low = max(0, (target - tolerance) // step)
    reachable = [w for w in range(low, cap + 1) if best[w] != neg]
    if not reachable:
        reachable = [w for w in range(cap + 1) if best[w] != neg]
        warnings.append(f"The footage is too short to reach {target_seconds:.1f}s; used all of the best of it.")
    if not reachable:
        return TimingResult([], 0, target, warnings + ["No moments could be placed."])
    end = max(reachable, key=lambda w: (best[w], -abs(w * step - target)))

    # choice[g][w] is the trim that gave the best value at w after group g (-1: the group was skipped).
    picked: list[Variant] = []
    w = end
    for g in range(len(groups) - 1, -1, -1):
        index = choice[g][w]
        if index >= 0:
            picked.append(groups[g][index])
            w -= -(-groups[g][index].frames(fps) // step)
    picked.reverse()
    hooks = [p for p, c in zip(picked, candidates) if c.hook]
    ordered = hooks + [p for p in picked if p not in hooks]
    return TimingResult(ordered, sum(p.frames(fps) for p in ordered), target, warnings)

