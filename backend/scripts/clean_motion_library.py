"""Remove what the local motion library does not need, and say why for each file.

The library (``static/motion/library``, gitignored) came from creator packs
on Google Drive. Removed:

* macOS leftovers (``.DS_Store``, ``._*`` forks, ``__MACOSX``);
* font formats no renderer here can load (Type 1 ``.pfm``/``.pfb``, Windows
  bitmap ``.fon``, WPF ``.compositefont``): libass and FFmpeg read TrueType
  and OpenType only;
* exact duplicates, keeping the copy with the most descriptive name;
* ZIP bundles whose every member is already unpacked in the library;
* downloads ripped from YouTube or Instagram (y2mate, Snapinsta, profile
  screenshots) whose source does not say they are free to use, and
  recognisable meme, game, TV and brand audio or art, which belong to someone
  else and can never go into an export.

``reference/`` (reels kept for testing) is left alone; it is never shipped.
Every removal is written to ``cleanup_report.json`` beside the library.

    cd backend
    venv/bin/python -m scripts.clean_motion_library            # dry run: lists what would go
    venv/bin/python -m scripts.clean_motion_library --apply    # removes it
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / "static" / "motion" / "library"
KEEP_UNTOUCHED = ("reference",)
UNUSABLE_SUFFIXES = {".pfm", ".pfb", ".fon", ".compositefont"}
MAC_JUNK = re.compile(r"(^\.DS_Store$|^\._)")
RIPPED = re.compile(r"y2mate|snapinsta|savefrom|ssstik|snaptik|screenshot-.*instagram", re.IGNORECASE)
# A download whose source says it is free to use is kept (and catalogued as
# "claimed free, verify"); the download tool says nothing about the rights.
CLAIMED_FREE = re.compile(
    r"youtube audio library|royalty.?free|no.?copyright|copyright.?free|creative commons|free (background|stock)|"
    r"stock video",
    re.IGNORECASE,
)
# Recognisable audio and art that belongs to games, shows, songs, memes or brands.
SOMEONE_ELSES = re.compile(
    r"mario|pac-?man|pakman|among us|\bgta\b|nani!|street fighter|bruh|faaah|oh nooo|oh common men|pixel death|\btroll|"
    r"steve death|illuminati|prank bro|brodyquest|hallelujah|jingle.?bells|no god please no|needs some milk|"
    r"just do it|what the hell|derp|dip dip potato|look at this dude|bye have a great time|ready to rumble|"
    r"happy nation|anime wow|daaamn|aye sound|oh hello there|surprise mother|the builder|trickshot|\bmlg\b|"
    r"pokemon|why are you running|\bwwe\b|wait a minute|you have to say|yoloo|sad romance",
    re.IGNORECASE,
)
# Names that say nothing about the file; a duplicate with one loses to a described copy.
NOISE_NAME = re.compile(r"^(km_|img_|vid_|copy of |dsc|\d+[._ -])|\d{6,}", re.IGNORECASE)


def _digest(path: Path) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _name_quality(path: Path) -> tuple[int, int, str]:
    """Higher sorts first: a described name, then more words, then a stable tie-break."""
    stem = path.stem
    return (0 if NOISE_NAME.search(stem) else 1, len(re.findall(r"[A-Za-z]{3,}", stem)), str(path))


def _files() -> list[Path]:
    return [
        path for path in LIBRARY.rglob("*")
        if path.is_file() and path.relative_to(LIBRARY).parts[0] not in KEEP_UNTOUCHED
    ]


def plan() -> dict[str, str]:
    """``{relative path: reason}`` for every file to remove."""
    remove: dict[str, str] = {}
    files = _files()
    for path in files:
        rel = str(path.relative_to(LIBRARY))
        if MAC_JUNK.search(path.name) or "__MACOSX" in path.parts:
            remove[rel] = "macOS leftover"
        elif path.suffix.lower() in UNUSABLE_SUFFIXES:
            remove[rel] = f"font format no renderer here loads ({path.suffix.lower()})"
        elif RIPPED.search(path.name) and not CLAIMED_FREE.search(rel):
            remove[rel] = "ripped from YouTube or Instagram, rights unknown"
        elif SOMEONE_ELSES.search(path.name):
            remove[rel] = "someone else's recognisable audio or art (game, show, song, meme, brand)"

    survivors = [path for path in files if str(path.relative_to(LIBRARY)) not in remove]
    by_size: dict[int, list[Path]] = collections.defaultdict(list)
    for path in survivors:
        by_size[path.stat().st_size].append(path)
    for size, same_size in by_size.items():
        if size == 0 or len(same_size) < 2:
            continue
        by_hash: dict[str, list[Path]] = collections.defaultdict(list)
        for path in same_size:
            by_hash[_digest(path)].append(path)
        for copies in by_hash.values():
            keep, *extra = sorted(copies, key=_name_quality, reverse=True)
            for path in extra:
                remove[str(path.relative_to(LIBRARY))] = f"duplicate of {keep.relative_to(LIBRARY)}"

    unpacked = {(path.name.lower(), path.stat().st_size) for path in survivors if path.suffix.lower() != ".zip"}
    for path in survivors:
        if path.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(path) as bundle:
                members = [m for m in bundle.infolist() if not m.is_dir() and "__MACOSX" not in m.filename
                           and not Path(m.filename).name.startswith("._")]
        except zipfile.BadZipFile:
            remove[str(path.relative_to(LIBRARY))] = "unreadable ZIP"
            continue
        if members and all((Path(m.filename).name.lower(), m.file_size) in unpacked for m in members):
            remove[str(path.relative_to(LIBRARY))] = "ZIP whose contents are already unpacked"
    return remove


def apply(remove: dict[str, str]) -> None:
    for rel in remove:
        (LIBRARY / rel).unlink(missing_ok=True)
    for folder in sorted((p for p in LIBRARY.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="remove the files (default: list them only)")
    args = parser.parse_args()
    remove = plan()
    sizes = {rel: (LIBRARY / rel).stat().st_size for rel in remove}
    totals = collections.Counter()
    for rel, reason in remove.items():
        totals[reason.split(" of ")[0] if reason.startswith("duplicate") else reason] += sizes[rel]
    for reason, size in totals.most_common():
        count = sum(1 for r in remove.values() if (r.split(" of ")[0] if r.startswith("duplicate") else r) == reason)
        print(f"{count:6d} files {size / 1e6:9.1f} MB  {reason}")
    print(f"{len(remove):6d} files {sum(sizes.values()) / 1e6:9.1f} MB  in total")
    if args.apply:
        (LIBRARY.parent / "cleanup_report.json").write_text(json.dumps(remove, indent=1, sort_keys=True))
        apply(remove)
        print("removed; report written to", LIBRARY.parent / "cleanup_report.json")


if __name__ == "__main__":
    main()
