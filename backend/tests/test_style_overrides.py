from __future__ import annotations

from subtitle_styling.service import _css_color_to_hex, _style_overrides


class TestCssColorToHex:
    def test_hex_forms(self):
        assert _css_color_to_hex("#ffe000") == "#FFE000"
        assert _css_color_to_hex("#fff") == "#FFFFFF"
        assert _css_color_to_hex("#00ff6680") == "#00FF66"

    def test_rgba(self):
        assert _css_color_to_hex("rgba(0,0,0,0.85)") == "#000000"
        assert _css_color_to_hex("rgb(255, 45, 45)") == "#FF2D2D"

    def test_garbage(self):
        assert _css_color_to_hex("red") is None
        assert _css_color_to_hex(None) is None
        assert _css_color_to_hex("#zzzzzz") is None


class TestStyleOverrides:
    def test_editor_config_maps_to_template_keys(self):
        overrides = _style_overrides({
            "font_color": "#ffffff",
            "highlight_color": "#fbbf24",
            "secondary_highlight_color": "#f8fafc",
            "has_bg_box": True,
            "bg_box_color": "rgba(0,0,0,0.85)",
            "uppercase": True,
            "emojis_enabled": False,
            "max_words_per_line": 3,
            "shadow_intensity": 0,
            "font_family": "'Bebas Neue', sans-serif",
        })
        assert overrides["font_color"] == "#FFFFFF"
        assert overrides["highlight_color"] == "#FBBF24"
        assert overrides["emphasis_color"] == "#F8FAFC"
        assert overrides["background"] is True
        assert overrides["background_color"] == "#000000"
        assert overrides["uppercase"] is True
        assert overrides["emoji"] is False
        assert overrides["max_words_per_line"] == 3
        assert overrides["shadow"] is False
        assert overrides["font_family"] == "Bebas Neue"

    def test_missing_or_invalid_values_leave_template_alone(self):
        assert _style_overrides({"font_color": "nope", "font_family": "sans-serif", "uppercase": "yes"}) == {}
        assert _style_overrides(None) == {}
