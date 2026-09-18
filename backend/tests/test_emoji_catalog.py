from __future__ import annotations

from subtitle_styling.emoji_catalog import (
    CATALOG_BY_SLUG,
    EMOJI_CATALOG,
    catalog_prompt_block,
    keyword_emoji_map,
    resolve_emoji,
    sanitize_ai_cues,
)


class TestCatalogIntegrity:
    def test_slugs_are_unique(self):
        slugs = [entry.slug for entry in EMOJI_CATALOG]
        assert len(slugs) == len(set(slugs))

    def test_every_entry_has_a_char_and_keywords(self):
        for entry in EMOJI_CATALOG:
            assert entry.char, entry.slug
            assert entry.keywords, entry.slug

    def test_slug_is_its_own_keyword(self):
        for entry in EMOJI_CATALOG:
            assert entry.slug in entry.keywords


class TestResolveEmoji:
    def test_resolves_slug(self):
        assert resolve_emoji("rocket") == CATALOG_BY_SLUG["rocket"].char

    def test_resolves_literal_char(self):
        assert resolve_emoji("\U0001F680") == "\U0001F680"

    def test_resolves_char_missing_variation_selector(self):
        # "✈️" is stored with the selector; a model often drops it.
        assert resolve_emoji("✈") == CATALOG_BY_SLUG["plane"].char

    def test_rejects_emoji_outside_catalog(self):
        assert resolve_emoji("\U0001F984") is None  # unicorn, not whitelisted

    def test_rejects_invented_slug(self):
        assert resolve_emoji("definitely_not_a_slug") is None

    def test_rejects_empty(self):
        assert resolve_emoji("") is None
        assert resolve_emoji(None) is None


class TestSanitizeAiCues:
    def test_keeps_whitelisted_cue(self):
        assert sanitize_ai_cues([{"keyword": "Profit!", "emoji": "chart_up"}]) == [
            {"keyword": "profit", "emoji": CATALOG_BY_SLUG["chart_up"].char}
        ]

    def test_drops_unknown_emoji(self):
        assert sanitize_ai_cues([{"keyword": "profit", "emoji": "\U0001F984"}]) == []

    def test_drops_duplicate_keywords(self):
        cues = [
            {"keyword": "money", "emoji": "money"},
            {"keyword": "money", "emoji": "bank"},
        ]
        assert len(sanitize_ai_cues(cues)) == 1

    def test_accepts_emoji_id_alias(self):
        assert sanitize_ai_cues([{"keyword": "speed", "emoji_id": "zap"}]) == [
            {"keyword": "speed", "emoji": CATALOG_BY_SLUG["zap"].char}
        ]

    def test_ignores_non_list_and_malformed(self):
        assert sanitize_ai_cues(None) == []
        assert sanitize_ai_cues("rocket") == []
        assert sanitize_ai_cues([1, "x", {"keyword": "a"}]) == []

    def test_respects_max_cues(self):
        cues = [{"keyword": f"w{i}", "emoji": "rocket"} for i in range(50)]
        assert len(sanitize_ai_cues(cues, max_cues=5)) == 5


class TestPromptBlock:
    def test_lists_only_slugs_the_catalog_knows(self):
        categories = {entry.category for entry in EMOJI_CATALOG}
        for line in catalog_prompt_block().splitlines():
            category, _, slugs = line.partition(":")
            assert category in categories, category
            for slug in slugs.split(","):
                assert slug.strip() in CATALOG_BY_SLUG, slug

    def test_every_slug_is_offered_to_the_model(self):
        block = catalog_prompt_block()
        for entry in EMOJI_CATALOG:
            assert entry.slug in block


class TestKeywordMap:
    def test_flattens_keywords(self):
        lookup = keyword_emoji_map()
        assert lookup["cash"] == CATALOG_BY_SLUG["money"].char
        assert lookup["rocket"] == CATALOG_BY_SLUG["rocket"].char

    def test_earlier_entry_wins_on_collision(self):
        lookup = keyword_emoji_map()
        # "money" appears as both a slug and a keyword of other entries.
        assert lookup["money"] == CATALOG_BY_SLUG["money"].char
