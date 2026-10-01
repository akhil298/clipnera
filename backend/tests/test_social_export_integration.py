from __future__ import annotations

import pytest

from content_intelligence.word_snapper import snap_clip_to_words
from subtitle_styling.emoji_annotator import annotate_caption_words, build_emoji_lookup
from subtitle_styling.phrase_segmenter import segment_for_captions, segment_phrases
from subtitle_styling.service import SubtitleStylingService
from subtitle_styling.templates import CAPTION_TEMPLATES
from clip_generation.model import SocialPlatform, SOCIAL_PLATFORM_DEFAULTS


class TestSocialExportTemplate:
    def test_platform_defaults_structure(self):
        from clip_generation.model import SOCIAL_PLATFORM_DEFAULTS

        assert len(SOCIAL_PLATFORM_DEFAULTS) == 8

        for platform, defaults in SOCIAL_PLATFORM_DEFAULTS.items():
            assert defaults["aspect_ratio"] in ("9:16", "1:1", "16:9")
            assert isinstance(defaults["dimensions"], list)
            assert len(defaults["dimensions"]) == 2
            assert isinstance(defaults["max_duration"], int)
            assert isinstance(defaults["emoji_enabled"], bool)

    def test_tiktok_has_emoji(self):
        from clip_generation.model import SOCIAL_PLATFORM_DEFAULTS

        assert SOCIAL_PLATFORM_DEFAULTS["tiktok"]["emoji_enabled"] is True

    def test_linkedin_no_emoji(self):
        from clip_generation.model import SOCIAL_PLATFORM_DEFAULTS

        assert SOCIAL_PLATFORM_DEFAULTS["linkedin"]["emoji_enabled"] is False


class TestEmojiAnnotationIntegration:
    def test_annotate_caption_words_basic(self):
        words = [
            {"start": 0.0, "end": 0.5, "text": "make"},
            {"start": 0.5, "end": 1.0, "text": "money"},
            {"start": 1.0, "end": 1.5, "text": "fast"},
            {"start": 1.5, "end": 2.0, "text": "today"},
        ]
        emoji_idx, emphasis = annotate_caption_words(words)
        assert isinstance(emoji_idx, dict)
        assert isinstance(emphasis, set)
        assert len(emoji_idx) > 0

    def test_ai_cues_lookup(self):
        cues = [{"keyword": "profit", "emoji": "📈"}]
        lookup = build_emoji_lookup(cues)
        assert lookup["profit"] == "📈"

    def test_emoji_with_ai_cues(self):
        words = [{"start": 0.0, "end": 0.5, "text": "profit"}]
        ai_cues = [{"keyword": "profit", "emoji": "📈"}]
        emoji_idx, _ = annotate_caption_words(words, ai_cues=ai_cues, max_emojis=1)
        assert 0 in emoji_idx

    def test_build_ass_file_accepts_ai_cues(self):
        from subtitle_styling.ass_generator import build_ass_file

        words = [
            {"start": 0.0, "end": 0.5, "text": "make"},
            {"start": 0.5, "end": 1.0, "text": "money"},
        ]
        ai_cues = [{"keyword": "money", "emoji": "💰"}]
        path = build_ass_file(
            transcript_words=words,
            clip_start=0.0,
            clip_end=1.5,
            style_id="default",
            width=1080,
            height=1920,
            title="Test",
            ai_cues=ai_cues,
        )
        assert path.endswith(".ass")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Test" in content or "test" in content.lower()
        assert "money" in content.lower()


class TestPhraseSegmentationIntegration:
    def test_segment_for_captions_basic(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello world this is a test"},
            {"start": 2.0, "end": 4.0, "text": "Another sentence here"},
        ]
        result = segment_for_captions(segments, max_chars=42, max_words_per_line=7)
        assert len(result) >= 1
        for seg in result:
            assert "start_time" in seg
            assert "end_time" in seg
            assert "text" in seg

    def test_segment_phrases_sentence_boundary(self):
        segments = [
            {"start": 0.0, "end": 3.0, "text": "This is the first sentence."},
            {"start": 3.0, "end": 6.0, "text": "This is the second sentence."},
        ]
        result = segment_phrases(segments, min_duration=2.0, max_gap=1.0, pad=0.08)
        assert len(result) >= 1
        assert result[0]["start_time"] >= 0.0


class TestPipelineSubtitleStyling:
    def test_step_subtitle_styling_exists(self):
        from pipeline.model import PipelineStepType

        assert hasattr(PipelineStepType, "SUBTITLE_STYLING")
        assert PipelineStepType.SUBTITLE_STYLING.value == "subtitle_styling"

    def test_pipeline_step_order_includes_styling(self):
        from pipeline.model import PipelineStepType

        step_order = [
            PipelineStepType.DOWNLOAD,
            PipelineStepType.TRANSCRIPTION,
            PipelineStepType.TOPIC_RESEARCH,
            PipelineStepType.HIGHLIGHT_DETECTION,
            PipelineStepType.SCORING,
            PipelineStepType.METADATA_GENERATION,
            PipelineStepType.CLIP_GENERATION,
            PipelineStepType.SUBTITLE_STYLING,
            PipelineStepType.BURN_IN_EXPORT,
        ]
        assert PipelineStepType.SUBTITLE_STYLING in step_order
        assert PipelineStepType.BURN_IN_EXPORT in step_order


class TestSubtitleStylingService:
    @pytest.mark.asyncio
    async def test_burn_subtitles_accepts_ai_cues_param(self):
        import inspect
        sig = inspect.signature(SubtitleStylingService.burn_subtitles)
        assert "ai_cues" in sig.parameters

    @pytest.mark.asyncio
    async def test_burn_subtitles_get_style_presets(self):
        service = SubtitleStylingService()
        result = await service.get_style_presets()
        types = [p["style_type"] for p in result]
        assert "karaoke" in types
        assert "spotlight" in types

    def test_style_presets_dict(self):
        # Retired ids such as "hormozi" resolve through LEGACY_STYLE_ALIASES
        # rather than existing as templates of their own.
        for style in ("karaoke", "simple", "spotlight", "typewriter", "glitch", "blur_in"):
            assert style in CAPTION_TEMPLATES
        assert "hormozi" not in CAPTION_TEMPLATES


class TestWordSnapping:
    def test_snap_to_word_boundaries(self):
        words = [
            {"start": 0.0, "end": 0.5, "text": "hello"},
            {"start": 0.5, "end": 1.0, "text": "world"},
            {"start": 1.0, "end": 1.5, "text": "test"},
        ]
        result = snap_clip_to_words(
            start=0.3, end=1.2,
            words=words, video_duration=2.0,
            min_duration=1.0, max_duration=5.0,
        )
        assert result[0] >= 0.0
        assert result[1] <= 2.0
        assert result[1] > result[0]

    def test_snap_no_words_fallback(self):
        result = snap_clip_to_words(
            start=5.0, end=10.0,
            words=[], video_duration=30.0,
        )
        assert result[0] == 5.0
        assert result[1] == 10.0
