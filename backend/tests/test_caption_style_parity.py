from __future__ import annotations

import re
from pathlib import Path

import pytest

from subtitle_styling.ass_generator import FONTS_DIR, ass_filter
from subtitle_styling.export_styles import OUTPUT_PATH, render
from subtitle_styling.model import LEGACY_STYLE_ALIASES, SubtitleStyleType
from subtitle_styling.templates import (
    CAPTION_TEMPLATES,
    TEMPLATE_DEFAULTS,
    get_template,
    get_template_info,
    get_template_names,
)


class TestTemplates:
    def test_expected_style_count(self) -> None:
        assert len(CAPTION_TEMPLATES) == 27

    def test_every_template_is_fully_populated(self) -> None:
        for name in get_template_names():
            template = get_template(name)
            for key in TEMPLATE_DEFAULTS:
                assert key in template, f"{name} missing {key}"
            assert template["name"] and template["description"]

    def test_unknown_style_falls_back_to_default(self) -> None:
        assert get_template("does_not_exist") == get_template("default")

    def test_info_covers_every_template(self) -> None:
        assert {item["id"] for item in get_template_info()} == set(CAPTION_TEMPLATES)

    def test_position_and_size_are_sane(self) -> None:
        for name in get_template_names():
            template = get_template(name)
            assert 0.5 <= template["position_y"] <= 0.95, name
            assert 12 <= template["font_size"] <= 64, name
            assert 1 <= template["max_words_per_line"] <= 10, name

    def test_colors_are_hex(self) -> None:
        hex_re = re.compile(r"^#[0-9A-Fa-f]{6,8}$")
        for name in get_template_names():
            template = get_template(name)
            for key in ("font_color", "highlight_color"):
                assert hex_re.match(template[key]), f"{name}.{key}={template[key]}"


class TestStyleResolution:
    def test_every_template_id_resolves_to_itself(self) -> None:
        for name in get_template_names():
            assert SubtitleStyleType.to_template(name) == name
            assert SubtitleStyleType.is_template(name)

    def test_legacy_aliases_resolve_to_real_templates(self) -> None:
        for alias, target in LEGACY_STYLE_ALIASES.items():
            assert target in CAPTION_TEMPLATES
            assert SubtitleStyleType.to_template(alias) == target

    def test_unknown_resolves_to_default(self) -> None:
        assert SubtitleStyleType.to_template("nonsense") == "default"


class TestFrontendParity:
    def test_generated_file_is_current(self) -> None:
        """Regression: the two lists drifted until six UI styles had no backend
        template and silently burned as Default."""
        if not OUTPUT_PATH.exists():
            pytest.skip("frontend mirror not present")
        assert OUTPUT_PATH.read_text(encoding="utf-8") == render(), (
            "captionStyles.generated.ts is stale — "
            "run: cd backend && python -m subtitle_styling.export_styles"
        )

    def test_frontend_declares_every_backend_style(self) -> None:
        if not OUTPUT_PATH.exists():
            pytest.skip("frontend mirror not present")
        content = OUTPUT_PATH.read_text(encoding="utf-8")
        for name in get_template_names():
            assert f'"{name}"' in content, f"{name} missing from frontend mirror"


class TestBundledFonts:
    def test_burn_filter_loads_bundled_fonts(self) -> None:
        assert ass_filter("/tmp/work/captions.ass") == f"ass=captions.ass:fontsdir={FONTS_DIR}"

    def test_bundled_faces_have_font_files(self) -> None:
        """A face missing from static/fonts silently burns in the fallback font."""
        bundled = {
            "Anton": "Anton-Regular.ttf",
            "Archivo Black": "ArchivoBlack-Regular.ttf",
            "Bangers": "Bangers-Regular.ttf",
            "Bebas Neue": "BebasNeue-Regular.ttf",
            "DM Serif Display": "DMSerifDisplay-Regular.ttf",
            "Luckiest Guy": "LuckiestGuy-Regular.ttf",
            "Permanent Marker": "PermanentMarker-Regular.ttf",
        }
        for name in get_template_names():
            family = get_template(name)["font_family"]
            if family in bundled:
                assert (FONTS_DIR / bundled[family]).is_file(), f"{name}: {family}"
