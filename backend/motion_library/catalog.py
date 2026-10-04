"""The local motion library: animated emoji, overlays and transitions an edit may use.

One file, ``catalog.json`` at the library root, lists every asset with its
kind, category, keywords, files and licence. Whatever picks an asset -- a
prompt or an agent tool -- searches that file and answers with an asset id, so
a model can never name a file that is not there.

The library is optional. A deployment without the folder has an empty library
and every search finds nothing, which callers report as "not found" rather
than fail.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

CATALOG_NAME = "catalog.json"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "motion_assets"
KINDS = ("animated_emoji", "overlay", "transition", "motion_graphic", "green_screen")

# How much a query word counts when it matches each part of an asset.
ID_WEIGHT, KEYWORD_WEIGHT, CATEGORY_WEIGHT, TEXT_WEIGHT = 3, 2, 2, 1
_WORD = re.compile(r"[a-z0-9]+")
# Words in every description, which would match every asset.
_FILLER = frozenset({"the", "and", "for", "with", "one"})


@dataclass(frozen=True)
class MotionAsset:
    id: str
    kind: str
    category: str
    keywords: tuple[str, ...]
    description: str
    use_when: str
    # Paths relative to the library root, by role: "video", or "lottie" and "gif".
    files: dict[str, str]
    width: int
    height: int
    fps: float
    duration_s: float
    transparent: bool
    loops: bool
    blend_mode: str

    def summary(self) -> dict[str, Any]:
        """The asset as a model reads it when choosing."""
        return {
            "id": self.id, "kind": self.kind, "category": self.category, "description": self.description,
            "use_when": self.use_when, "files": self.files, "size": [self.width, self.height],
            "duration_s": self.duration_s, "loops": self.loops, "transparent": self.transparent,
            "blend_mode": self.blend_mode,
        }


def library_root() -> Path:
    configured = get_settings().MOTION_LIBRARY_DIR.strip()
    return Path(configured).expanduser() if configured else DEFAULT_ROOT


def _words(text: str) -> set[str]:
    """Lower-case words of three letters or more, a plural 's' dropped so "sparkles" finds "sparkle"."""
    return {
        w[:-1] if len(w) > 3 and w.endswith("s") else w
        for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _FILLER
    }


def _usable(entry: dict[str, Any], root: Path) -> bool:
    if (entry.get("license") or {}).get("commercial_ok") is not True:
        return False
    return all((root / path).is_file() for path in (entry.get("files") or {}).values())


@lru_cache(maxsize=4)
def _read(catalog_path: str, modified_ns: int) -> tuple[MotionAsset, ...]:
    root = Path(catalog_path).parent
    entries = json.loads(Path(catalog_path).read_text(encoding="utf-8")).get("assets") or []
    usable = [e for e in entries if e.get("kind") in KINDS and _usable(e, root)]
    if len(usable) != len(entries):
        log.info("Motion library: %d of %d assets are usable (licence cleared, files present)", len(usable), len(entries))
    return tuple(
        MotionAsset(
            id=e["id"], kind=e["kind"], category=e["category"], keywords=tuple(e.get("keywords") or ()),
            description=e.get("description", ""), use_when=e.get("use_when", ""), files=dict(e["files"]),
            width=int(e["width"]), height=int(e["height"]), fps=float(e["fps"]), duration_s=float(e["duration_s"]),
            transparent=bool(e.get("transparent")), loops=bool(e.get("loops")), blend_mode=e.get("blend_mode", "normal"),
        )
        for e in usable
    )


def load_assets() -> tuple[MotionAsset, ...]:
    """Every asset that may be used: licence cleared for commercial use and its files on disk."""
    catalog = library_root() / CATALOG_NAME
    if not catalog.is_file():
        return ()
    return _read(str(catalog), catalog.stat().st_mtime_ns)


def _score(asset: MotionAsset, query: set[str]) -> int:
    fields = (
        (ID_WEIGHT, _words(asset.id)),
        (KEYWORD_WEIGHT, _words(" ".join(asset.keywords))),
        (CATEGORY_WEIGHT, _words(asset.category)),
        (TEXT_WEIGHT, _words(f"{asset.description} {asset.use_when}")),
    )
    return sum(max((weight for weight, words in fields if word in words), default=0) for word in query)


def find_assets(query: str, kind: str | None = None, limit: int = 5) -> list[MotionAsset]:
    """The assets that best match ``query``, best first; empty when nothing in the library fits."""
    words = _words(query)
    scored = [
        (_score(asset, words), asset) for asset in load_assets() if kind is None or asset.kind == kind
    ]
    ranked = sorted((pair for pair in scored if pair[0] > 0), key=lambda pair: (-pair[0], pair[1].id))
    return [asset for _, asset in ranked[:limit]]
