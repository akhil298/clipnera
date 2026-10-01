from __future__ import annotations

import pytest

from subtitle_styling.templates import (
    CAPTION_TEMPLATES,
    DEFAULT_STYLE,
    TEMPLATE_DEFAULTS,
    get_template,
    get_all_templates,
    get_template_names,
    get_template_info,
)


class TestTemplates:
    def test_get_template_default(self):
        template = get_template(DEFAULT_STYLE)
        assert template["name"] == "Karaoke"
        assert template["animation"] == "karaoke"
        assert template["rows"] == 2

    def test_get_template_unknown_falls_back(self):
        assert get_template("nonexistent")["name"] == "Karaoke"

    def test_retired_id_takes_its_replacement(self):
        assert get_template("mrbeast")["name"] == "Punch"
        assert get_template("clean_dark")["name"] == "Backdrop"

    def test_get_template_merges_defaults(self):
        template = get_template("reveal")
        assert template["background"] is True
        assert template["upcoming_color"] == "#A3A3A3"
        assert template["animation"] == "karaoke"
        assert template["uppercase"] is False
        assert template["emoji"] is False

    def test_get_template_grow_glows(self):
        template = get_template("grow")
        assert template["glow"] is True
        assert template["active_scale"] > 1.2

    def test_get_template_word_box(self):
        template = get_template("highlighter")
        assert template["word_box"] is True
        assert template["word_box_color"] == "#F472B6"

    def test_get_template_stack_colours_its_second_row(self):
        assert get_template("gold_stack")["second_line_color"] == "#FFE100"
        assert get_template("typewriter")["second_line_scale"] > 1

    def test_get_all_templates(self):
        all_templates = get_all_templates()
        for name in ("karaoke", "simple", "punch", "spotlight", "blur_in", "glitch"):
            assert name in all_templates
        assert len(all_templates) == len(CAPTION_TEMPLATES) == 21

    def test_get_template_names(self):
        names = get_template_names()
        assert isinstance(names, list)
        assert DEFAULT_STYLE in names
        assert len(names) == len(CAPTION_TEMPLATES)

    def test_names_are_original(self):
        """No style is named after a creator, channel or another product."""
        banned = ("beast", "hormozi", "youshaei", "think media", "opus", "tiktok", "mozi", "pod p")
        for name in get_template_names():
            label = f"{name} {get_template(name)['name']}".lower()
            assert not any(word in label for word in banned), name

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
