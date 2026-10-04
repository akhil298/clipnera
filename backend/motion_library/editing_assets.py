"""Editing assets: the hooks, music, effects and sound effects collected from studied reels.

A reel moves from the ``references/`` inbox to ``analyzed/`` once it is
measured (``measure``) and its notes (``analysis.json``, see ``analysis``)
validate. Everything under ``editing_assets/`` is then rebuilt from
``analyzed/``, so it can be deleted and regenerated at any time::

    analyzed/<reel>/                        reel.mp4, reference.json, measure/, analysis.json
    editing_assets/
      hook_collection/index.json            every hook: type, text, template, timing
      hook_collection/<reel>/hook.mp4
      music_collection/index.json           every soundtrack: mood, energy, bpm, drop, beats
      music_collection/<reel>/audio.m4a
      effect_collection/index.json          every technique: how to do it, examples by reel
      effect_collection/<technique>/<reel>_<n>.mp4
      sfx_collection/index.json             every sound effect heard, as one of our own sounds
      sfx_collection/<sound>/<reel>_<n>.m4a

The app reads only the ``index.json`` files, each cached until it changes, and
every path in them is relative to the library root, so the folders can move to
object storage behind a CDN without touching the code.

Clips cut from a reel are somebody else's footage and audio: their entries
carry ``license.commercial_ok`` false and nothing renders them into an export
until that changes. Hook templates, technique recipes and the sound ids (our
own synthesised sounds, see ``hook_transitions``) are free to use.

Run ``python -m motion_library.editing_assets`` to file every reel whose notes
are ready, or with ``--rebuild`` to regenerate the collections only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.logging_config import get_logger
from motion_library.analysis import HOOK_TYPES, TECHNIQUES, ReelAnalysis
from motion_library.catalog import _words, library_root
from motion_library.references import (
    ANALYZED_DIR, MEASURE_DIR, MEASUREMENTS_NAME, NOTES_NAME, REFERENCES_DIR, VIDEO_NAME,
)

log = get_logger(__name__)

ANALYSIS_NAME = "analysis.json"
ASSETS_DIR = "editing_assets"
HOOKS, MUSIC, EFFECTS, SFX = "hook_collection", "music_collection", "effect_collection", "sfx_collection"
COLLECTIONS = (HOOKS, MUSIC, EFFECTS, SFX)
INDEX_NAME = "index.json"
HOOK_CLIP, MUSIC_CLIP = "hook.mp4", "audio.m4a"
SCHEMA_VERSION = 1
REFERENCE_ONLY = {"commercial_ok": False, "note": "Cut from somebody else's reel; not cleared for exports."}
# Soundtracks with no music in them are not collected.
NO_MUSIC = frozenset({"voiceover", "silent"})
# An example clip spans this long around the moment: a little before, more after.
EFFECT_BEFORE_S, EFFECT_AFTER_S = 0.6, 0.9
SFX_BEFORE_S, SFX_AFTER_S = 0.15, 0.85
KEYWORD_WEIGHT, TEXT_WEIGHT = 2, 1


class NotesError(Exception):
    """A reel's notes are missing or do not validate; the reel stays in the inbox."""


