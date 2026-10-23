"""Build the reel engine's sound-effect, motion-graphic and animated-emoji libraries from clean free sources.

    cd backend && venv/bin/python scripts/build_asset_libraries.py [sfx] [lottie] [emoji]

Each library lives under ``static/motion/`` (files gitignored; run this on every host that renders) with a tracked
``manifest.json`` that lists what each file is, the role the engine uses it for and its licence:

- ``sfx/library/``: Mixkit sound effects for transitions, impacts, risers and soft UI clicks, as 48 kHz WAV with
  leading silence trimmed. No beeps, alarms, dings or cartoon sounds: those read as noise over a voice.
  Licence: Mixkit Sound Effects Free License (no attribution).
- ``lottie/``: LottieFiles free animations (arrows, underlines, circles, bursts, confetti, check marks, follow and
  subscribe buttons...) as Lottie JSON the graphics renderer plays frame by frame. Licence: Lottie Simple License.
- ``emoji/``: Google's Noto animated emoji as Lottie JSON. Licence: CC BY 4.0 (credit "Animated emoji by Google").
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MOTION = Path(__file__).resolve().parents[1] / "static" / "motion"
AGENT = {"User-Agent": "Mozilla/5.0 (Clipnera asset library builder)"}

# ------------------------------------------------------------------ sound effects

SFX_SITE = "https://mixkit.co/free-sound-effects/"
SFX_LICENCE = "Mixkit Sound Effects Free License"
# Our roles and the Mixkit categories that feed each.
SFX_ROLES = {
    "whoosh": ["whoosh", "woosh", "swoosh", "swish", "whip", "sweep"],
    "transition": ["transition", "slide", "zoom", "glitch", "spin", "rewind"],
    "impact": ["impact", "thud", "stomp", "cinematic"],
    "riser": ["swell"],
    "click": ["click", "interface", "camera", "keyboard", "type", "typewriter"],
}
SFX_SKIP = {"beep", "bleep", "buzzer", "alarm", "alert", "error", "notification", "ding", "bell", "cartoon", "fart", "laugh",
            "phone", "ring", "siren", "scream", "horror", "scary", "game over", "arcade", "video game"}
SFX_MAX_SECONDS = 6
# Every sound sits at the level of our own whoosh, so one effect gain suits them all (none blasts over a voice).
SFX_LUFS, SFX_SHORT_PEAK_DB, SFX_MAX_PEAK_DB = -19.0, -6.0, -1.0
SFX_PAGES = 2

# ------------------------------------------------------------------ motion graphics

LOTTIE_API = "https://graphql.lottiefiles.com/2022-08"
LOTTIE_LICENCE = "Lottie Simple License (LottieFiles free animation)"
# Role -> searches. Roles are what the engine asks for; each search adds a few animations to that role.
LOTTIE_ROLES = {
    "arrow": ["arrow pointing", "hand drawn arrow", "curved arrow", "arrow down"],
    "underline": ["underline", "brush stroke", "highlight marker"],
    "circle": ["circle scribble", "hand drawn circle", "circle highlight"],
    "burst": ["burst", "sparkle", "shine", "star burst"],
    "confetti": ["confetti", "celebration", "fireworks"],
    "check": ["check mark", "success tick", "checkbox"],
    "cross": ["cross mark", "wrong", "error x"],
    "follow": ["subscribe button", "follow button", "like button", "bell notification icon"],
    "swipe": ["swipe up", "scroll down", "tap here"],
    "money": ["money", "coins", "dollar"],
    "growth": ["growth chart", "graph up", "rocket launch"],
    "idea": ["light bulb idea", "brain thinking"],
    "time": ["clock", "hourglass", "timer"],
    "heart": ["heart like", "love heart"],
    "fire": ["fire flame", "hot trending"],
    "warning": ["warning sign", "attention"],
    "loading": ["loading dots", "progress loader"],
    "location": ["location pin", "map pin"],
    "phone": ["smartphone", "mobile app"],
    "chat": ["chat bubble", "message"],
}
LOTTIE_PER_SEARCH = 6
LOTTIE_MAX_BYTES = 900_000

# ------------------------------------------------------------------ animated emoji

EMOJI_LIST = "https://googlefonts.github.io/noto-emoji-animation/data/api.json"
EMOJI_URL = "https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/lottie.json"
EMOJI_LICENCE = "CC BY 4.0 (Animated emoji by Google, Noto Emoji)"


def fetch(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers={**AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=60) as r:
        return r.read()


def save_manifest(folder: Path, entries: dict, licence: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps({"licence": licence, "count": len(entries), "entries": entries},
                                                     indent=1, ensure_ascii=False))


def old_manifest(folder: Path) -> dict:
    path = folder / "manifest.json"
    return json.loads(path.read_text()).get("entries", {}) if path.exists() else {}


# ------------------------------------------------------------------ sfx

def sfx_cards(page: str) -> list[dict]:
    out = []
    for block in re.split(r'data-audio-player-item-id-value="', page)[1:]:
        sid = block.split('"', 1)[0]
        if not sid.isdigit():
            continue
        title = re.search(r'item-grid-card__title[^>]*>\s*([^<]+?)\s*<', block)
        tags = [html.unescape(t).strip().lower() for t in re.findall(r'class="meta-links__link"[^>]*>([^<]+)</a>', block)]
        time = re.search(r'data-test-id="duration">\s*(\d+):(\d+)', block)
        out.append({"id": sid, "title": html.unescape(title.group(1)) if title else f"Sound {sid}", "tags": tags,
                    "seconds": int(time.group(1)) * 60 + int(time.group(2)) if time else 0})
    return out


def sfx_wanted(card: dict) -> bool:
    words = f"{card['title']} {' '.join(card['tags'])}".lower()
    return 0 < card["seconds"] <= SFX_MAX_SECONDS and not any(s in words for s in SFX_SKIP)


def levels(path: Path) -> tuple[float | None, float]:
    """(integrated loudness LUFS or None when too short to measure, true peak dBFS)."""
    text = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    summary = text.rsplit("Summary:", 1)[-1]
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    value = float(lufs.group(1)) if lufs else -70.0
    return (value if value > -60 else None), (float(peak.group(1)) if peak and peak.group(1) != "-inf" else -70.0)


def level(path: Path) -> float:
    """Bring ``path`` to the library level in place; returns the gain applied in dB."""
    lufs, peak = levels(path)
    gain = (SFX_LUFS - lufs) if lufs is not None else (SFX_SHORT_PEAK_DB - peak)
    gain = min(gain, SFX_MAX_PEAK_DB - peak)
    if abs(gain) >= 0.5:
        tmp = path.with_suffix(".tmp.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-af", f"volume={gain:.2f}dB", str(tmp)], check=True)
        tmp.replace(path)
    return round(gain, 1)


def sfx_save(card: dict, role: str, folder: Path) -> dict | None:
    out = folder / f"mk_{card['id']}.wav"
    if not out.exists():
        mp3 = fetch(f"https://assets.mixkit.co/active_storage/sfx/{card['id']}/{card['id']}-preview.mp3")
        tmp = folder / f"mk_{card['id']}.mp3"
        tmp.write_bytes(mp3)
        done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", "silenceremove=start_periods=1:start_threshold=-50dB",
                               "-ar", "48000", "-ac", "2", str(out)], capture_output=True)
        tmp.unlink(missing_ok=True)
        if done.returncode:
            return None
        level(out)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True)
    return {"file": out.name, "role": role, "title": card["title"], "tags": card["tags"],
            "seconds": round(float(probe.stdout or 0), 2), "source": f"mixkit sfx {card['id']}", "licence": SFX_LICENCE}


def build_sfx() -> None:
    folder = MOTION / "sfx" / "library"
    folder.mkdir(parents=True, exist_ok=True)
    entries = old_manifest(folder)
    jobs: dict[str, tuple[dict, str]] = {}
    for role, categories in SFX_ROLES.items():
        for category in categories:
            for page in range(1, SFX_PAGES + 1):
                url = f"{SFX_SITE}{category}/" + (f"?page={page}" if page > 1 else "")
                try:
                    found = sfx_cards(fetch(url).decode("utf-8", "ignore"))
                except Exception as exc:
                    print(f"  skip {url}: {exc}")
                    break
                for card in found:
                    key = f"mk_{card['id']}"
                    if sfx_wanted(card) and key not in entries and key not in jobs:
                        jobs[key] = (card, role)
                if not found:
                    break
    print(f"sfx: {len(jobs)} new sounds to fetch")
    with cf.ThreadPoolExecutor(8) as ex:
        for key, entry in zip(jobs, ex.map(lambda j: sfx_save(j[0], j[1], folder), jobs.values())):
            if entry:
                entries[key] = entry
    save_manifest(folder, entries, SFX_LICENCE)
    print(f"sfx: {len(entries)} sounds; by role " + ", ".join(f"{r} {sum(e['role'] == r for e in entries.values())}" for r in SFX_ROLES))


# ------------------------------------------------------------------ lottie

def lottie_search(query: str, first: int) -> list[dict]:
    body = json.dumps({"query": "query($q: String!, $n: Int) { searchPublicAnimations(query: $q, first: $n) { edges { node "
                                "{ id name jsonUrl createdBy { username } } } } }", "variables": {"q": query, "n": first}}).encode()
    data = json.loads(fetch(LOTTIE_API, body, {"content-type": "application/json"}))
    return [e["node"] for e in (data.get("data") or {}).get("searchPublicAnimations", {}).get("edges", [])]


def lottie_ok(raw: bytes) -> dict | None:
    """A playable vector animation: valid Lottie, not huge, no embedded raster images, a sane frame range."""
    if len(raw) > LOTTIE_MAX_BYTES:
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(doc, dict) or "layers" not in doc or doc.get("op", 0) <= doc.get("ip", 0):
        return None
    if any(isinstance(a, dict) and str(a.get("p", "")).startswith("data:image") for a in doc.get("assets", [])):
        return None
    fr = float(doc.get("fr") or 30)
    return {"w": doc.get("w"), "h": doc.get("h"), "seconds": round((doc["op"] - doc.get("ip", 0)) / fr, 2), "fps": fr}


def build_lottie() -> None:
    folder = MOTION / "lottie"
    folder.mkdir(parents=True, exist_ok=True)
    entries = old_manifest(folder)
    jobs = []
    for role, searches in LOTTIE_ROLES.items():
        for query in searches:
            try:
                for node in lottie_search(query, LOTTIE_PER_SEARCH):
                    key = f"lf_{node['id']}"
                    if key not in entries and node.get("jsonUrl") and all(j[0] != key for j in jobs):
                        jobs.append((key, role, query, node))
            except Exception as exc:
                print(f"  skip search {query!r}: {exc}")
    print(f"lottie: {len(jobs)} new animations to check")

    def get(job):
        key, role, query, node = job
        try:
            raw = fetch(node["jsonUrl"])
        except Exception:
            return None
        meta = lottie_ok(raw)
        if not meta:
            return None
        (folder / f"{key}.json").write_bytes(raw)
        return key, {"file": f"{key}.json", "role": role, "name": node.get("name") or query, "query": query, **meta,
                     "source": f"lottiefiles {node['id']}", "licence": LOTTIE_LICENCE}

    with cf.ThreadPoolExecutor(8) as ex:
        for got in ex.map(get, jobs):
            if got:
                entries[got[0]] = got[1]
    save_manifest(folder, entries, LOTTIE_LICENCE)
    print(f"lottie: {len(entries)} animations; by role " + ", ".join(f"{r} {sum(e['role'] == r for e in entries.values())}" for r in LOTTIE_ROLES))


# ------------------------------------------------------------------ emoji

def build_emoji() -> None:
    folder = MOTION / "emoji"
    folder.mkdir(parents=True, exist_ok=True)
    entries = old_manifest(folder)
    icons = json.loads(fetch(EMOJI_LIST))["icons"]
    todo = [i for i in icons if f"e_{i['codepoint']}" not in entries]
    print(f"emoji: {len(todo)} new animated emoji to fetch")

    def get(icon):
        code = icon["codepoint"]
        try:
            raw = fetch(EMOJI_URL.format(code=code))
        except Exception:
            return None
        meta = lottie_ok(raw) if len(raw) <= 3 * LOTTIE_MAX_BYTES else None
        if not meta:
            return None
        (folder / f"e_{code}.json").write_bytes(raw)
        words = sorted({w for t in icon.get("tags", []) for w in t.strip(":").replace("-", " ").split()})
        return f"e_{code}", {"file": f"e_{code}.json", "codepoint": code, "words": words, "tags": icon.get("tags", []),
                             "categories": icon.get("categories", []), "popularity": icon.get("popularity", 0), **meta,
                             "source": "noto animated emoji", "licence": EMOJI_LICENCE}

    with cf.ThreadPoolExecutor(8) as ex:
        for got in ex.map(get, todo):
            if got:
                entries[got[0]] = got[1]
    save_manifest(folder, entries, EMOJI_LICENCE)
    print(f"emoji: {len(entries)} animated emoji")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("libraries", nargs="*", choices=["sfx", "lottie", "emoji"], help="which to build (default: all)")
    for name in parser.parse_args().libraries or ["sfx", "lottie", "emoji"]:
        {"sfx": build_sfx, "lottie": build_lottie, "emoji": build_emoji}[name]()


if __name__ == "__main__":
    main()
