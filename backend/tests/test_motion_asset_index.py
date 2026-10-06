import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from motion import catalog
import scripts.organize_motion_library as organizer
from scripts.index_motion_library import (
    _asset_type,
    _category,
    _fraction,
    _archive_records,
    _preview_sheet,
    _reuse_previews,
    _tags,
    _time_slices,
)


def test_media_type_and_category_are_inferred_from_path():
    video = Path("library/Film Burn Transitions/FilmBurn01.mov")
    audio = Path("library/SFX/trending sfx/Short whoosh.wav")
    vector = Path("library/Overlays/arrow.svg")

    assert _asset_type(video) == "video"
    assert _category(video, "video") == "transition"
    assert _asset_type(audio) == "audio"
    assert _category(audio, "audio") == "sound_effect"
    assert _asset_type(vector) == "vector"
    assert _category(vector, "vector") == "overlay"


def test_fraction_handles_unknown_and_invalid_values():
    assert _fraction("30000/1001") == 29.9700
    assert _fraction("0/0") is None
    assert _fraction("N/A") is None


def test_audio_categories_distinguish_music_from_effects():
    assert _category(Path("SFX/impact.wav"), "audio") == "sound_effect"
    assert _category(Path("Music/ambient-loop.wav"), "audio") == "ambience"
    assert _category(Path("Music/score.mp3"), "audio") == "music"


def test_unified_storage_root_does_not_override_asset_category():
    assert _category(Path("static/motion/fonts/Example.ttf"), "font") == "font"
    assert _category(Path("static/motion/library/motion_graphic/flash.mp4"), "video") == "motion_graphic"
    assert _category(Path("static/motion/hook_graphics/flash.mp4"), "video") == "motion_graphic"


def test_image_media_context_does_not_describe_stills_as_video():
    from scripts.index_motion_library import _media_context

    context = _media_context({
        "duration_seconds": None,
        "image": {"width": 240, "height": 240, "codec": "png", "has_alpha": True},
    })

    assert "Image: 240x240" in context
    assert "Video:" not in context


def test_tags_use_path_and_filename_terms_without_duplicates():
    assert _tags(Path("library/Backgrounds/Neon Neon.mp4")) == [
        "backgrounds", "neon"
    ]


def test_video_time_slices_cover_duration_and_are_bounded():
    slices = _time_slices(19.2, 12)

    assert slices[0]["from_seconds"] == 0.0
    assert slices[-1]["to_seconds"] == 19.2
    assert all(item["from_seconds"] < item["sample_seconds"] < item["to_seconds"] for item in slices)
    assert len(_time_slices(1000, 12)) == 12


def test_video_preview_sheet_is_extracted_from_sampled_time_slices(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required")
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=5:duration=1.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        capture_output=True,
    )
    preview = tmp_path / "preview.jpg"
    _preview_sheet(source, preview, [{"sample_seconds": 0.3}], ffmpeg)
    assert preview.is_file()

    _preview_sheet(
        source,
        preview,
        [
            {"sample_seconds": 0.3},
            {"sample_seconds": 1.0},
        ],
        ffmpeg,
    )

    assert preview.is_file()


def test_archive_members_are_individually_cataloged_without_extraction(tmp_path, monkeypatch):
    import scripts.index_motion_library as indexer

    library = tmp_path / "library"
    library.mkdir()
    archive = library / "Effects.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("Transitions/Light Leak.mov", b"asset bytes")
    monkeypatch.setattr(indexer, "BACKEND", tmp_path)

    records = _archive_records([archive])

    assert len(records) == 1
    assert records[0]["path"] == "library/Effects.zip!/Transitions/Light Leak.mov"
    assert records[0]["category"] == "transition"
    assert records[0]["retrieval_status"] == "extract_archive_member_before_use"


def test_archive_video_members_get_media_facts_and_preview_sheets(tmp_path, monkeypatch):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg and ffprobe are required")
    import scripts.index_motion_library as indexer

    backend = tmp_path / "backend"
    asset_root = backend / "static" / "motion"
    archive = asset_root / "library" / "archive" / "video.zip"
    archive.parent.mkdir(parents=True)
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=5:duration=1.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        capture_output=True,
    )
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(source, "Transitions/sample transition.mp4")
    monkeypatch.setattr(indexer, "BACKEND", backend)
    monkeypatch.setattr(indexer, "PREVIEWS", asset_root / "previews")

    [record] = _archive_records([archive], ffprobe, ffmpeg, make_previews=True)

    assert record["media"]["duration_seconds"] > 0
    assert record["preview_sheet"] == f"static/motion/previews/{record['id']}.jpg"
    assert (backend / record["preview_sheet"]).is_file()


