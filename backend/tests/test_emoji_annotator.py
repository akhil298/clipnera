from __future__ import annotations

import pytest

from subtitle_styling.emoji_annotator import (
    EMOJI_KEYWORD_MAP,
    POWER_WORDS,
    annotate_caption_words,
    build_emoji_lookup,
    normalize_token,
    _singularize,
    _lookup_emoji,
)


class TestNormalizeToken:
    def test_basic(self):
        assert normalize_token("Hello") == "hello"

    def test_strips_punctuation(self):
        assert normalize_token("hello!!!") == "hello"
        assert normalize_token("(test)") == "test"

    def test_empty(self):
        assert normalize_token("") == ""
        assert normalize_token("!!!") == ""


class TestSingularize:
    def test_plural_ies(self):
        assert _singularize("ideas") == "idea"
        assert _singularize("babies") == "babe"

    def test_plural_s(self):
        assert _singularize("goals") == "goal"
        assert _singularize("stories") == "storie"

    def test_no_plural(self):
        assert _singularize("test") == "test"

    def test_short_word(self):
        assert _singularize("is") == "is"


class TestLookupEmoji:
    def test_direct_match(self):
        assert _lookup_emoji("money", {"money": "💰"}) == "💰"

    def test_singular_match(self):
        lookup = {"money": "💰"}
        assert _lookup_emoji("moneys", lookup) == "💰"

    def test_no_match(self):
        assert _lookup_emoji("xyz", {"money": "💰"}) is None

    def test_empty_token(self):
        assert _lookup_emoji("", {"money": "💰"}) is None


class TestBuildEmojiLookup:
    def test_base_map(self):
        lookup = build_emoji_lookup()
        assert lookup["money"] == "\U0001F4B0"

    def test_with_ai_cues(self):
        cues = [{"keyword": "customword", "emoji": "🎯"}]
        lookup = build_emoji_lookup(cues)
        assert lookup["customword"] == "🎯"

    def test_ai_cue_overrides(self):
        cues = [{"keyword": "money", "emoji": "💸"}]
        lookup = build_emoji_lookup(cues)
        assert lookup["money"] == "💸"

    def test_empty_cues(self):
        lookup = build_emoji_lookup(None)
        assert "money" in lookup

    def test_malformed_cue_ignored(self):
        cues = [{"keyword": "", "emoji": "🎯"}, {"keyword": 123, "emoji": "🎯"}]
        lookup = build_emoji_lookup(cues)
        assert 123 not in lookup


class TestAnnotateCaptionWords:
    @pytest.fixture
    def words(self):
        return [
            {"start": 0.0, "end": 0.5, "text": "make"},
            {"start": 0.5, "end": 1.0, "text": "money"},
            {"start": 1.0, "end": 1.5, "text": "fast"},
            {"start": 1.5, "end": 2.0, "text": "easy"},
            {"start": 2.0, "end": 2.5, "text": "today"},
        ]

    def test_emoji_annotation(self, words):
        emoji_idx, emphasis = annotate_caption_words(words)
        assert 1 in emoji_idx
        assert emoji_idx[1] == "\U0001F4B0"

    def test_emphasis_for_power_words(self, words):
        emoji_idx, emphasis = annotate_caption_words(words)
        assert 4 in emphasis
        assert 3 in emphasis

    def test_max_emojis_limit(self, words):
        emoji_idx, _ = annotate_caption_words(words, max_emojis=1)
        assert len(emoji_idx) <= 1

    def test_min_word_gap(self, words):
        emoji_idx, _ = annotate_caption_words(words, min_word_gap=3, max_emojis=10)
        indices = sorted(emoji_idx.keys())
        for i in range(1, len(indices)):
            assert indices[i] - indices[i - 1] >= 3

    def test_disable_emoji(self, words):
        emoji_idx, emphasis = annotate_caption_words(words, enable_emoji=False)
        assert emoji_idx == {}
        assert 1 not in emphasis
        assert 3 in emphasis

    def test_disable_emphasis(self, words):
        emoji_idx, emphasis = annotate_caption_words(words, enable_emphasis=False)
        assert emphasis == set()

    def test_number_annotation(self):
        words = [{"start": 0.0, "end": 0.5, "text": "10x"}]
        emoji_idx, emphasis = annotate_caption_words(words)
        assert 0 in emphasis

    def test_empty_words(self):
        emoji_idx, emphasis = annotate_caption_words([])
        assert emoji_idx == {}
        assert emphasis == set()

    def test_repeat_gap(self):
        words = [
            {"start": i, "end": i + 0.5, "text": "money"}
            for i in range(20)
        ]
        emoji_idx, _ = annotate_caption_words(words, repeat_gap=5, max_emojis=10)
        for i in range(len(emoji_idx) - 1):
            indices = sorted(emoji_idx.keys())
            for j in range(1, len(indices)):
                assert indices[j] - indices[j - 1] >= 5
