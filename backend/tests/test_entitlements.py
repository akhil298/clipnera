"""Tier capability rules and their enforcement.

These cover the security-relevant half of the tier system: that a free caller
cannot obtain paid capabilities by crafting a request, and that an unknown or
broken plan degrades to Free rather than to Pro.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.exceptions import CustomException
from pipeline.route import _apply_entitlements
from subscription.entitlements import (
    ENTITLEMENTS,
    FREE_CAPTION_STYLES,
    entitlements_for,
)
from subscription.model import PlanSlug


class TestEntitlementsTable:
    def test_free_is_the_most_restricted_tier(self):
        free = entitlements_for(PlanSlug.FREE.value)
        assert free.aspect_ratios == ("9:16",)
        assert free.watermark_forced is True
        assert free.pro_ai_provider is False
        assert free.caption_styles == FREE_CAPTION_STYLES

    @pytest.mark.parametrize("slug", [PlanSlug.PRO.value, PlanSlug.PRO_PLUS.value])
    def test_paid_tiers_unlock_formats_styles_and_provider(self, slug):
        ent = entitlements_for(slug)
        assert set(ent.aspect_ratios) == {"9:16", "1:1", "4:5", "16:9"}
        assert ent.caption_styles is None  # every style
        assert ent.watermark_forced is False
        assert ent.pro_ai_provider is True

    def test_clip_cap_increases_with_tier(self):
        free = entitlements_for(PlanSlug.FREE.value).max_clips_per_video
        pro = entitlements_for(PlanSlug.PRO.value).max_clips_per_video
        pro_plus = entitlements_for(PlanSlug.PRO_PLUS.value).max_clips_per_video
        assert free < pro < pro_plus

    @pytest.mark.parametrize("value", [None, "", "bogus", "enterprise"])
    def test_unknown_plan_degrades_to_free_not_paid(self, value):
        # A broken subscription row must never hand out paid capabilities.
        assert entitlements_for(value) == ENTITLEMENTS[PlanSlug.FREE.value]

    def test_free_styles_are_a_subset_of_the_catalogue(self):
        from subtitle_styling.templates import get_template_names

        assert set(FREE_CAPTION_STYLES).issubset(set(get_template_names()))

    def test_to_dict_is_json_safe(self):
        data = entitlements_for(PlanSlug.FREE.value).to_dict()
        assert isinstance(data["aspect_ratios"], list)
        assert isinstance(data["caption_styles"], list)
        assert entitlements_for(PlanSlug.PRO.value).to_dict()["caption_styles"] is None


class TestPipelineEnforcement:
    """_apply_entitlements is the server-side gate behind the UI controls."""

    def test_free_request_for_paid_ratios_is_clamped(self):
        free = entitlements_for(PlanSlug.FREE.value)
        ratios, _, _ = _apply_entitlements(free, ["9:16", "1:1", "4:5", "16:9"], True, None)
        assert ratios == ["9:16"]

    def test_free_request_for_only_paid_ratios_is_rejected(self):
        free = entitlements_for(PlanSlug.FREE.value)
        with pytest.raises(CustomException) as exc:
            _apply_entitlements(free, ["16:9"], True, None)
        assert exc.value.status_code == 403
        assert exc.value.code == "ASPECT_RATIO_NOT_ENTITLED"

    def test_paid_request_keeps_every_ratio(self):
        pro = entitlements_for(PlanSlug.PRO.value)
        ratios, _, _ = _apply_entitlements(pro, ["9:16", "1:1", "4:5", "16:9"], True, None)
        assert ratios == ["9:16", "1:1", "4:5", "16:9"]

    def test_free_cannot_switch_off_the_watermark(self):
        free = entitlements_for(PlanSlug.FREE.value)
        _, watermark, _ = _apply_entitlements(free, ["9:16"], False, None)
        assert watermark is True

    def test_paid_can_switch_off_the_watermark(self):
        pro = entitlements_for(PlanSlug.PRO.value)
        _, watermark, _ = _apply_entitlements(pro, ["9:16"], False, None)
        assert watermark is False

    def test_clip_count_is_capped_to_the_plan(self):
        free = entitlements_for(PlanSlug.FREE.value)
        _, _, settings = _apply_entitlements(free, ["9:16"], True, {"max_clips": 999})
        assert settings["max_clips"] == free.max_clips_per_video

    def test_clip_count_below_the_cap_is_respected(self):
        pro = entitlements_for(PlanSlug.PRO.value)
        _, _, settings = _apply_entitlements(pro, ["9:16"], True, {"max_clips": 3})
        assert settings["max_clips"] == 3

    def test_missing_clip_count_defaults_to_the_cap(self):
        free = entitlements_for(PlanSlug.FREE.value)
        _, _, settings = _apply_entitlements(free, ["9:16"], True, None)
        assert settings["max_clips"] == free.max_clips_per_video

    @pytest.mark.parametrize("bad", [0, -5, "many", None])
    def test_invalid_clip_count_falls_back_to_the_cap(self, bad):
        free = entitlements_for(PlanSlug.FREE.value)
        _, _, settings = _apply_entitlements(free, ["9:16"], True, {"max_clips": bad})
        assert settings["max_clips"] == free.max_clips_per_video

    def test_free_cannot_request_a_paid_caption_style(self):
        free = entitlements_for(PlanSlug.FREE.value)
        with pytest.raises(CustomException) as exc:
            _apply_entitlements(free, ["9:16"], True, {"caption_style": "cyberpunk"})
        assert exc.value.status_code == 403
        assert exc.value.code == "CAPTION_STYLE_NOT_ENTITLED"

    def test_free_can_request_an_included_caption_style(self):
        free = entitlements_for(PlanSlug.FREE.value)
        _, _, settings = _apply_entitlements(free, ["9:16"], True, {"caption_style": "hormozi"})
        assert settings["caption_style"] == "hormozi"

    def test_paid_can_request_any_caption_style(self):
        pro = entitlements_for(PlanSlug.PRO.value)
        _, _, settings = _apply_entitlements(pro, ["9:16"], True, {"caption_style": "cyberpunk"})
        assert settings["caption_style"] == "cyberpunk"

    def test_style_type_alias_is_also_checked(self):
        # The burn payload names the field style_type rather than caption_style.
        free = entitlements_for(PlanSlug.FREE.value)
        with pytest.raises(CustomException):
            _apply_entitlements(free, ["9:16"], True, {"style_type": "luxury"})

    def test_original_clip_settings_are_not_mutated(self):
        free = entitlements_for(PlanSlug.FREE.value)
        original = {"max_clips": 999, "other": "kept"}
        _, _, settings = _apply_entitlements(free, ["9:16"], True, original)
        assert original["max_clips"] == 999
        assert settings["other"] == "kept"