def test_reindex_reuses_existing_video_preview_when_skipping_extraction(tmp_path, monkeypatch):
    import scripts.index_motion_library as indexer

    monkeypatch.setattr(indexer, "BACKEND", tmp_path)
    preview = tmp_path / "static" / "motion" / "previews" / "old.jpg"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"preview")
    old_catalog = tmp_path / "catalog.json"
    old_catalog.write_text(json.dumps({
        "assets": [{
            "path": "static/old/video.mp4",
            "source_path": "library/video.mp4",
            "preview_sheet": "static/motion/previews/old.jpg",
            "time_slices": [{"sample_seconds": 1.0}],
            "time_slice_method": "uniform_samples_not_semantic_scene_detection",
        }]
    }))
    records = [{
        "path": "static/motion/library/visual_asset/video.mp4",
        "source_path": "library/video.mp4",
        "file_type": "video",
    }]

    _reuse_previews(records, old_catalog)

    assert records[0]["preview_sheet"] == "static/motion/previews/old.jpg"
    assert records[0]["time_slices"] == [{"sample_seconds": 1.0}]


def test_organizer_moves_assets_by_category_and_keeps_original_paths(tmp_path, monkeypatch):
    source_root = tmp_path / "backend" / "library"
    destination_root = tmp_path / "backend" / "static" / "motion" / "library"
    sound = source_root / "SFX" / "swoosh.wav"
    video = source_root / "Transitions" / "film_burn.mov"
    sound.parent.mkdir(parents=True)
    video.parent.mkdir(parents=True)
    sound.write_bytes(b"sound")
    video.write_bytes(b"video")
    monkeypatch.setattr(organizer, "SOURCE_ROOT", source_root)
    monkeypatch.setattr(organizer, "DESTINATION_ROOT", destination_root)
    monkeypatch.setattr(organizer, "MANIFEST_PATH", destination_root / "organization.json")
    monkeypatch.setattr(organizer, "ASSET_ROOT", destination_root.parent)
    monkeypatch.setattr(organizer, "BACKEND", tmp_path / "backend")

    result = organizer.organize()

    assert result["files"] == 2
    assert (destination_root / "sound_effect" / "SFX" / "swoosh.wav").read_bytes() == b"sound"
    assert (destination_root / "transition" / "Transitions" / "film_burn.mov").read_bytes() == b"video"
    assert not source_root.exists()
    mapping = json.loads((destination_root / "organization.json").read_text())["assets"]
    assert mapping["static/motion/library/sound_effect/SFX/swoosh.wav"] == "library/SFX/swoosh.wav"
    assert organizer.organize() == {
        "files": 0,
        "already_organized": True,
        "organized_files": 2,
        "manifest": "static/motion/library/organization.json",
    }


def test_search_assets_ranks_matches_and_filters_by_category(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps({
        "assets": [
            {"name": "Film Burn", "path": "library/archive.zip!/film burn.mov", "category": "transition",
             "description": "film burn transition", "tags": ["film", "burn"],
             "retrieval_status": "extract_archive_member_before_use"},
            {"name": "Soft click", "path": "library/sfx/click.wav", "category": "sound_effect",
             "description": "soft interface click", "tags": ["ui", "click"]},
            {"name": "Film burn", "path": "library/transitions/burn.mov", "category": "transition",
             "description": "film burn transition", "tags": ["film", "burn"]},
        ]
    }))
    monkeypatch.setattr(catalog, "CATALOG", catalog_path)

    results = catalog.search_assets("film transition")
    assert results[0]["path"] == "library/transitions/burn.mov"
    assert catalog.search_assets("click", category="sound_effect")[0]["name"] == "Soft click"


def test_resolve_asset_handles_direct_files_and_cached_archive_members(tmp_path, monkeypatch):
    asset_root = tmp_path / "backend" / "static" / "motion"
    direct = asset_root / "library" / "sound_effect" / "click.wav"
    direct.parent.mkdir(parents=True)
    direct.write_bytes(b"direct")
    archive = asset_root / "library" / "archive" / "effects.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("Sound Effects/whoosh.wav", b"archived")
    monkeypatch.setattr(catalog, "BACKEND", tmp_path / "backend")
    monkeypatch.setattr(catalog, "ASSET_ROOT", asset_root)
    monkeypatch.setattr(catalog, "EXTRACTED", asset_root / "extracted")

    assert catalog.resolve_asset({"path": "static/motion/library/sound_effect/click.wav"}) == direct
    member = catalog.resolve_asset({
        "path": "static/motion/library/archive/effects.zip!/Sound Effects/whoosh.wav"
    })
    assert member.read_bytes() == b"archived"
    assert catalog.resolve_asset({
        "path": "static/motion/library/archive/effects.zip!/Sound Effects/whoosh.wav"
    }) == member


@pytest.mark.parametrize(
    "path",
    [
        "static/motion/library/archive/effects.zip!/../../outside.wav",
        "../outside.wav",
    ],
)
def test_resolve_asset_rejects_paths_outside_motion_root(path, tmp_path, monkeypatch):
    asset_root = tmp_path / "backend" / "static" / "motion"
    asset_root.mkdir(parents=True)
    monkeypatch.setattr(catalog, "BACKEND", tmp_path / "backend")
    monkeypatch.setattr(catalog, "ASSET_ROOT", asset_root)

    with pytest.raises(ValueError):
        catalog.resolve_asset({"path": path})


@pytest.mark.parametrize(("query", "limit"), [("", 10), ("whoosh", 0), ("sound", 51)])
def test_search_assets_rejects_invalid_query_and_limit(query, limit):
    with pytest.raises(ValueError):
        catalog.search_assets(query, limit=limit)
