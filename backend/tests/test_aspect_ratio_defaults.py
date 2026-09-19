"""Aspect ratios are chosen by content category unless the caller says otherwise.

Rendering every supported shape for every clip quadrupled encode time to produce
files nothing read, so the fallback now follows the category. A caller-supplied
list, and a deployment-wide config pin, both still outrank it.
"""

import pytest

from content_intelligence.service import (
    CATEGORY_ASPECT_RATIOS,
    FALLBACK_ASPECT_RATIOS,
    ContentIntelligenceService,
)
from core.config import get_settings
from video_processor.geometry import SUPPORTED_ASPECT_RATIOS


@pytest.fixture(autouse=True)
def _clear_config_pin():
    """Most tests want the category to decide, which needs the pin unset."""
    settings = get_settings()
    original = settings.DEFAULT_OUTPUT_ASPECT_RATIOS
    settings.DEFAULT_OUTPUT_ASPECT_RATIOS = ""
    yield settings
    settings.DEFAULT_OUTPUT_ASPECT_RATIOS = original


class TestCategoryDefaults:
    def test_gaming_is_vertical_only(self):
        assert ContentIntelligenceService.default_aspect_ratios("gaming") == ["9:16"]

    def test_podcast_adds_square(self):
        assert ContentIntelligenceService.default_aspect_ratios("podcast_interview") == [
            "9:16",
            "1:1",
        ]

    def test_tutorial_adds_landscape(self):
        assert ContentIntelligenceService.default_aspect_ratios("tutorial_educational") == [
            "9:16",
            "16:9",
        ]

    def test_food_adds_tall_feed_ratio(self):
        assert ContentIntelligenceService.default_aspect_ratios("food") == ["9:16", "4:5"]

    @pytest.mark.parametrize("category", ["unknown", "", None, "not_a_category"])
    def test_unrecognised_category_falls_back(self, category):
        assert ContentIntelligenceService.default_aspect_ratios(category) == list(
            FALLBACK_ASPECT_RATIOS
        )

    def test_category_matching_ignores_case_and_padding(self):
        assert ContentIntelligenceService.default_aspect_ratios("  GAMING ") == ["9:16"]

    def test_every_category_yields_supported_ratios(self):
        """A typo in the map would otherwise be dropped silently at render time."""
        for category, ratios in CATEGORY_ASPECT_RATIOS.items():
            assert ratios, f"{category} maps to no ratios"
            for ratio in ratios:
                assert ratio in SUPPORTED_ASPECT_RATIOS, f"{category} -> {ratio}"

    def test_every_category_includes_vertical(self):
        """9:16 is the one shape the product always publishes."""
        for category, ratios in CATEGORY_ASPECT_RATIOS.items():
            assert "9:16" in ratios, f"{category} omits 9:16"

    def test_no_category_renders_all_four(self):
        """The regression this change exists to prevent."""
        for category in CATEGORY_ASPECT_RATIOS:
            ratios = ContentIntelligenceService.default_aspect_ratios(category)
            assert len(ratios) < len(SUPPORTED_ASPECT_RATIOS), category


class TestConfigPin:
    def test_configured_value_outranks_category(self, _clear_config_pin):
        _clear_config_pin.DEFAULT_OUTPUT_ASPECT_RATIOS = "1:1,16:9"
        assert ContentIntelligenceService.default_aspect_ratios("gaming") == ["1:1", "16:9"]

    def test_blank_config_defers_to_category(self, _clear_config_pin):
        _clear_config_pin.DEFAULT_OUTPUT_ASPECT_RATIOS = "   "
        assert ContentIntelligenceService.default_aspect_ratios("gaming") == ["9:16"]

    def test_config_whitespace_is_trimmed(self, _clear_config_pin):
        _clear_config_pin.DEFAULT_OUTPUT_ASPECT_RATIOS = " 9:16 , 1:1 "
        assert ContentIntelligenceService.default_aspect_ratios("food") == ["9:16", "1:1"]
