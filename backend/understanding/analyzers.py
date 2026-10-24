"""The MUD fields Clipnera had no analyzer for (MEDIA_INVENTORY.md), as pure functions.

Each takes data the existing analyzers already produced (words, shots, an audio
file) and returns MUD rows; none calls a model.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

import numpy as np

from content_intelligence.scorer import ClipScorer
from edit_engine.perception import BLUR_THRESHOLD, BRIGHT_THRESHOLD, DARK_THRESHOLD
from understanding.mud import Beat, Drop, Filler, Moment, Music, QualityFlag, Scene, Shot, Silence, Trim, Utterance, Word

# A gap between words longer than this is a pause; longer than DEAD_AIR, dead air.
PAUSE_SECONDS = 0.3
DEAD_AIR_SECONDS = 1.0
# Mean grey-level change between frames a second apart, at 256 px: above this the picture moves a lot
# (a shaky camera or fast action; this measure can't tell which). Static shots sit around 2-6.
FAST_MOTION = 25.0
# Scenes break at a pause this long, and are cut at a shot edge once they run this long.
SCENE_PAUSE_SECONDS = 1.5
SCENE_MAX_SECONDS = 45.0
MAX_MOMENTS = 40
# Action peaks need this many usable shots to compare, and score 1.0 at this much motion.
MIN_SHOTS_FOR_PEAKS = 4
# A line is an earlier take when one of the next few lines says it again this closely.
RETAKE_MIN_WORDS = 4
RETAKE_LOOKAHEAD = 3
RETAKE_SIMILARITY = 0.8
# A line is a quote moment at this score, with at least this many words.
QUOTE_SCORE = 0.2
MIN_QUOTE_WORDS = 4
# Lines kept as moments when the scorer rates none of them highly.
FALLBACK_QUOTES = 5
FULL_MOTION = 40.0
# Share of an audio file that must be speech before it is treated as voice, not music.
MUSIC_SPEECH_RATIO = 0.3

_HESITATIONS: dict[str, Filler] = {"um": "um", "umm": "um", "erm": "um", "hmm": "um", "uh": "uh", "uhh": "uh", "ah": "uh"}
_PAIRS: dict[tuple[str, str], Filler] = {("you", "know"): "you_know", ("i", "mean"): "i_mean"}


def _bare(text: str) -> str:
    return re.sub(r"[^\w']", "", text.lower())


def tag_fillers(words: Sequence[Word]) -> list[Word]:
    """Words with ``filler`` set where they read as filler rather than meaning."""
    tagged = [word.model_copy() for word in words]
    bare = [_bare(w.text) for w in tagged]
    for i, word in enumerate(tagged):
        previous = tagged[i - 1] if i else None
        after_pause = previous is None or word.t0 - previous.t1 >= PAUSE_SECONDS or previous.text.rstrip().endswith((".", "?", "!"))
        if bare[i] in _HESITATIONS:
            word.filler = _HESITATIONS[bare[i]]
        elif i + 1 < len(tagged) and (bare[i], bare[i + 1]) in _PAIRS and tagged[i + 1].text.rstrip().endswith(","):
            word.filler = tagged[i + 1].filler = _PAIRS[(bare[i], bare[i + 1])]
        elif bare[i] == "like" and (word.text.rstrip().endswith(",") or (previous and previous.text.rstrip().endswith(","))):
            word.filler = "like"
        elif bare[i] == "so" and after_pause and word.text.rstrip().endswith(","):
            word.filler = "so"
        elif previous and bare[i] and bare[i] == bare[i - 1] and word.t0 - previous.t1 < 0.5:
            # "I I think": the first of a stuttered pair is the one to cut.
            previous.filler = previous.filler or "repeat"
    # "I think I think", "you know what, you know what": a phrase said twice in a row; the first saying is cut.
    for n in (4, 3, 2):
        for i in range(len(tagged) - 2 * n + 1):
            first, again = bare[i:i + n], bare[i + n:i + 2 * n]
            if all(first) and first == again and tagged[i + n].t0 - tagged[i + n - 1].t1 < 1.0:
                for word in tagged[i:i + n]:
                    word.filler = word.filler or "repeat"
    return tagged


def find_silences(words: Sequence[Word], duration: float) -> list[Silence]:
    """Gaps with no words: before the first, between words, after the last."""
    if not words:
        return []
    edges = [0.0, *(t for w in words for t in (w.t0, w.t1)), duration]
    silences: list[Silence] = []
    for start, end in zip(edges[::2], edges[1::2]):
        gap = end - start
        if gap >= PAUSE_SECONDS:
            silences.append(Silence(t0=round(start, 3), t1=round(end, 3),
                                    kind="dead_air" if gap >= DEAD_AIR_SECONDS else "pause"))
    return silences


def shot_flags(shot: dict[str, Any]) -> list[str]:
    flags = []
    if shot["blur"] < BLUR_THRESHOLD:
        flags.append("blur")
    if shot["brightness"] < DARK_THRESHOLD:
        flags.append("dark")
    if shot["brightness"] > BRIGHT_THRESHOLD:
        flags.append("bright")
    if shot["motion"] > FAST_MOTION:
        flags.append("fast_motion")
    return flags


def quality_ranges(shots: Sequence[Shot]) -> list[QualityFlag]:
    """Each flag over the time it covers, touching shots merged into one range."""
    ranges: list[QualityFlag] = []
    for flag in sorted({f for shot in shots for f in shot.flags}):
        for shot in shots:
            if flag not in shot.flags:
                continue
            last = next((r for r in reversed(ranges) if r.flag == flag), None)
            if last and abs(last.t1 - shot.t0) < 0.01:
                last.t1 = shot.t1
            else:
                ranges.append(QualityFlag(flag=flag, t0=shot.t0, t1=shot.t1))
    return sorted(ranges, key=lambda r: (r.t0, r.flag))


def group_scenes(shots: Sequence[Shot], utterances: Sequence[Utterance], silences: Sequence[Silence],
                 duration: float) -> tuple[list[Scene], list[Shot]]:
    """Scenes of whole shots, broken where the speaker pauses long or a scene runs long.

    Without shots (audio), a scene is a stretch between long pauses. Returns the scenes and
    the shots with their ``scene_id`` set.
    """
    long_pauses = [s for s in silences if s.t1 - s.t0 >= SCENE_PAUSE_SECONDS]
    units = [(s.t0, s.t1) for s in shots] or _spans_between(long_pauses, duration)
    groups: list[list[int]] = []
    for index, (t0, _) in enumerate(units):
        if groups:
            first, previous = units[groups[-1][0]][0], units[groups[-1][-1]][0]
            # A long pause that ends after the last unit began and by the time this one begins.
            paused = any(previous < p.t1 <= t0 + 0.01 for p in long_pauses)
            if not paused and t0 - first < SCENE_MAX_SECONDS:
                groups[-1].append(index)
                continue
        groups.append([index])

    scenes: list[Scene] = []
    placed = [shot.model_copy() for shot in shots]
    for n, group in enumerate(groups):
        scene_id = f"sc{n:03d}"
        t0, t1 = units[group[0]][0], units[group[-1]][1]
        first_words = next((u.text for u in utterances if u.t1 > t0 and u.t0 < t1), None)
        for index in group:
            if placed:
                placed[index].scene_id = scene_id
        scenes.append(Scene(id=scene_id, t0=t0, t1=t1, shot_ids=[placed[i].id for i in group] if placed else [],
                            title=" ".join(first_words.split()[:8]) if first_words else None))
    return scenes, placed


def _spans_between(pauses: Sequence[Silence], duration: float) -> list[tuple[float, float]]:
    edges = [0.0, *(t for p in pauses for t in (p.t0, p.t1)), duration]
    return [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a > 0.05] or [(0.0, duration)]


def find_moments(utterances: Sequence[Utterance], shots: Sequence[Shot],
                 picks: Sequence[tuple[float, float, float, str]] = ()) -> list[Moment]:
    """Quote moments and action peaks (the busiest usable shots).

    ``picks`` are the quotes a model chose reading the transcript, as (score, t0, t1, why). Without
    them the clip scorer rates each line, and the best few are kept even when none rates highly:
    a recording with speech always has moments to cut from.
    """
    quotes = [(score, "quote", t0, t1, why) for score, t0, t1, why in picks] or _scored_quotes(utterances)
    found = list(quotes)
    motions = [s.motion for s in shots if s.usable]
    # Peaks only mean something against other shots: the busiest sixth of at least a few.
    if len(motions) >= MIN_SHOTS_FOR_PEAKS:
        high = float(np.percentile(motions, 85))
        for shot in shots:
            if shot.usable and shot.motion >= high and shot.motion > 8.0:
                found.append((min(1.0, shot.motion / FULL_MOTION), "action_peak", shot.t0, shot.t1, "most movement"))

    ranked = sorted(found, key=lambda m: (-m[0], m[2]))[:MAX_MOMENTS]
    moments = []
    for n, (score, kind, t0, t1, why) in enumerate(sorted(ranked, key=lambda m: m[2])):
        in_shots = [s.id for s in shots if s.t1 > t0 and s.t0 < t1]
        moments.append(Moment(id=f"m{n:03d}", t0=round(t0, 3), t1=round(t1, 3), score=round(score, 3),
                              kind=kind, why=why, shot_ids=in_shots))  # type: ignore[arg-type]
    return moments


def _scored_quotes(utterances: Sequence[Utterance]) -> list[tuple[float, str, float, float, str]]:
    """Each full line rated by the clip scorer: those over the bar, or the best few when none is."""
    rated = []
    for u in utterances:
        text, length = u.text.lower(), max(0.1, u.t1 - u.t0)
        if len(text.split()) < MIN_QUOTE_WORDS:
            continue
        parts = {
            "hook": ClipScorer._hook_score(text), "emotion": ClipScorer._engagement_score(text, length),
            "value": ClipScorer._value_score(text, length),
        }
        why = " + ".join(name for name, value in sorted(parts.items(), key=lambda kv: -kv[1]) if value >= 6) or "spoken line"
        rated.append((min(1.0, sum(parts.values()) / 75.0), "quote", u.t0, u.t1, why))
    strong = [quote for quote in rated if quote[0] >= QUOTE_SCORE]
    return strong or sorted(rated, key=lambda quote: -quote[0])[:FALLBACK_QUOTES]


def find_retakes(utterances: Sequence[Utterance]) -> list[Trim]:
    """Earlier takes of a line said again almost word for word within the next few lines."""
    trims = []
    for n, line in enumerate(utterances):
        words = _words(line.text)
        if len(words) < RETAKE_MIN_WORDS:
            continue
        again = next((later for later in utterances[n + 1:n + 1 + RETAKE_LOOKAHEAD]
                      if SequenceMatcher(None, words, _words(later.text)).ratio() >= RETAKE_SIMILARITY), None)
        if again is not None:
            trims.append(Trim(t0=line.t0, t1=line.t1, kind="retake", why="said again just after"))
    return trims


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def analyze_music(audio_path: str) -> tuple[list[Beat], Music]:
    """Beats, downbeats (4/4 assumed) and drops of a music file."""
    import librosa  # Imported here: it is slow to import and only music needs it.

    signal, rate = librosa.load(audio_path, sr=22050, mono=True)
    onset = librosa.onset.onset_strength(y=signal, sr=rate)
    tempo, frames = librosa.beat.beat_track(onset_envelope=onset, sr=rate)
    times = librosa.frames_to_time(frames, sr=rate)
    strengths = onset[frames] if len(frames) else np.array([])
    peak = float(strengths.max()) if len(strengths) else 1.0
    # The bar starts on whichever of the four beat phases is loudest overall.
    phase = int(np.argmax([strengths[p::4].sum() for p in range(4)])) if len(strengths) >= 4 else 0
    beats = [
        Beat(t=round(float(t), 3), is_downbeat=(i - phase) % 4 == 0, bar=(i - phase) // 4 + 1,
             beat_in_bar=(i - phase) % 4 + 1, conf=round(float(s) / peak, 3) if peak else 1.0)
        for i, (t, s) in enumerate(zip(times, strengths))
    ]
    return beats, Music(tempo_bpm=round(float(np.atleast_1d(tempo)[0]), 2), drops=_drops(signal, rate))


def _drops(signal: np.ndarray, rate: int, limit: int = 4) -> list[Drop]:
    """Where loudness jumps most, a second against the two before it."""
    import librosa

    hop = 512
    rms = librosa.feature.rms(y=signal, hop_length=hop)[0]
    per_second = int(rate / hop)
    if len(rms) < per_second * 4:
        return []
    window = np.convolve(rms, np.ones(per_second) / per_second, mode="same")
    rise = np.zeros_like(window)
    rise[per_second * 2:] = window[per_second * 2:] - window[: -per_second * 2]
    found: list[Drop] = []
    top = float(rise.max()) or 1.0
    for index in np.argsort(rise)[::-1]:
        if rise[index] <= 0 or len(found) == limit:
            break
        t = float(index * hop / rate)
        if all(abs(t - d.t) > 8.0 for d in found):
            found.append(Drop(t=round(t, 3), strength=round(float(rise[index]) / top, 3)))
    return sorted(found, key=lambda d: d.t)
