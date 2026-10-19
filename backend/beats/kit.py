"""The clean motion kit: assets a beat may show, found by the words that were said.

The kit lives in ``static/motion/kit`` (layout and sources in
``docs/motion_kit/ASSET_KIT.md``); ``manifest.json`` is the only thing read.
An asset is only picked when one of its trigger words was spoken, and only
when its file is on disk, so a missing download never puts a broken graphic
on screen.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

DEFAULT_KIT_DIR = Path(__file__).resolve().parent.parent / "static" / "motion" / "kit"
_WORD = re.compile(r"[\w₹$€£%]+", re.UNICODE)
# Words that never pick an asset on their own.
STOP = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "was", "it", "this", "that",
    "my", "your", "our", "i", "you", "we", "they", "he", "she", "be", "so", "very", "really", "just", "like",
})


def kit_dir() -> Path:
    configured = (getattr(get_settings(), "MOTION_KIT_DIR", "") or "").strip()
    return Path(configured) if configured else DEFAULT_KIT_DIR


def words_of(text: str) -> set[str]:
    """Lower-case words and their singulars, without stop words."""
    out: set[str] = set()
    for word in _WORD.findall((text or "").lower()):
        if word in STOP:
            continue
        out.add(word)
        if len(word) > 3 and word.endswith("es"):
            out.add(word[:-2])
        if len(word) > 2 and word.endswith("s"):
            out.add(word[:-1])
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


@lru_cache(maxsize=1)
def manifest() -> tuple[dict[str, Any], ...]:
    path = kit_dir() / "manifest.json"
    if not path.is_file():
        log.info("Motion kit has no manifest at %s; beats needing assets are skipped", path)
        return ()
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("assets") or []
    except (ValueError, OSError) as exc:
        log.warning("Motion kit manifest is unreadable: %s", exc)
        return ()
    return tuple(entry for entry in entries if isinstance(entry, dict) and entry.get("path"))


def find(kinds: tuple[str, ...], said: str, wanted: str = "") -> dict[str, Any] | None:
    """The asset of one of ``kinds`` whose trigger words best match ``wanted``, among words in ``said``.

    ``wanted`` is the thing to show ("rupee coin"); only its words that were
    actually spoken count, so the model cannot ask for a picture of something
    nobody mentioned.
    """
    spoken = words_of(said)
    asked = words_of(wanted) & spoken if wanted else spoken
    if not asked:
        return None
    best, best_score = None, 0
    for entry in manifest():
        if entry.get("kind") not in kinds:
            continue
        triggers = {w.lower() for w in entry.get("words") or []}
        score = len(asked & triggers) * 2 + len(spoken & triggers)
        if score > best_score and asked & triggers and path_of(entry):
            best, best_score = entry, score
    return best


def logo(name: str) -> dict[str, Any] | None:
    """The brand logo for a name said aloud, matched on its slug."""
    key = slug(name)
    if not key:
        return None
    for entry in manifest():
        if entry.get("kind") == "logo" and (slug(entry.get("id", "").removeprefix("logo.")) == key
                                            or key in {slug(w) for w in entry.get("words") or []}):
            return entry if path_of(entry) else None
    return None


def path_of(entry: dict[str, Any]) -> Path | None:
    """The asset's file on disk, or ``None`` when it was never synced here."""
    path = kit_dir() / str(entry.get("path") or "")
    return path if path.is_file() else None