def _assets(root: Path) -> Path:
    return root / ASSETS_DIR


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_json(path: Path, data: Any) -> None:
    """Written beside its final name and swapped in, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(partial, path)


def _cut(video: Path, target: Path, start: float, end: float, audio_only: bool = False) -> str | None:
    """``target`` holding ``video`` from ``start`` to ``end``, cut once; its path, or None if FFmpeg failed."""
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        streams = ["-vn", "-c:a", "aac", "-b:a", "192k"] if audio_only else [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart"]
        done = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end - start:.3f}",
             *streams, str(target)],
            capture_output=True,
        )
        if done.returncode != 0:
            log.warning("Could not cut %s: %s", target.name, done.stderr.decode(errors="replace")[-200:])
            return None
    return str(target)


def read_notes(folder: Path) -> tuple[ReelAnalysis, dict[str, Any], dict[str, Any]]:
    """A reel's notes, its saved details and its measurements."""
    try:
        analysis = ReelAnalysis.model_validate_json((folder / ANALYSIS_NAME).read_text(encoding="utf-8"))
        reference = json.loads((folder / NOTES_NAME).read_text(encoding="utf-8"))
        measured = json.loads((folder / MEASURE_DIR / MEASUREMENTS_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NotesError(f"{folder.name}: {Path(exc.filename).name} is missing") from exc
    except ValidationError as exc:
        raise NotesError(f"{folder.name}: {exc}") from exc
    return analysis, reference, measured


def ready(root: Path) -> list[Path]:
    """Inbox reels that are measured and have notes."""
    inbox = root / REFERENCES_DIR
    if not inbox.is_dir():
        return []
    return sorted(
        folder for folder in inbox.iterdir()
        if (folder / ANALYSIS_NAME).is_file() and (folder / MEASURE_DIR / MEASUREMENTS_NAME).is_file()
    )


def file_reel(folder: Path, root: Path) -> Path:
    """Move a studied reel out of the inbox into ``analyzed/``, once its notes validate."""
    read_notes(folder)
    target = root / ANALYZED_DIR / folder.name
    if target.exists():
        raise NotesError(f"{folder.name} is already analysed; edit {target / ANALYSIS_NAME} instead")
    target.parent.mkdir(parents=True, exist_ok=True)
    folder.rename(target)
    return target


class _Reel:
    """One analysed reel and the asset entries cut from it."""

    def __init__(self, folder: Path, root: Path) -> None:
        self.folder, self.root = folder, root
        self.analysis, reference, self.measured = read_notes(folder)
        self.video = folder / VIDEO_NAME
        self.source = {"reel": folder.name, "url": reference["source_url"], "creator": reference.get("creator", "")}

    def clip(self, target: Path, start: float, end: float, audio_only: bool = False) -> str | None:
        start, end = max(0.0, start), min(end, self.measured["duration_s"])
        cut = _cut(self.video, target, start, end, audio_only)
        return _relative(Path(cut), self.root) if cut else None

    def hook(self) -> dict[str, Any]:
        hook, words = self.analysis.hook, self.measured["speech"]["words"]
        end = min(hook.ends_s, self.measured["duration_s"])
        return {
            "id": self.folder.name, "type": hook.type, "type_meaning": HOOK_TYPES[hook.type], "ends_s": round(end, 2),
            "on_screen_text": hook.on_screen_text, "text_style": hook.text_style,
            "spoken": hook.spoken or " ".join(w["word"] for w in words if w["start_s"] < end),
            "visual": hook.visual, "why_it_works": hook.why_it_works, "template": hook.template,
            "cuts_s": [cut for cut in self.measured["cuts_s"] if cut < end],
            "music_mood": self.analysis.music.mood, "look": self.analysis.look,
            "keywords": [self.analysis.niche, hook.type, *self.analysis.tags],
            "clip": self.clip(_assets(self.root) / HOOKS / self.folder.name / HOOK_CLIP, 0.0, end),
            "source": self.source, "license": REFERENCE_ONLY,
        }

    def music(self) -> dict[str, Any] | None:
        music, sound = self.analysis.music, self.measured["sound"]
        if music.kind in NO_MUSIC or sound.get("silent"):
            return None
        return {
            "id": self.folder.name, "kind": music.kind, "mood": music.mood, "energy": music.energy,
            "vocals": music.vocals, "bpm": sound.get("bpm"), "drop_s": sound.get("drop_s"),
            "duration_s": self.measured["duration_s"], "beats_s": sound.get("beats_s", []),
            "loudness_half_seconds": sound.get("loudness_half_seconds", []),
            "sync": music.sync, "track_hint": music.track_hint,
            "keywords": [self.analysis.niche, music.mood, music.energy, music.kind, *self.analysis.tags],
            "clip": self.clip(_assets(self.root) / MUSIC / self.folder.name / MUSIC_CLIP,
                              0.0, self.measured["duration_s"], audio_only=True),
            "source": self.source, "license": REFERENCE_ONLY,
        }

    def effect_examples(self) -> list[tuple[str, dict[str, Any]]]:
        examples = []
        for technique in self.analysis.techniques:
            for n, at in enumerate(technique.at_s, start=1):
                target = _assets(self.root) / EFFECTS / technique.id / f"{self.folder.name}_{n}.mp4"
                examples.append((technique.id, {
                    "at_s": at, "note": technique.note, "niche": self.analysis.niche,
                    "clip": self.clip(target, at - EFFECT_BEFORE_S, at + EFFECT_AFTER_S),
                    "source": self.source, "license": REFERENCE_ONLY,
                }))
            if not technique.at_s:
                examples.append((technique.id, {
                    "at_s": None, "note": technique.note, "niche": self.analysis.niche, "clip": None,
                    "source": self.source,
                }))
        return examples

    def sfx_examples(self) -> list[tuple[str, dict[str, Any]]]:
        examples = []
        for effect in self.analysis.sound_effects:
            for n, at in enumerate(effect.at_s, start=1):
                target = _assets(self.root) / SFX / effect.id / f"{self.folder.name}_{n}.m4a"
                examples.append((effect.id, {
                    "at_s": at, "note": effect.note, "niche": self.analysis.niche,
                    "clip": self.clip(target, at - SFX_BEFORE_S, at + SFX_AFTER_S, audio_only=True),
                    "source": self.source, "license": REFERENCE_ONLY,
                }))
        return examples


def _grouped(pairs: list[tuple[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for id_, example in pairs:
        groups[id_].append(example)
    return groups


def rebuild(root: Path) -> dict[str, int]:
    """Regenerate every collection from ``analyzed/``; returns how many entries each holds."""
    reels = []
    for folder in sorted(p for p in (root / ANALYZED_DIR).glob("*") if p.is_dir()):
        try:
            reels.append(_Reel(folder, root))
        except NotesError as exc:
            log.warning("Skipping analysed reel: %s", exc)
    effects = _grouped([pair for reel in reels for pair in reel.effect_examples()])
    sounds = _grouped([pair for reel in reels for pair in reel.sfx_examples()])
    collections = {
        HOOKS: [reel.hook() for reel in reels],
        MUSIC: [track for reel in reels if (track := reel.music()) is not None],
        EFFECTS: [
            {"id": id_, "how": TECHNIQUES[id_][0], "maps_to": list(TECHNIQUES[id_][1]),
             "keywords": [id_.replace("_", " "), *{e["niche"] for e in examples}], "examples": examples}
            for id_, examples in sorted(effects.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
        SFX: [
            # Our own synthesised sound by this id is free to use; the examples show how the reels used one.
            {"id": id_, "usable_sound": id_, "keywords": [id_.replace("_", " ")], "examples": examples}
            for id_, examples in sorted(sounds.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
    }
    for name, entries in collections.items():
        _write_json(_assets(root) / name / INDEX_NAME, {"version": SCHEMA_VERSION, "count": len(entries), "entries": entries})
    return {name: len(entries) for name, entries in collections.items()}


@lru_cache(maxsize=8)
def _read_index(path: str, modified_ns: int) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(Path(path).read_text(encoding="utf-8")).get("entries") or ())


def load_index(collection: str) -> tuple[dict[str, Any], ...]:
    """One collection's entries; empty when it has not been built."""
    path = _assets(library_root()) / collection / INDEX_NAME
    if not path.is_file():
        return ()
    return _read_index(str(path), path.stat().st_mtime_ns)


def _score(entry: dict[str, Any], query: set[str]) -> int:
    keywords = _words(" ".join(entry["keywords"]))
    text = _words(" ".join(str(entry.get(field, "")) for field in ("visual", "template", "how", "sync", "track_hint")))
    return sum(KEYWORD_WEIGHT if word in keywords else TEXT_WEIGHT if word in text else 0 for word in query)


def find_editing_assets(collection: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    """The entries of ``collection`` that best match ``query``, best first; empty when none fits."""
    words = _words(query)
    scored = [(_score(entry, words), entry) for entry in load_index(collection)]
    ranked = sorted((pair for pair in scored if pair[0] > 0), key=lambda pair: (-pair[0], pair[1]["id"]))
    return [entry for _, entry in ranked[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rebuild", action="store_true", help="Only regenerate the collections from analyzed/.")
    args = parser.parse_args()
    root = library_root()
    if not args.rebuild:
        for folder in ready(root):
            try:
                print(f"filed {file_reel(folder, root).name}")
            except NotesError as exc:
                print(f"kept in inbox: {exc}")
    for name, count in rebuild(root).items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
