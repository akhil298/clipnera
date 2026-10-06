"""Build a local, LLM-readable catalog of editing assets and video previews.

All motion assets live under ``backend/static/motion``. The catalog records
source files, runtime assets, technical media properties, inferred
categories/tags, and sampled video time slices. Descriptions are intentionally
marked as filename-inferred: this local indexer does not claim to understand
visual content.

Run from the repository root with:

    backend/venv/bin/python backend/scripts/index_motion_library.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
STATIC = BACKEND / "static"
ASSET_ROOT = STATIC / "motion"
LIBRARY = ASSET_ROOT / "library"
CATALOG = ASSET_ROOT / "catalog.json"
PREVIEWS = ASSET_ROOT / "previews"
EXTRACTED = ASSET_ROOT / "extracted"
ORGANIZATION_MANIFEST = LIBRARY / "organization.json"

VIDEO_EXTENSIONS = {
    ".avi", ".gif", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm", ".wmv",
}
AUDIO_EXTENSIONS = {".aac", ".aif", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"}
IMAGE_EXTENSIONS = {".avif", ".bmp", ".jpeg", ".jpg", ".png", ".webp"}
VECTOR_EXTENSIONS = {".svg"}
ARCHIVE_EXTENSIONS = {".7z", ".rar", ".tar", ".zip"}
FONT_EXTENSIONS = {
    ".afm", ".compositefont", ".eot", ".fon", ".otf", ".pfb", ".pfm", ".ttc", ".ttf", ".woff", ".woff2",
}
EDITABLE_EXTENSIONS = {".aep", ".ai", ".eps", ".mogrt", ".psd", ".prproj"}
LUT_EXTENSIONS = {".cube", ".3dl", ".look"}
DOCUMENT_EXTENSIONS = {".pdf", ".rtf", ".txt"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
TOKEN = re.compile(r"[a-z0-9]+")
PATH_TAG_IGNORES = {
    "static", "motion", "library", "previews", "branding", "fonts", "font", "sfx", "hook_graphics",
}
DESCRIPTION_POLICY = (
    "Local metadata only. Names and tags are inferred from paths; video time slices are uniform samples, "
    "not semantic scene descriptions. Preview sheets let a downstream vision model inspect representative frames. "
    "ZIP members are cataloged but require extraction before use."
)


def _fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return round(float(numerator) / float(denominator), 4) if float(denominator) else None
    except (ValueError, ZeroDivisionError):
        return None


def _asset_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VECTOR_EXTENSIONS:
        return "vector"
    if suffix in FONT_EXTENSIONS:
        return "font"
    if suffix in ARCHIVE_EXTENSIONS:
        return "archive"
    if suffix in EDITABLE_EXTENSIONS:
        return "editing_project"
    if suffix in LUT_EXTENSIONS:
        return "lut"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    if suffix in {".html", ".json", ".lottie"}:
        return "motion_document"
    if suffix in {".dat", ".ini", ".setting", ".url"}:
        return "reference"
    return "other"


def _category(path: Path, asset_type: str) -> str:
    words = " ".join(part.lower().replace("-", " ").replace("_", " ") for part in path.parts)
    if "ambience" in words or "ambient" in words:
        return "ambience"
    if "music" in words or "song" in words or "soundtrack" in words:
        return "music"
    if "sfx" in words or "sound effect" in words or asset_type == "audio":
        return "sound_effect"
    if "transition" in words or "transitions" in words:
        return "transition"
    if "text preset" in words or "lower third" in words or "kinetic text" in words:
        return "text_graphic"
    if "overlay" in words or "green screen" in words or "greenscreen" in words:
        return "overlay"
    if "background" in words or "backdrop" in words:
        return "background"
    if "texture" in words or "film burn" in words or "film grain" in words:
        return "texture"
    if "lut" in words or asset_type == "lut":
        return "lut"
    if "3d asset" in words or "3d assets" in words:
        return "3d_asset"
    if "b roll" in words or "broll" in words:
        return "b_roll"
    if "watermark" in words or "branding" in words or "intro" in words or "outro" in words:
        return "branding"
    if "hook graphics" in words or "motion graphic" in words or "motion graphics" in words:
        return "motion_graphic"
    if asset_type == "font":
        return "font"
    if asset_type == "editing_project":
        return "editing_template"
    if asset_type == "archive":
        return "archive"
    if asset_type in {"image", "video", "vector"}:
        return "visual_asset"
    if asset_type == "other":
        return "other"
    return "reference"


def _tags(path: Path) -> list[str]:
    tags: list[str] = []
    for part in (*path.parts[:-1], path.stem):
        lowered = part.lower()
        if lowered in PATH_TAG_IGNORES or lowered.startswith("drive-download"):
            continue
        for token in TOKEN.findall(lowered):
            if token.isdigit() or token.startswith("2026"):
                continue
            if token not in tags:
                tags.append(token)
    return tags


def _probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries",
            "format=duration,format_name,bit_rate:"
            "stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,"
            "r_frame_rate,channels,sample_rate,bit_rate,duration",
            "-of", "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    format_data = data.get("format") or {}
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    duration = format_data.get("duration") or video.get("duration")
    if not duration and video and path.suffix.lower() not in IMAGE_EXTENSIONS:
        counted = subprocess.run(
            [
                ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate,r_frame_rate,nb_read_frames,duration_ts,time_base",
                "-of", "json", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        counted_streams = json.loads(counted.stdout).get("streams") or []
        if counted_streams:
            counted_video = counted_streams[0]
            frame_count = _int_or_none(counted_video.get("nb_read_frames"))
            frame_rate = _fraction(counted_video.get("avg_frame_rate") or counted_video.get("r_frame_rate"))
            time_base = _fraction(counted_video.get("time_base"))
            duration_ticks = _int_or_none(counted_video.get("duration_ts"))
            if duration_ticks is not None and time_base:
                duration = duration_ticks * time_base
            elif frame_count is not None and frame_rate:
                duration = frame_count / frame_rate
    output: dict[str, Any] = {
        "format": format_data.get("format_name"),
        "duration_seconds": round(float(duration), 3) if duration else None,
        "bitrate": _int_or_none(format_data.get("bit_rate")),
        "video": None,
        "audio": [],
    }
    if video and path.suffix.lower() in IMAGE_EXTENSIONS:
        output["image"] = {
            "codec": video.get("codec_name"),
            "width": _int_or_none(video.get("width")),
            "height": _int_or_none(video.get("height")),
            "pixel_format": video.get("pix_fmt"),
            "has_alpha": "a" in str(video.get("pix_fmt") or ""),
        }
    elif video:
        pixel_format = str(video.get("pix_fmt") or "")
        output["video"] = {
            "codec": video.get("codec_name"),
            "width": _int_or_none(video.get("width")),
            "height": _int_or_none(video.get("height")),
            "fps": _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
            "pixel_format": pixel_format or None,
            "has_alpha": "a" in pixel_format,
        }
    for stream in audio_streams:
        output["audio"].append({
            "codec": stream.get("codec_name"),
            "channels": _int_or_none(stream.get("channels")),
            "sample_rate": _int_or_none(stream.get("sample_rate")),
            "bitrate": _int_or_none(stream.get("bit_rate")),
        })
    return output


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None


def _time_slices(duration: float, count: int) -> list[dict[str, float | int]]:
    slice_count = min(count, max(1, math.ceil(duration / 8)))
    interval = duration / slice_count
    return [
        {
            "index": index,
            "from_seconds": round(index * interval, 3),
            "to_seconds": round((index + 1) * interval, 3),
            "sample_seconds": round((index + 0.5) * interval, 3),
        }
        for index in range(slice_count)
    ]


def _preview_sheet(
    path: Path,
    preview_path: Path,
    slices: list[dict[str, float | int]],
    ffmpeg: str,
) -> None:
    """Extract a small contact sheet using seeks, without copying source video."""
    inputs: list[str] = []
    filters: list[str] = []
    for index, item in enumerate(slices):
        inputs.extend(["-ss", f"{item['sample_seconds']:.3f}", "-i", str(path)])
        filters.append(
            f"[{index}:v:0]scale=320:180:force_original_aspect_ratio=decrease,"
            f"pad=320:180:(ow-iw)/2:(oh-ih)/2:black,setsar=1,setpts=PTS-STARTPTS[v{index}]"
        )
    if len(slices) == 1:
        filters.append("[v0]format=yuvj420p[sheet]")
    else:
        columns = min(4, len(slices))
        layout = "|".join(f"{index % columns * 320}_{index // columns * 180}" for index in range(len(slices)))
        labels = "".join(f"[v{index}]" for index in range(len(slices)))
        filters.append(f"{labels}xstack=inputs={len(slices)}:layout={layout},format=yuvj420p[sheet]")
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            *inputs, "-filter_complex", ";".join(filters), "-map", "[sheet]",
            "-frames:v", "1", "-q:v", "3", str(preview_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _asset_record(path: Path, root: Path, ffprobe: str, ffmpeg: str | None, make_previews: bool) -> dict[str, Any]:
    relative = path.relative_to(BACKEND).as_posix()
    asset_type = _asset_type(path)
    category = _category(Path(relative), asset_type)
    name = path.stem.replace("_", " ").replace("-", " ").strip()
    tags = _tags(Path(relative))
    record: dict[str, Any] = {
        "id": hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20],
        "name": name,
        "path": relative,
        "source_path": _source_path(relative),
        "source_root": root.relative_to(BACKEND).as_posix(),
        "file_type": asset_type,
        "extension": path.suffix.lower().lstrip("."),
        "mime_type": mimetypes.guess_type(path.name)[0],
        "size_bytes": path.stat().st_size,
        "category": category,
        "tags": tags,
        "description": f"{name} — {category.replace('_', ' ')} {asset_type.replace('_', ' ')} asset.",
        "description_status": "filename_inferred",
        "semantic_caption_status": "not_generated_local_only",
        "license_status": "review_source_license_before_publication",
    }
    manifest_metadata = _manifest_metadata(path)
    if manifest_metadata:
        record["manifest_metadata"] = manifest_metadata
        if manifest_metadata.get("tags"):
            record["tags"] = list(dict.fromkeys([*record["tags"], *manifest_metadata["tags"]]))
        if manifest_metadata.get("category"):
            record["category"] = str(manifest_metadata["category"])
    if asset_type in {"video", "audio", "image"}:
        try:
            probe = _probe(path, ffprobe)
            record["media"] = probe
            if asset_type == "video" and probe["duration_seconds"] and ffmpeg and make_previews:
                slices = _time_slices(probe["duration_seconds"], 12)
                preview_id = record["id"]
                preview = PREVIEWS / f"{preview_id}.jpg"
                try:
                    _preview_sheet(path, preview, slices, ffmpeg)
                    record["time_slices"] = slices
                    record["preview_sheet"] = preview.relative_to(BACKEND).as_posix()
                    record["time_slice_method"] = "uniform_samples_not_semantic_scene_detection"
                except (OSError, subprocess.CalledProcessError) as error:
                    record["preview_error"] = _error_text(error)
        except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as error:
            record["index_error"] = _error_text(error)
    if manifest_metadata.get("licence") or manifest_metadata.get("license"):
        record["license"] = manifest_metadata.get("licence") or manifest_metadata.get("license")
    slices_context = "; ".join(
        f"{item['from_seconds']}-{item['to_seconds']}s (sample {item['sample_seconds']}s)"
        for item in record.get("time_slices", [])
    )
    record["llm_context"] = " ".join([
        f"Name: {name}.",
        f"Category: {category.replace('_', ' ')}.",
        f"Tags: {', '.join(record['tags'])}.",
        f"File: {relative}.",
        _media_context(record.get("media")),
        f"Declared metadata: {json.dumps(manifest_metadata, ensure_ascii=False)}." if manifest_metadata else "",
        f"Sampled time ranges: {slices_context}." if slices_context else "",
        f"Preview: {record.get('preview_sheet', 'unavailable')}.",
        "Visual description is not machine-generated; inspect the preview sheet before selecting.",
    ]).strip()
    return record


def _media_context(media: dict[str, Any] | None) -> str:
    if not media:
        return ""
    facts: list[str] = []
    if media.get("duration_seconds") is not None:
        facts.append(f"Duration: {media['duration_seconds']} seconds.")
    video = media.get("video")
    if video:
        facts.append(
            f"Video: {video.get('width')}x{video.get('height')} at {video.get('fps')} fps; "
            f"codec {video.get('codec')}; alpha {video.get('has_alpha')}."
        )
    image = media.get("image")
    if image:
        facts.append(
            f"Image: {image.get('width')}x{image.get('height')}; codec {image.get('codec')}; "
            f"alpha {image.get('has_alpha')}."
        )
    audio = media.get("audio") or []
    if audio:
        facts.append(f"Audio tracks: {len(audio)}.")
    return " ".join(facts)


def _error_text(error: BaseException) -> str:
    detail = getattr(error, "stderr", None)
    return detail.strip() if isinstance(detail, str) and detail.strip() else str(error)


def _manifest_metadata(path: Path) -> dict[str, Any]:
    manifest = path.parent / "manifest.json"
    if not manifest.is_file():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entries = data.get("graphics") if isinstance(data, dict) else None
    if isinstance(entries, list):
        entry = next((item for item in entries if item.get("file") == path.name), None)
        if entry:
            return {
                key: entry[key]
                for key in ("name", "moods", "sfx")
                if key in entry
            } | {"duration_seconds": data.get("duration")}
    if isinstance(data, dict):
        entry = next(
            (
                item for item in data.values()
                if isinstance(item, dict) and item.get("file") == path.name
            ),
            None,
        )
        if entry:
            return entry
    return {}


@lru_cache(maxsize=1)
def _organization_map() -> dict[str, str]:
    if not ORGANIZATION_MANIFEST.is_file():
        return {}
    data = json.loads(ORGANIZATION_MANIFEST.read_text(encoding="utf-8"))
    return data.get("assets", {})


def _source_path(relative: str) -> str:
    return _organization_map().get(relative, relative)


def _asset_paths(roots: list[Path]) -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.name not in IGNORED_NAMES
                and path != CATALOG
                and PREVIEWS not in path.parents
                and EXTRACTED not in path.parents
                and path != ORGANIZATION_MANIFEST
            ):
                found.append((path, root))
    return sorted(found, key=lambda item: item[0].relative_to(BACKEND).as_posix().casefold())


def _reuse_previews(records: list[dict[str, Any]], catalog_path: Path) -> None:
    if not catalog_path.is_file():
        return
    previous = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_path: dict[str, dict[str, Any]] = {}
    for asset in previous.get("assets", []):
        if asset.get("preview_sheet"):
            by_path[asset.get("source_path", asset.get("path", ""))] = asset
            by_path[asset.get("path", "")] = asset
    for asset in records:
        if asset.get("file_type") != "video" or asset.get("preview_sheet"):
            continue
        prior = by_path.get(asset.get("source_path", "")) or by_path.get(asset.get("path", ""))
        if not prior:
            continue
        preview = prior["preview_sheet"]
        if not (BACKEND / preview).is_file():
            continue
        for key in ("preview_sheet", "time_slices", "time_slice_method"):
            if key in prior:
                asset[key] = prior[key]


def _archive_records(
    archive_paths: list[Path],
    ffprobe: str | None = None,
    ffmpeg: str | None = None,
    make_previews: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for archive in archive_paths:
        try:
            with zipfile.ZipFile(archive) as zipped:
                for member in zipped.infolist():
                    if member.is_dir() or Path(member.filename).name in IGNORED_NAMES:
                        continue
                    relative = archive.relative_to(BACKEND).as_posix()
                    member_path = Path(member.filename)
                    asset_type = _asset_type(member_path)
                    combined_path = Path(relative).parent / member_path
                    category = _category(combined_path, asset_type)
                    name = member_path.stem.replace("_", " ").replace("-", " ").strip()
                    tags = _tags(combined_path)
                    record: dict[str, Any] = {
                        "id": hashlib.sha256(f"{relative}!{member.filename}".encode("utf-8")).hexdigest()[:20],
                        "name": name,
                        "path": f"{relative}!/{member.filename}",
                        "source_path": f"{_source_path(relative)}!/{member.filename}",
                        "archive_path": relative,
                        "member_path": member.filename,
                        "file_type": asset_type,
                        "extension": member_path.suffix.lower().lstrip("."),
                        "mime_type": mimetypes.guess_type(member_path.name)[0],
                        "size_bytes": member.file_size,
                        "compressed_size_bytes": member.compress_size,
                        "category": category,
                        "tags": tags,
                        "description": f"{name} — {category.replace('_', ' ')} {asset_type.replace('_', ' ')} asset in an archive.",
                        "description_status": "filename_inferred",
                        "semantic_caption_status": "not_generated_local_only",
                        "license_status": "review_source_license_before_publication",
                        "retrieval_status": "extract_archive_member_before_use",
                    }
                    if ffprobe and asset_type in {"video", "audio", "image"}:
                        try:
                            with tempfile.TemporaryDirectory(prefix="motion-index-") as temporary:
                                local_path = Path(temporary) / member_path.name
                                with zipped.open(member) as source, local_path.open("wb") as destination:
                                    shutil.copyfileobj(source, destination)
                                record["media"] = _probe(local_path, ffprobe)
                                duration = record["media"].get("duration_seconds")
                                if (
                                    asset_type == "video"
                                    and duration
                                    and ffmpeg
                                    and make_previews
                                ):
                                    slices = _time_slices(float(duration), 12)
                                    preview = PREVIEWS / f"{record['id']}.jpg"
                                    _preview_sheet(local_path, preview, slices, ffmpeg)
                                    record["time_slices"] = slices
                                    record["preview_sheet"] = preview.relative_to(BACKEND).as_posix()
                                    record["time_slice_method"] = "uniform_samples_not_semantic_scene_detection"
                        except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as error:
                            record["index_error"] = _error_text(error)
                    slices_context = "; ".join(
                        f"{item['from_seconds']}-{item['to_seconds']}s (sample {item['sample_seconds']}s)"
                        for item in record.get("time_slices", [])
                    )
                    record["llm_context"] = " ".join([
                        f"Name: {name}.",
                        f"Category: {category.replace('_', ' ')}.",
                        f"Tags: {', '.join(tags)}.",
                        f"Archive member: {relative}!/{member.filename}.",
                        f"Size: {member.file_size} bytes.",
                        _media_context(record.get("media")),
                        f"Sampled time ranges: {slices_context}." if slices_context else "",
                        f"Preview: {record.get('preview_sheet', 'unavailable')}.",
                        "Visual description is not machine-generated; inspect the preview sheet before selecting.",
                    ]).strip()
                    records.append(record)
        except (OSError, zipfile.BadZipFile) as error:
            records.append({
                "id": hashlib.sha256(archive.relative_to(BACKEND).as_posix().encode("utf-8")).hexdigest()[:20],
                "path": archive.relative_to(BACKEND).as_posix(),
                "file_type": "archive",
                "archive_index_error": str(error),
            })
    return records


def build_catalog(
    roots: list[Path],
    output: Path,
    ffprobe: str,
    ffmpeg: str | None,
    make_previews: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    assets = _asset_paths(roots)
    if limit is not None:
        assets = assets[:limit]
    records = [
        _asset_record(path, root, ffprobe, ffmpeg, make_previews)
        for path, root in assets
    ]
    archive_paths = [path for path, _ in assets if path.suffix.lower() == ".zip"]
    archive_records = _archive_records(archive_paths, ffprobe, ffmpeg, make_previews)
    records.extend(archive_records)
    if not make_previews:
        _reuse_previews(records, output)
    archive_member_count = sum("archive_path" in record for record in archive_records)
    catalog = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage_root": "backend/static/motion",
        "description_policy": DESCRIPTION_POLICY,
        "asset_count": len(records),
        "archive_member_count": archive_member_count,
        "index_error_count": sum(
            "index_error" in record or "preview_error" in record or "archive_index_error" in record
            for record in records
        ),
        "assets": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return catalog


def refresh_previews(output: Path, ffprobe: str, ffmpeg: str, count: int = 12) -> tuple[int, int]:
    data = json.loads(output.read_text(encoding="utf-8"))
    succeeded = failed = 0
    for asset in data["assets"]:
        if (
            asset.get("file_type") != "video"
            or asset.get("preview_sheet")
            or asset.get("archive_path")
        ):
            continue
        media = asset.get("media") or {}
        duration = media.get("duration_seconds")
        path = BACKEND / asset["path"]
        if not path.is_file():
            asset["preview_error"] = "video source unavailable"
            failed += 1
            continue
        if not duration:
            media = _probe(path, ffprobe)
            asset["media"] = media
            duration = media.get("duration_seconds")
        if not duration:
            asset["preview_error"] = "video duration unavailable after probing"
            failed += 1
            continue
        slices = _time_slices(float(duration), count)
        preview = PREVIEWS / f"{asset['id']}.jpg"
        try:
            _preview_sheet(path, preview, slices, ffmpeg)
            asset["time_slices"] = slices
            asset["preview_sheet"] = preview.relative_to(BACKEND).as_posix()
            asset["time_slice_method"] = "uniform_samples_not_semantic_scene_detection"
            asset.pop("preview_error", None)
            succeeded += 1
        except (OSError, subprocess.CalledProcessError) as error:
            asset["preview_error"] = _error_text(error)
            failed += 1
    data["index_error_count"] = sum(
        "index_error" in asset or "preview_error" in asset or "archive_index_error" in asset
        for asset in data["assets"]
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return succeeded, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="index only the first N assets (for a smoke test)")
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help="skip extraction and reuse existing contact sheets when their source paths match",
    )
    parser.add_argument("--output", type=Path, default=CATALOG)
    parser.add_argument(
        "--archives-only",
        action="store_true",
        help="add archive-member records to an existing catalog without probing all media again",
    )
    parser.add_argument(
        "--previews-only",
        action="store_true",
        help="create missing video contact sheets from an existing catalog",
    )
    args = parser.parse_args(argv)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        parser.error("ffprobe is required to read media metadata")
    ffmpeg = shutil.which("ffmpeg")
    if not args.no_previews and not ffmpeg:
        parser.error("ffmpeg is required to create video preview sheets")
    if args.previews_only:
        if not ffprobe:
            parser.error("ffprobe is required to read media metadata")
        if not ffmpeg:
            parser.error("ffmpeg is required to create video preview sheets")
        succeeded, failed = refresh_previews(args.output, ffprobe, ffmpeg)
        print(f"Generated {succeeded} video preview sheets; {failed} failures; catalog: {args.output}")
        return 0
    roots = [ASSET_ROOT]
    if args.archives_only:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        physical = _asset_paths(roots)
        archive_paths = [path for path, _ in physical if path.suffix.lower() == ".zip"]
        data["assets"] = [asset for asset in data["assets"] if "archive_path" not in asset]
        data["assets"].extend(_archive_records(archive_paths, ffprobe, ffmpeg, not args.no_previews))
        data["assets"].sort(key=lambda asset: asset.get("path", "").casefold())
        data["asset_count"] = len(data["assets"])
        data["archive_member_count"] = sum("archive_path" in asset for asset in data["assets"])
        data["description_policy"] = DESCRIPTION_POLICY
        data["index_error_count"] = sum(
            "index_error" in asset or "preview_error" in asset or "archive_index_error" in asset
            for asset in data["assets"]
        )
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
        print(f"Indexed {data['archive_member_count']} archive members; catalog: {args.output}")
        return 0
    try:
        catalog = build_catalog(
            roots=roots,
            output=args.output,
            ffprobe=ffprobe,
            ffmpeg=ffmpeg,
            make_previews=not args.no_previews,
            limit=args.limit,
        )
    except OSError as error:
        print(f"Catalog build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Indexed {catalog['asset_count']} assets; "
        f"{catalog['index_error_count']} media/preview errors; catalog: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
