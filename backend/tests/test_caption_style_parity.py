from __future__ import annotations

import re
from pathlib import Path

import pytest

from subtitle_styling.ass_generator import FONTS_DIR, ass_filter
from subtitle_styling.export_styles import OUTPUT_PATH, render
from subtitle_styling.model import SubtitleStyleType
from subtitle_styling.templates import (
    CAPTION_TEMPLATES,
    DEFAULT_STYLE,
    LEGACY_STYLE_ALIASES,
    TEMPLATE_DEFAULTS,
    get_template,
    get_template_info,
    get_template_names,
)


class TestTemplates:
    def test_expected_style_count(self) -> None:
        assert len(CAPTION_TEMPLATES) == 21

    def test_every_template_is_fully_populated(self) -> None:
        for name in get_template_names():
            template = get_template(name)
            for key in TEMPLATE_DEFAULTS:
                assert key in template, f"{name} missing {key}"
            assert template["name"] and template["description"]

    def test_unknown_style_falls_back_to_default(self) -> None:
        assert get_template("does_not_exist") == get_template(DEFAULT_STYLE)

    def test_retired_ids_render_as_their_replacement(self) -> None:
        assert get_template("hormozi") == get_template("lime_stack")

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
        assert SubtitleStyleType.to_template("nonsense") == DEFAULT_STYLE

    def test_no_retired_id_shadows_a_current_one(self) -> None:
        assert not set(LEGACY_STYLE_ALIASES) & set(CAPTION_TEMPLATES)


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
            "Poppins Black": "Poppins-Black.ttf",
            "Courier Prime": "CourierPrime-Bold.ttf",
            "Roboto": "Roboto-Bold.ttf",
        }
        for name in get_template_names():
            family = get_template(name)["font_family"]
            assert family in bundled, f"{name}: {family} is not bundled"
            assert (FONTS_DIR / bundled[family]).is_file(), f"{name}: {family}"

    def test_every_bundled_font_ships_its_license(self) -> None:
        """OFL and Apache fonts may only be redistributed with their license."""
        licenses = list(FONTS_DIR.glob("LICENSE-*.txt"))
        names = {
            "Anton": "anton", "Archivo": "archivo-black", "Bangers": "bangers", "BebasNeue": "bebas-neue",
            "CourierPrime": "courier-prime", "DejaVu": "dejavu", "DMSerifDisplay": "dm-serif-display",
            "LuckiestGuy": "luckiest-guy", "NotoNaskhArabic": "noto-naskh-arabic", "NotoSans": "noto-sans-",
            "PermanentMarker": "permanent-marker", "Poppins": "poppins", "Roboto": "roboto",
        }
        for font in FONTS_DIR.glob("*.ttf"):
            prefix = next((p for p in names if font.name.startswith(p)), None)
            assert prefix, f"{font.name} has no known license"
            assert any(names[prefix] in lic.name for lic in licenses), f"{font.name} ships without its license"
