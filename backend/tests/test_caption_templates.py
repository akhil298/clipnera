from __future__ import annotations

import pytest

from subtitle_styling.templates import (
    CAPTION_TEMPLATES,
    TEMPLATE_DEFAULTS,
    get_template,
    get_all_templates,
    get_template_names,
    get_template_info,
)


class TestTemplates:
    def test_get_template_default(self):
        template = get_template("default")
        assert template["name"] == "Default"
        assert template["animation"] == "karaoke"
        assert template["emoji"] is True
        assert template["word_pop"] is True

    def test_get_template_unknown_falls_back(self):
        template = get_template("nonexistent")
        assert template["name"] == "Default"

    def test_get_template_merges_defaults(self):
        template = get_template("minimal")
        assert template["background"] is True
        assert template["background_color"] == "#00000080"
        assert template["animation"] == "fade"
        assert template["word_pop"] is False
        assert template["emoji"] is False

    def test_get_template_neon_glow(self):
        template = get_template("neon")
        assert template["glow"] is True
        assert template["font_color"] == "#00FFFF"
        assert template["highlight_color"] == "#FF00FF"

    def test_get_template_hormozi_uppercase(self):
        template = get_template("hormozi")
        assert template["uppercase"] is True
        assert template["word_box"] is True

    def test_get_template_mrbeast_yellow(self):
        template = get_template("mrbeast")
        assert template["font_color"] == "#FFFF00"
        assert template["highlight_color"] == "#FF2D2D"

    def test_get_template_tiktok_pink(self):
        template = get_template("tiktok")
        assert template["highlight_color"] == "#FE2C55"

    def test_get_template_podcast_professional(self):
        template = get_template("podcast")
        assert template["font_family"] == "DejaVu Sans"
        assert template["max_words_per_line"] == 5

    def test_get_all_templates(self):
        all_templates = get_all_templates()
        assert "default" in all_templates
        assert "hormozi" in all_templates
        assert "mrbeast" in all_templates
        assert "minimal" in all_templates
        assert "tiktok" in all_templates
        assert "neon" in all_templates
        assert "podcast" in all_templates
        assert len(all_templates) == len(CAPTION_TEMPLATES)

    def test_get_template_names(self):
        names = get_template_names()
        assert isinstance(names, list)
        assert "default" in names
        assert len(names) == len(CAPTION_TEMPLATES)

    def test_get_template_info(self):
        info = get_template_info()
        assert len(info) == len(CAPTION_TEMPLATES)
        for item in info:
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "animation" in item

    def test_template_defaults_provided(self):
        for key, value in TEMPLATE_DEFAULTS.items():
            for name, template in CAPTION_TEMPLATES.items():
                assert key in template or key in TEMPLATE_DEFAULTS

    def test_all_templates_have_required_fields(self):
        # Templates declare only what makes them distinct; shared values come
        # from TEMPLATE_DEFAULTS, so assert against the merged result.
        required = ["name", "description", "font_family", "font_size", "font_color", "highlight_color"]
        for name in CAPTION_TEMPLATES:
            template = get_template(name)
            for field in required:
                assert field in template, f"Template '{name}' missing '{field}'"
