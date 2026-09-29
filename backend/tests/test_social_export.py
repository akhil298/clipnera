from __future__ import annotations

import pytest

from clip_generation.model import SocialPlatform, SOCIAL_PLATFORM_DEFAULTS
from clip_generation.schema import SocialExportRequest, SocialExportResponse, SocialExportClipResponse


class TestSocialPlatform:
    def test_platforms_exist(self):
        assert SocialPlatform.TIKTOK.value == "tiktok"
        assert SocialPlatform.INSTAGRAM_REELS.value == "instagram_reels"
        assert SocialPlatform.YOUTUBE_SHORTS.value == "youtube_shorts"
        assert SocialPlatform.LINKEDIN.value == "linkedin"
        assert SocialPlatform.TWITTER.value == "twitter"
        assert SocialPlatform.SNAPCHAT.value == "snapchat"

    def test_all_defaults_have_required_keys(self):
        for platform, defaults in SOCIAL_PLATFORM_DEFAULTS.items():
            assert "aspect_ratio" in defaults, f"Missing aspect_ratio for {platform}"
            assert "dimensions" in defaults, f"Missing dimensions for {platform}"
            assert "subtitle_style" in defaults, f"Missing subtitle_style for {platform}"
            assert "max_duration" in defaults, f"Missing max_duration for {platform}"
            assert "emoji_enabled" in defaults, f"Missing emoji_enabled for {platform}"
            assert len(defaults["dimensions"]) == 2
            assert defaults["dimensions"][0] > 0
            assert defaults["dimensions"][1] > 0

    def test_tiktok_defaults(self):
        defaults = SOCIAL_PLATFORM_DEFAULTS["tiktok"]
        assert defaults["aspect_ratio"] == "9:16"
        assert defaults["dimensions"] == [1080, 1920]
        assert defaults["subtitle_style"] == "tiktok"
        assert defaults["emoji_enabled"] is True

    def test_twitter_defaults(self):
        defaults = SOCIAL_PLATFORM_DEFAULTS["twitter"]
        assert defaults["aspect_ratio"] == "16:9"
        assert defaults["subtitle_style"] == "minimal"
        assert defaults["max_duration"] == 140

    def test_linkedin_defaults(self):
        defaults = SOCIAL_PLATFORM_DEFAULTS["linkedin"]
        assert defaults["aspect_ratio"] == "1:1"
        assert defaults["subtitle_style"] == "podcast"
        assert defaults["emoji_enabled"] is False


class TestSocialExportRequest:
    def test_defaults(self):
        req = SocialExportRequest()
        assert "tiktok" in req.platforms
        assert "instagram_reels" in req.platforms
        assert req.style_type is None
        assert req.max_clips == 10
        assert req.enable_emoji is True
        assert req.watermark_enabled is True
        assert req.burn_subtitles is True
        assert req.show_title is True

    def test_custom_platforms(self):
        req = SocialExportRequest(platforms=["tiktok", "youtube_shorts", "linkedin"])
        assert req.platforms == ["tiktok", "youtube_shorts", "linkedin"]

    def test_custom_max_clips(self):
        req = SocialExportRequest(max_clips=5)
        assert req.max_clips == 5

    def test_disable_burn(self):
        req = SocialExportRequest(burn_subtitles=False)
        assert req.burn_subtitles is False

    def test_hide_title(self):
        req = SocialExportRequest(show_title=False)
        assert req.show_title is False

    def test_disable_emoji(self):
        req = SocialExportRequest(enable_emoji=False)
        assert req.enable_emoji is False

    def test_custom_style(self):
        req = SocialExportRequest(style_type="mrbeast")
        assert req.style_type == "mrbeast"

    def test_custom_config(self):
        config = {"font_size": 42, "emoji": False}
        req = SocialExportRequest(custom_config=config)
        assert req.custom_config == config


class TestSocialExportResponse:
    def test_clip_response(self):
        clip = SocialExportClipResponse(
            clip_id="abc-123",
            platform="tiktok",
            aspect_ratio="9:16",
            burned_presigned_url="https://example.com/clip.mp4",
            local_path="/tmp/clip.mp4",
            s3_key="social/user/project/abc-123_tiktok.mp4",
        )
        assert clip.clip_id == "abc-123"
        assert clip.platform == "tiktok"
        assert clip.aspect_ratio == "9:16"

    def test_full_response(self):
        resp = SocialExportResponse(
            project_id="proj-1",
            exported_clips=[
                SocialExportClipResponse(
                    clip_id="clip-1",
                    platform="tiktok",
                    aspect_ratio="9:16",
                )
            ],
            platforms=["tiktok"],
            total_exported=1,
            watermark_enabled=True,
        )
        assert resp.project_id == "proj-1"
        assert resp.total_exported == 1
        assert len(resp.exported_clips) == 1


class TestExportSelectionFields:
    def test_clip_ids_and_aspect_ratio_default_to_none(self):
        req = SocialExportRequest()
        assert req.clip_ids is None
        assert req.aspect_ratio is None
        assert req.animation_speed is None

    def test_watermark_can_be_turned_off_in_request(self):
        assert SocialExportRequest(watermark_enabled=False).watermark_enabled is False


class TestExportEntitlements:
    @staticmethod
    def _check(plan: str, **fields):
        from pipeline.service import _check_export_entitlements
        from subscription.entitlements import entitlements_for

        _check_export_entitlements(entitlements_for(plan), SocialExportRequest(platforms=["tiktok"], **fields))

    def test_free_plan_may_export_vertical(self):
        self._check("free", aspect_ratio="9:16")

    def test_free_plan_refused_other_sizes(self):
        from core.exceptions import CustomException

        with pytest.raises(CustomException):
            self._check("free", aspect_ratio="16:9")

    def test_pro_plan_may_export_any_size(self):
        for ratio in ("9:16", "1:1", "4:5", "16:9"):
            self._check("pro", aspect_ratio=ratio)

    def test_unsupported_ratio_rejected(self):
        from core.exceptions import CustomException

        with pytest.raises(CustomException):
            self._check("pro", aspect_ratio="3:2")
