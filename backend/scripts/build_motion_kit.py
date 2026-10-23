"""Build Clipnera's clean motion kit in ``static/motion/kit`` (see docs/motion_kit/ASSET_KIT.md).

Only sources with a clean licence, each downloaded from its official home, its
licence saved verbatim, every asset given trigger words, and one manifest
written for the backend to read:

    fluent     Microsoft Fluent Emoji, 3D style (MIT)            -> icons/3d/fluent/*.png   kind object3d
    lucide     Lucide icons (ISC)                                -> icons/line/lucide/*.svg kind icon_line
    logos      Simple Icons (CC0 files; trademarks stay theirs)  -> logos/*.svg             kind logo
    maps       Natural Earth countries + India/US states (PD)    -> maps/*.svg              kind map
    textures   Poly Haven textures (CC0)                         -> backgrounds/*.jpg       kind background
    matte      MODNet portrait matting, ONNX (Apache-2.0)        -> models/modnet.onnx
    made       what scripts/generate_kit_images.py made          -> icons/3d/made, stills/  kinds object3d, still

    cd backend && venv/bin/python scripts/build_motion_kit.py                 # every source, then the manifest
    venv/bin/python scripts/build_motion_kit.py --only logos maps             # some sources
    venv/bin/python scripts/build_motion_kit.py --manifest                    # rebuild the manifest only
    venv/bin/python scripts/build_motion_kit.py --push | --pull               # one tarball per source in S3

Each source writes ``sources/<name>.json`` (its manifest entries); the
manifest is all of them merged, so a source can be rebuilt on its own.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beats.kit import kit_dir, slug  # noqa: E402

KIT = kit_dir()
SOURCES = KIT / "sources"
LICENSES = KIT / "LICENSES"
TODAY = date.today().isoformat()
UA = {"User-Agent": "clipnera-motion-kit/1.0"}

FLUENT_REPO = "https://github.com/microsoft/fluentui-emoji.git"
NPM = "https://registry.npmjs.org/{name}/latest"
NATURAL_EARTH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{layer}.geojson"
POLY_HAVEN = "https://api.polyhaven.com"
MODNET = "https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx"
MODNET_LICENSE = "https://raw.githubusercontent.com/ZHKKKe/MODNet/master/LICENSE"
# Poly Haven categories that make good card backgrounds, and how many of each.
TEXTURE_CATEGORIES = {"fabric": 3, "wood": 3, "marble": 2, "concrete": 2, "paper": 3, "plaster": 2}
ADMIN1_COUNTRIES = {"India", "United States of America"}
MAP_POINTS = 260
S3_PREFIX = "motion-kit"


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers=UA), timeout=120) as response:
        return response.read()


def fetch_json(url: str) -> Any:
    return json.loads(fetch(url))


def save_source(name: str, entries: list[dict[str, Any]]) -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    (SOURCES / f"{name}.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name}: {len(entries)} assets")


def save_licence(name: str, text: str | bytes) -> None:
    LICENSES.mkdir(parents=True, exist_ok=True)
    data = text.encode() if isinstance(text, str) else text
    (LICENSES / f"{name}.txt").write_bytes(data)


def entry(kind: str, ident: str, path: Path, words: list[str], source: str, url: str, licence: str, **extra: Any) -> dict[str, Any]:
    cleaned = sorted({w.strip().lower() for w in words if w and w.strip()})
    return {
        "id": ident, "kind": kind, "path": str(path.relative_to(KIT)), "words": cleaned, "source": source,
        "source_url": url, "licence": licence, "added": TODAY, **extra,
    }


def npm_tarball(name: str) -> tuple[str, tarfile.TarFile]:
    meta = fetch_json(NPM.format(name=name))
    return meta["version"], tarfile.open(fileobj=io.BytesIO(fetch(meta["dist"]["tarball"])), mode="r:gz")


# --- sources -----------------------------------------------------------------------------------------


def build_fluent() -> None:
    out = KIT / "icons" / "3d" / "fluent"
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "fluent"
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", FLUENT_REPO, str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", "--no-cone",
                        "/assets/*/3D/*", "/assets/*/Default/3D/*", "/assets/*/metadata.json", "/LICENSE"], check=True)
        save_licence("fluent-emoji", (repo / "LICENSE").read_bytes())
        for folder in sorted((repo / "assets").iterdir()):
            pngs = sorted(folder.glob("3D/*.png")) or sorted(folder.glob("Default/3D/*.png"))
            meta_path = folder / "metadata.json"
            if not pngs or not meta_path.is_file():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            name = slug(folder.name) or slug(meta.get("cldr", ""))
            target = out / f"{name}.png"
            shutil.copyfile(pngs[0], target)
            words = [*meta.get("keywords", []), meta.get("cldr", ""), folder.name, *folder.name.lower().split()]
            entries.append(entry("object3d", f"obj.fluent.{name}", target, words, "fluent-emoji", FLUENT_REPO, "MIT",
                                 style="glossy_3d", transparent=True))
    save_source("fluent", entries)


def build_lucide() -> None:
    out = KIT / "icons" / "line" / "lucide"
    out.mkdir(parents=True, exist_ok=True)
    version, tar = npm_tarball("lucide-static")
    tags = json.loads(tar.extractfile("package/tags.json").read()) if "package/tags.json" in tar.getnames() else {}
    for member in tar.getmembers():
        if member.name == "package/LICENSE":
            save_licence("lucide", tar.extractfile(member).read())
    entries = []
    for member in tar.getmembers():
        match = re.fullmatch(r"package/icons/([a-z0-9-]+)\.svg", member.name)
        if not match:
            continue
        name = match.group(1)
        target = out / f"{name}.svg"
        target.write_bytes(tar.extractfile(member).read())
        entries.append(entry("icon_line", f"icon.{name}", target, [*name.split("-"), *tags.get(name, [])], "lucide",
                             f"https://lucide.dev (lucide-static {version})", "ISC"))
    save_source("lucide", entries)


def build_logos() -> None:
    out = KIT / "logos"
    out.mkdir(parents=True, exist_ok=True)
    version, tar = npm_tarball("simple-icons")
    names = tar.getnames()
    data_name = next(n for n in names if n.endswith("simple-icons.json"))
    data = json.loads(tar.extractfile(data_name).read())
    icons = data["icons"] if isinstance(data, dict) else data
    save_licence("simple-icons", tar.extractfile("package/LICENSE.md").read() if "package/LICENSE.md" in names else "CC0-1.0")
    entries = []
    for icon in icons:
        icon_slug = icon.get("slug") or slug(icon["title"])
        member = f"package/icons/{icon_slug}.svg"
        if member not in names:
            continue
        svg = tar.extractfile(member).read().decode()
        # Brand colour in, so the tile shows the logo as people know it.
        svg = svg.replace("<svg ", f'<svg fill="#{icon.get("hex", "111111")}" ', 1)
        target = out / f"{icon_slug}.svg"
        target.write_text(svg, encoding="utf-8")
        aliases = icon.get("aliases") or {}
        words = [icon["title"], icon_slug, *aliases.get("aka", []), *(dup.get("title", "") for dup in aliases.get("dup", []))]
        entries.append(entry("logo", f"logo.{icon_slug}", target, words, "simple-icons", f"https://simpleicons.org (simple-icons {version})",
                             "CC0-1.0 (trademark of its owner)", hex=icon.get("hex", "")))
    save_source("logos", entries)


def _rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [polygon[0] for polygon in geometry["coordinates"]]
    return []


def _svg(rings: list[list[list[float]]]) -> str:
    """The rings as one SVG path, equirectangular with the latitude's squeeze, a few hundred points."""
    points = [p for ring in rings for p in ring]
    if not points:
        return ""
    lat0 = sum(p[1] for p in points) / len(points)
    squeeze = max(0.2, math.cos(math.radians(lat0)))
    xs = [p[0] * squeeze for p in points]
    ys = [-p[1] for p in points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = 100 / max(maxx - minx, maxy - miny, 1e-6)
    step = max(1, len(points) // MAP_POINTS)
    paths = []
    for ring in sorted(rings, key=len, reverse=True)[:12]:
        kept = ring[::step] if len(ring) > 3 * step else ring
        if len(kept) < 3:
            continue
        coords = " L".join(f"{(x * squeeze - minx) * scale:.1f},{(-y - miny) * scale:.1f}" for x, y in kept)
        paths.append(f"M{coords} Z")
    width, height = (maxx - minx) * scale, (maxy - miny) * scale
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {width + 4:.1f} {height + 4:.1f}">'
            f'<path d="{" ".join(paths)}"/></svg>')


def build_maps() -> None:
    out = KIT / "maps"
    out.mkdir(parents=True, exist_ok=True)
    save_licence("natural-earth", "Natural Earth: public domain. https://www.naturalearthdata.com/about/terms-of-use/\n")
    entries = []
    countries = fetch_json(NATURAL_EARTH.format(layer="ne_50m_admin_0_countries"))
    for feature in countries["features"]:
        props = feature["properties"]
        name = props.get("NAME") or props.get("ADMIN")
        svg = _svg(_rings(feature["geometry"]))
        if not name or not svg:
            continue
        target = out / f"country_{slug(name)}.svg"
        target.write_text(svg, encoding="utf-8")
        words = [name, props.get("NAME_LONG", ""), props.get("ADMIN", ""), props.get("NAME_EN", ""), props.get("NAME_HI", "")]
        entries.append(entry("map", f"map.country.{slug(name)}", target, words, "natural-earth", "https://www.naturalearthdata.com", "Public domain"))
    states = fetch_json(NATURAL_EARTH.format(layer="ne_10m_admin_1_states_provinces"))
    for feature in states["features"]:
        props = feature["properties"]
        if props.get("admin") not in ADMIN1_COUNTRIES:
            continue
        name = props.get("name") or props.get("name_en")
        svg = _svg(_rings(feature["geometry"]))
        if not name or not svg:
            continue
        country = "in" if props["admin"] == "India" else "us"
        target = out / f"state_{country}_{slug(name)}.svg"
        target.write_text(svg, encoding="utf-8")
        words = [name, props.get("name_en", ""), props.get("name_hi", ""), *(props.get("name_alt") or "").split("|")]
        entries.append(entry("map", f"map.state.{country}.{slug(name)}", target, words, "natural-earth", "https://www.naturalearthdata.com", "Public domain"))
    save_source("maps", entries)


def build_textures() -> None:
    out = KIT / "backgrounds" / "texture"
    out.mkdir(parents=True, exist_ok=True)
    save_licence("poly-haven", "Poly Haven assets: CC0 1.0. https://polyhaven.com/license\n")
    entries = []
    for category, count in TEXTURE_CATEGORIES.items():
        found = fetch_json(f"{POLY_HAVEN}/assets?t=textures&c={category}")
        for ident in sorted(found, key=lambda k: -found[k].get("download_count", 0))[:count]:
            files = fetch_json(f"{POLY_HAVEN}/files/{ident}")
            diffuse = files.get("Diffuse") or files.get("diffuse") or {}
            url = ((diffuse.get("2k") or {}).get("jpg") or {}).get("url")
            if not url:
                continue
            target = out / f"{ident}.jpg"
            target.write_bytes(fetch(url))
            tags = found[ident].get("tags", []) + found[ident].get("categories", [])
            entries.append(entry("background", f"bg.texture.{ident}", target, [category, *tags], "poly-haven",
                                 f"https://polyhaven.com/a/{ident}", "CC0-1.0"))
    save_source("textures", entries)


def build_matte() -> None:
    target = KIT / "models" / "modnet.onnx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(fetch(MODNET))
    save_licence("modnet", fetch(MODNET_LICENSE))
    print(f"matte: {target.stat().st_size // 1_000_000} MB")


def collect_made() -> None:
    """Entries for the images scripts/generate_kit_images.py made (its own records)."""
    records = KIT / "made" / "records.json"
    entries = json.loads(records.read_text(encoding="utf-8")) if records.is_file() else []
    save_source("made", [e for e in entries if (KIT / e["path"]).is_file()])


BUILDERS = {
    "fluent": build_fluent, "lucide": build_lucide, "logos": build_logos, "maps": build_maps,
    "textures": build_textures, "matte": build_matte, "made": collect_made,
}


# --- manifest and sync -------------------------------------------------------------------------------


def write_manifest() -> None:
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(SOURCES.glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item["id"] in seen or not (KIT / item["path"]).is_file():
                continue
            seen.add(item["id"])
            assets.append(item)
    counts: dict[str, int] = {}
    for item in assets:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    (KIT / "manifest.json").write_text(json.dumps({"built": TODAY, "counts": counts, "assets": assets}, ensure_ascii=False),
                                       encoding="utf-8")
    print("manifest:", counts)


TARBALLS = {
    "fluent": ["icons/3d/fluent"], "lucide": ["icons/line/lucide"], "logos": ["logos"], "maps": ["maps"],
    "textures": ["backgrounds/texture"], "matte": ["models"], "made": ["icons/3d/made", "stills", "made"],
    "index": ["manifest.json", "sources", "LICENSES"],
}


def push() -> None:
    from clients.services.s3 import S3
    from core.config import get_settings

    bucket, s3 = get_settings().S3_BUCKET_NAME, S3()
    with tempfile.TemporaryDirectory() as tmp:
        for name, parts in TARBALLS.items():
            present = [p for p in parts if (KIT / p).exists()]
            if not present:
                continue
            archive = Path(tmp) / f"{name}.tar"
            # Follows links: a worktree's kit folders are links to the checkout that built the kit.
            with tarfile.open(archive, "w", dereference=True) as tar:
                for part in present:
                    tar.add(KIT / part, arcname=part)
            s3.upload_file(bucket, f"{S3_PREFIX}/{name}.tar", str(archive))
            print(f"pushed {name} ({archive.stat().st_size // 1_000_000} MB)")


def pull() -> None:
    from clients.services.s3 import S3
    from core.config import get_settings

    bucket, s3 = get_settings().S3_BUCKET_NAME, S3()
    KIT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in TARBALLS:
            archive = Path(tmp) / f"{name}.tar"
            try:
                s3.download_file(bucket, f"{S3_PREFIX}/{name}.tar", str(archive))
            except Exception as exc:
                print(f"skip {name}: {exc}")
                continue
            with tarfile.open(archive) as tar:
                tar.extractall(KIT, filter="data")
            print(f"pulled {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=sorted(BUILDERS))
    parser.add_argument("--manifest", action="store_true", help="rebuild the manifest from sources/ only")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--pull", action="store_true")
    args = parser.parse_args()
    if args.pull:
        pull()
        return
    if args.push:
        push()
        return
    if not args.manifest:
        for name in args.only or BUILDERS:
            try:
                BUILDERS[name]()
            except Exception as exc:
                print(f"{name} failed: {exc}", file=sys.stderr)
    write_manifest()


if __name__ == "__main__":
    main()
