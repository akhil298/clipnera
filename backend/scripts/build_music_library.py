"""Build the reel engine's music library from Mixkit's free stock music, measured for editing.

Each track is downloaded to ``static/motion/music/library/`` (gitignored; run this on every host that renders)
and measured: tempo, beats, downbeats, drops and loudness over time. ``manifest.json`` there lists each track
with its moods, genres, tempo, energy, first downbeat and drops, so the sound agent picks by mood and energy,
cuts picture reels to the track's own beat and lands a drop on the reveal.

    cd backend && venv/bin/python scripts/build_music_library.py [--per-mood 6]

Licence: Mixkit Stock Music Free License (royalty free, no attribution required; not for CDs, DVDs, games or
TV and radio broadcast). Confirm the full terms before relying on it commercially.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from understanding.analyzers import analyze_music  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "static" / "motion" / "music" / "library"
SITE = "https://mixkit.co/free-stock-music/"
LICENCE = "Mixkit Stock Music Free License"
AGENT = {"User-Agent": "Mozilla/5.0 (Clipnera music library builder)"}
# Our moods (the director's vocabulary) and the Mixkit pages and tags that feed each.
MOODS: dict[str, dict] = {
    "upbeat": {"pages": ["mood/upbeat/", "mood/happy/", "mood/positive/"], "tags": {"upbeat", "happy", "positive", "carefree", "cheerful", "fun"}},
    "energetic": {"pages": ["mood/energetic/", "mood/driving/", "tag/sports/"], "tags": {"energetic", "driving", "propulsive", "aggressive", "sports", "action", "exciting"}},
    "chill": {"pages": ["mood/relaxed/", "chillout/", "mood/calm/"], "tags": {"relaxed", "calm", "chillout", "mellow", "smooth", "relaxation"}},
    "lofi": {"pages": ["lo-fi-beats/", "tag/lo-fi/"], "tags": {"lo-fi beats", "lo-fi", "downtempo"}},
    "cinematic": {"pages": ["mood/epic/", "film-score/", "mood/hopeful/"], "tags": {"epic", "cinematic", "film score", "hopeful", "orchestral pop", "majestic"}},
    "inspiring": {"pages": ["mood/uplifting/", "tag/motivational/", "mood/hopeful/"], "tags": {"uplifting", "motivational", "inspiring", "hopeful", "triumphant"}},
    "dramatic": {"pages": ["mood/dramatic/", "mood/suspenseful/"], "tags": {"dramatic", "tension", "suspenseful", "serious", "dark"}},
    "corporate": {"pages": ["corporate-music/", "tag/technology/"], "tags": {"corporate music", "corporate", "technology", "underscore"}},
    "funny": {"pages": ["mood/playful/", "mood/quirky/", "tag/comedy/"], "tags": {"playful", "quirky", "humorous", "silly", "comedy", "whimsical"}},
    "urban": {"pages": ["hip-hop/", "trap/"], "tags": {"hip hop", "trap", "city", "urban"}},
}
SKIP = {"christmas", "horror", "scary", "nightmarish", "eerie", "wedding", "religious", "gregorian chant"}


def fetch(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def cards(page: str) -> list[dict]:
    """Every track card on a Mixkit listing page: id, title, tags, seconds."""
    out = []
    for block in re.split(r'data-audio-player-item-id-value="', page)[1:]:
        track_id = block.split('"', 1)[0]
        if not track_id.isdigit():
            continue
        title = re.search(r'item-grid-card__title[^>]*>\s*([^<]+?)\s*<', block)
        artist = re.search(r'item-grid-card__artist[^>]*>\s*(?:<[^>]+>\s*)*([^<]+?)\s*<', block)
        tags = [html.unescape(t).strip().lower() for t in re.findall(r'class="meta-links__link"[^>]*>([^<]+)</a>', block)]
        time = re.search(r'data-test-id="duration">\s*(\d+):(\d+)', block)
        out.append({"id": track_id, "title": html.unescape(title.group(1)) if title else f"Track {track_id}",
                    "artist": html.unescape(artist.group(1)) if artist else "", "tags": tags,
                    "seconds": int(time.group(1)) * 60 + int(time.group(2)) if time else 0})
    return out


def energy_curve(path: Path) -> tuple[float, list[float]]:
    import librosa

    signal, rate = librosa.load(str(path), sr=22050, mono=True)
    rms = librosa.feature.rms(y=signal, hop_length=rate // 2)[0]
    peak = float(rms.max()) or 1.0
    return round(float(np.mean(rms) / peak), 3), [round(float(v / peak), 3) for v in rms]


def measure(path: Path) -> dict:
    beats, music = analyze_music(str(path))
    energy, curve = energy_curve(path)
    downbeats = [b.t for b in beats if b.is_downbeat]
    return {"bpm": music.tempo_bpm, "first_downbeat": downbeats[0] if downbeats else (beats[0].t if beats else 0.0),
            "downbeats": downbeats[:400], "drops": [{"t": d.t, "strength": d.strength} for d in music.drops],
            "energy": energy, "energy_curve": curve}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-mood", type=int, default=6)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    seen: dict[str, dict] = {}
    for mood, spec in MOODS.items():
        found = []
        for page in spec["pages"]:
            try:
                found += cards(fetch(SITE + page))
            except Exception as exc:  # a missing category page is skipped
                print(f"  {page}: {exc}")
        picked = 0
        for card in found:
            tags = set(card["tags"])
            if card["id"] in seen or tags & SKIP or not tags & spec["tags"] or card["seconds"] and card["seconds"] < 60:
                continue
            seen[card["id"]] = {**card, "mood": mood}
            picked += 1
            if picked >= args.per_mood:
                break
        print(f"{mood}: {picked} tracks")
    for track_id, card in seen.items():
        key = f"mixkit_{track_id}"
        target = OUT / f"{key}.mp3"
        if not target.exists():
            # Downloaded beside the target, so the final rename never crosses filesystems (/tmp is often its own).
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir=OUT) as tmp:
                tmp.write(urllib.request.urlopen(urllib.request.Request(f"https://assets.mixkit.co/music/{track_id}/{track_id}.mp3",
                                                                        headers=AGENT), timeout=120).read())
            Path(tmp.name).replace(target)
        if key not in manifest or "bpm" not in manifest[key]:
            info = measure(target)
            seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(target)],
                                           capture_output=True, text=True).stdout or 0)
            manifest[key] = {"file": target.name, "title": card["title"], "artist": card["artist"], "mood": card["mood"],
                             "tags": card["tags"], "seconds": round(seconds, 2), "licence": LICENCE,
                             "source_url": f"https://mixkit.co/free-stock-music/?q={track_id}", "source": "mixkit", **info}
            print(f"  {key}: {card['title']} · {card['mood']} · {info['bpm']} bpm · energy {info['energy']}")
            manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(manifest)} tracks in {manifest_path}")


if __name__ == "__main__":
    main()
