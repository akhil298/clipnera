"""Move the raw editing library into category folders under static/motion.

Original relative paths are preserved below each category so duplicate
filenames never collide. An organization manifest records each old path.

Run from the repository root with:

    backend/venv/bin/python backend/scripts/organize_motion_library.py --dry-run
    backend/venv/bin/python backend/scripts/organize_motion_library.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.index_motion_library import (
    ASSET_ROOT,
    BACKEND,
    _asset_type,
    _category,
)

SOURCE_ROOT = BACKEND / "library"
DESTINATION_ROOT = ASSET_ROOT / "library"
MANIFEST_PATH = DESTINATION_ROOT / "organization.json"


def _assets() -> list[tuple[Path, Path, str]]:
    assets = []
    for source in SOURCE_ROOT.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(SOURCE_ROOT)
        category = _category(relative, _asset_type(source))
        target = DESTINATION_ROOT / category / relative
        assets.append((source, target, category))
    return assets


def _write_manifest(mapping: dict[str, str]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {"version": 1, "organized_root": "backend/static/motion/library", "assets": mapping},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(MANIFEST_PATH)


def organize(dry_run: bool = False) -> dict[str, Any]:
    if not SOURCE_ROOT.is_dir():
        if MANIFEST_PATH.is_file():
            mapping = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("assets", {})
            return {
                "files": 0,
                "already_organized": True,
                "organized_files": len(mapping),
                "manifest": MANIFEST_PATH.relative_to(BACKEND).as_posix(),
            }
        raise FileNotFoundError(f"Raw asset library does not exist: {SOURCE_ROOT}")
    assets = _assets()
    counts = Counter(category for _, _, category in assets)
    if dry_run:
        return {"files": len(assets), "categories": dict(sorted(counts.items()))}

    mapping: dict[str, str] = {}
    if MANIFEST_PATH.is_file():
        stored = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        mapping.update(stored.get("assets", {}))

    for index, (source, target, _) in enumerate(assets, start=1):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite an existing asset: {target}")
        os.replace(source, target)
        mapping[target.relative_to(BACKEND).as_posix()] = source.relative_to(BACKEND).as_posix()
        if index % 500 == 0:
            _write_manifest(mapping)

    _write_manifest(mapping)
    for directory in sorted(SOURCE_ROOT.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass
    try:
        SOURCE_ROOT.rmdir()
    except OSError:
        pass
    return {
        "files": len(assets),
        "categories": dict(sorted(counts.items())),
        "manifest": MANIFEST_PATH.relative_to(BACKEND).as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show category totals without moving files")
    args = parser.parse_args()
    try:
        result = organize(dry_run=args.dry_run)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Asset organization failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
