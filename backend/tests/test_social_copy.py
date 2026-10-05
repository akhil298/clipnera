"""Instagram caption and hashtags for each clip, and Tenglish for Telugu speech."""

from __future__ import annotations

import json

import pytest

from content_intelligence.social_copy import MAX_HASHTAGS, SocialCopyWriter, clean_hashtags, finish
from transcription.language import spoken_language



class _Client:
    def __init__(self, items_for):
        self.items_for = items_for
        self.prompts: list[str] = []

    async def chat(self, messages, **kwargs):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        return json.dumps({"items": self.items_for(prompt)})


def _clips(n: int, **extra) -> list[dict]:
    return [{"title": f"Title {i}", "description": f"Desc {i}", "transcript_excerpt": f"words {i}",
             "content_category": "podcast_interview", "hashtags": ["#podcast"], **extra} for i in range(n)]


@pytest.mark.asyncio
async def test_every_clip_gets_a_caption_and_specific_hashtags():
    def items(prompt):
        return [{"index": i, "caption": f"Hook {i}\nContext\nSend this to a friend", "hashtags": ["#fyp", "#moneytips", "#Investing"]}
                for i in range(8) if f"[{i}]" in prompt]

    client = _Client(items)
    clips = await SocialCopyWriter(client).write(_clips(8))
    # Eight clips go out in two batches.
    assert len(client.prompts) == 2
    for clip in clips:
        assert clip["social_caption"].startswith("Hook")
        assert "#fyp" not in clip["hashtags"]
        assert 3 <= len(clip["hashtags"]) <= MAX_HASHTAGS


@pytest.mark.asyncio
async def test_a_failed_batch_falls_back_to_the_clips_own_copy():
    class _Broken:
        async def chat(self, *a, **k):
            raise RuntimeError("provider down")

    clips = await SocialCopyWriter(_Broken()).write(_clips(2))
    assert clips[0]["social_caption"] == "Title 0\nDesc 0"
    assert "#podcast" in clips[0]["hashtags"]


@pytest.mark.asyncio
async def test_telugu_speech_asks_for_tenglish_and_never_keeps_telugu_script():
    def items(prompt):
        return [{"index": 0, "caption": "ఈ trick తో mee salary double 🔥", "hashtags": ["#తెలుగు", "#money"]}]

    client = _Client(items)
    clip = (await SocialCopyWriter(client).write(_clips(1, title="మీ money waste"), language="te"))[0]
    assert "Tenglish" in client.prompts[0]
    assert "#telugu" in client.prompts[0]
    for text in (clip["social_caption"], clip["title"], *clip["hashtags"]):
        assert not any("ఀ" <= ch <= "౿" for ch in text), text


def test_hashtags_are_capped_at_five_and_deduplicated():
    tags = clean_hashtags(["#a1", "#A1", "#b2", "#c3", "#d4", "#e5", "#f6"], "tech", "en")
    assert tags == ["#a1", "#b2", "#c3", "#d4", "#e5"]


def test_too_few_hashtags_are_topped_up_from_the_category():
    tags = clean_hashtags(["#viral"], "food", "te")
    assert tags[0] == "#telugu" and len(tags) == 3


def test_finish_without_copy_keeps_the_clip_usable():
    clip = finish({"title": "T", "description": None, "content_category": "tech"}, None, "en")
    assert clip["social_caption"] == "T"
    assert clip["hashtags"]


def test_romanised_telugu_is_still_recognised_as_telugu():
    segments = [{"words": [{"word": "meeru", "native": "మీరు"}, {"word": "money"}, {"word": "cheyandi", "native": "చేయండి"}]}]
    assert spoken_language(segments, "en") == "te"
    assert spoken_language([{"text": "plain english words here"}], "en") == "en"
