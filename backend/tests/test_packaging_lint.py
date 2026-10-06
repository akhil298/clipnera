from __future__ import annotations

import asyncio
import json

from content_intelligence.metadata_gen import MetadataGenerator
from content_intelligence.packaging_lint import repeats, restates

HOOK = "in just about four days our immunity system gets 50% better"


def test_a_title_that_restates_its_hook_is_caught():
    assert restates("Gratitude boosts immunity by 50% in just 4 days", HOOK)
    assert {"immunity", "50", "4", "day"} <= repeats("Gratitude boosts immunity by 50% in just 4 days", HOOK)


def test_a_title_that_pairs_with_its_hook_passes():
    assert not restates("Ten minutes of thanks a day changes your body", HOOK)
    assert not restates("Anything", None)


class _Writer:
    def __init__(self, title: str) -> None:
        self.title, self.prompts = title, []

    async def chat(self, messages, **_):
        self.prompts.append(messages[-1]["content"])
        return json.dumps({"items": [{"index": 0, "title": self.title, "description": "d", "hashtags": ["#a"]}]})


def _clip(title: str) -> dict:
    return {"title": title, "hook_text": HOOK, "transcript_excerpt": "we practice gratitude", "content_category": "podcast_interview"}


def test_a_restating_title_is_written_again_with_the_hook_to_avoid():
    writer = _Writer("Ten minutes of thanks a day changes your body")
    (clip,) = asyncio.run(MetadataGenerator(writer).generate_batch([_clip("Gratitude boosts immunity by 50% in 4 days")]))
    assert clip["title"] == "Ten minutes of thanks a day changes your body"
    assert "must not repeat its words" in writer.prompts[0] and HOOK in writer.prompts[0]


def test_a_rewrite_that_is_no_better_keeps_the_original():
    writer = _Writer("Immunity jumps 50% in four days")
    (clip,) = asyncio.run(MetadataGenerator(writer).generate_batch([_clip("Gratitude lifts immunity 50%")]))
    assert clip["title"] == "Gratitude lifts immunity 50%"


def test_a_good_title_costs_no_call():
    writer = _Writer("unused")
    (clip,) = asyncio.run(MetadataGenerator(writer).generate_batch([_clip("Ten minutes of thanks a day")]))
    assert clip["title"] == "Ten minutes of thanks a day" and writer.prompts == []


def _line(words: list[str], start: float = 20.0, step: float = 0.45):
    from content_intelligence.sentences import Sentence

    timed = [{"word": w, "start": start + i * step, "end": start + i * step + 0.4} for i, w in enumerate(words)]
    return Sentence(id=5, start=timed[0]["start"], end=timed[-1]["end"], text=" ".join(words), words=timed)


def test_a_long_hook_is_cut_where_a_clause_ends():
    from content_intelligence.edit_plan import _hook

    line = _line("I promise you, if you're sincere, just for two, three weeks of doing that, you'll surprise yourself".split())
    start, end = _hook(5, [1, 5], {5: line}, [(0.0, 60.0)])
    kept = [w["word"] for w in line.words if start <= w["start"] and w["end"] <= end]
    assert kept[-1].endswith(",") and "you'll" not in kept


def test_a_long_hook_with_no_clause_end_is_dropped():
    from content_intelligence.edit_plan import _hook

    line = _line(("word " * 30).split())
    assert _hook(5, [1, 5], {5: line}, [(0.0, 60.0)]) is None
