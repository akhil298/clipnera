"""Music from the library (scripts/build_music_library.py): pick a track for the reel and line it up with the edit.

A track is picked by mood (the director's), energy (picture reels and fast recipes want more), tempo (picture
reels cut on its beat, so 85-135 BPM) and length, preferring tracks used less. It starts on a downbeat chosen
so that one of its measured drops lands on the reveal, and picture reels are cut on its beat from there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / "static" / "motion" / "music" / "library"
NEIGHBOURS = {
    "upbeat": ("energetic", "inspiring", "funny"), "energetic": ("upbeat", "urban"), "chill": ("lofi", "corporate"),
    "lofi": ("chill",), "cinematic": ("inspiring", "dramatic"), "inspiring": ("cinematic", "upbeat"),
    "dramatic": ("cinematic",), "corporate": ("chill", "inspiring"), "funny": ("upbeat",), "urban": ("energetic", "chill"),
}
WANT_ENERGY = {"upbeat": 0.6, "energetic": 0.75, "chill": 0.4, "lofi": 0.4, "cinematic": 0.55, "inspiring": 0.55,
               "dramatic": 0.55, "corporate": 0.5, "funny": 0.55, "urban": 0.6}
DROP_TOLERANCE = 0.35


@dataclass(frozen=True)
class Track:
    key: str
    path: Path
    title: str
    mood: str
    bpm: float
    seconds: float
    energy: float
    downbeats: tuple[float, ...]
    drops: tuple[tuple[float, float], ...]
    licence: str
    source: str

    @property
    def beat(self) -> float:
        bpm = self.bpm
        while bpm > 0 and bpm < 80:
            bpm *= 2
        while bpm > 160:
            bpm /= 2
        return 60.0 / bpm if bpm else 60 / 112


@lru_cache(maxsize=1)
def library() -> tuple[Track, ...]:
    manifest = LIBRARY / "manifest.json"
    if not manifest.exists():
        return ()
    out = []
    for key, entry in json.loads(manifest.read_text()).items():
        path = LIBRARY / entry["file"]
        if path.exists() and entry.get("bpm"):
            out.append(Track(key=key, path=path, title=entry["title"], mood=entry["mood"], bpm=float(entry["bpm"]),
                             seconds=float(entry["seconds"]), energy=float(entry.get("energy", 0.5)),
                             downbeats=tuple(entry.get("downbeats") or [entry.get("first_downbeat", 0.0)]),
                             drops=tuple((float(d["t"]), float(d["strength"])) for d in entry.get("drops") or []),
                             licence=entry.get("licence", ""), source=entry.get("source", "")))
    return tuple(out)


def pick(mood: str, seconds: float, picture: bool, avoid: set[str] = frozenset()) -> Track | None:
    """The best track for the reel's mood, energy and length; ``avoid`` holds keys used recently."""
    tracks = library()
    if not tracks:
        return None
    family = (mood, *NEIGHBOURS.get(mood, ()))
    want = WANT_ENERGY.get(mood, 0.55) + (0.1 if picture else 0.0)

    def cost(t: Track) -> float:
        mood_cost = 0.0 if t.mood == mood else 0.6 if t.mood in family else 2.0
        tempo_cost = 0.0 if not picture or 85 <= 60 / t.beat <= 135 else 0.8
        length_cost = 0.0 if t.seconds >= seconds + 4 else 3.0
        return mood_cost + tempo_cost + length_cost + abs(t.energy - want) * 1.5 + (1.0 if t.key in avoid else 0.0)

    return min(tracks, key=cost)


def offset(track: Track, reveal: float | None, seconds: float) -> float:
    """Where in the track the reel starts: a downbeat from which a drop lands on ``reveal``, with room for the reel."""
    starts = [d for d in track.downbeats if d + seconds <= track.seconds - 0.5] or [0.0]
    if reveal is not None and track.drops:
        best = None
        for start in starts:
            for t, strength in track.drops:
                miss = abs((t - start) - reveal)
                if miss <= DROP_TOLERANCE and (best is None or strength > best[0]):
                    best = (strength, start)
        if best:
            return round(best[1], 3)
        # No downbeat puts a drop exactly there: take the start that lands the strongest drop nearest the reveal.
        candidates = [(abs((t - s) - reveal) - strength, s) for s in starts for t, strength in track.drops if t - s >= 0]
        if candidates:
            return round(min(candidates)[1], 3)
    return round(starts[0], 3)
