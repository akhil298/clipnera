"""Formats in the Map and Director passes and in the clips built from their plans."""

from __future__ import annotations

import json

import pytest

from content_intelligence.director import DIRECTOR_SCHEMA, MAP_SCHEMA, VideoDirector, _merge_maps
from content_intelligence.edit_plan import build_clips, build_story_clips
from content_intelligence.sentences import build_sentences
from formats import FORMATS, RECIPES, VisualEvidence
from test_director import _segment, _talk

SCORES = {"hook": 8, "payoff": 8, "standalone": 8, "emotion": 7, "pacing": 7}
FACE = VisualEvidence(start=0.0, end=10_000.0, face=0.9)
SCREEN = VisualEvidence(start=0.0, end=10_000.0, face=0.6, screen=0.8, facecam=0.5,
                        facecam_box=(0.75, 0.75, 0.2, 0.2), content_box=(0.0, 0.0, 1.0, 0.7))


def _clips(plan: dict, evidence: list[VisualEvidence] | None, count: int = 40, video_format: str | None = None,
           segments: list[dict] | None = None, jump_cuts: bool = False) -> list[dict]:
    sentences = build_sentences(segments or _talk(count))
    return build_clips([{"scores": SCORES, **plan}], sentences, sentences[-1].end, 10.0, 60.0, 5, "podcast_interview",
                       jump_cuts, evidence=evidence, video_format=video_format)


class TestSchemas:
    def test_map_has_video_and_candidate_formats(self):
        assert MAP_SCHEMA["properties"]["format"]["enum"] == list(FORMATS)
        assert {"format", "format_confidence"} <= set(MAP_SCHEMA["required"])
        assert "format" in MAP_SCHEMA["properties"]["candidates"]["items"]["required"]

    def test_director_has_format_and_items(self):
        clip = DIRECTOR_SCHEMA["properties"]["clips"]["items"]
        assert {"format", "items", "layout"} <= set(clip["required"])
        item = clip["properties"]["items"]["items"]
        assert item["required"] == ["at", "label", "rank"] and item["additionalProperties"] is False


class TestFormatResolution:
    def test_supported_choice_is_kept(self):
        clip = _clips({"segments": [{"from": 3, "to": 8}], "format": "screen_share"}, [SCREEN])[0]
        assert clip["content_format"] == "screen_share" and clip["format_source"] == "ai"
        assert clip["layout_hint"] == RECIPES["screen_share"].layout
        assert clip["format_evidence"]["facecam_box"] == [0.75, 0.75, 0.2, 0.2]

    def test_unsupported_choice_falls_back_to_the_picture(self):
        clip = _clips({"segments": [{"from": 3, "to": 8}], "format": "screen_share", "layout": "single_speaker"},
                      [FACE])[0]
        assert clip["content_format"] == "talking_head" and clip["format_source"] == "visual"
        assert clip["layout_hint"] == "single_speaker"  # follow-layout formats keep the director's hint

    def test_without_evidence_only_formats_needing_nothing_survive(self):
        clip = _clips({"segments": [{"from": 3, "to": 8}], "format": "yap"}, None)[0]
        assert clip["content_format"] == "talking_head" and clip["format_evidence"] is None

    def test_plan_without_format_takes_the_video_format(self):
        clip = _clips({"segments": [{"from": 3, "to": 8}]}, [FACE], video_format="yap")[0]
        assert clip["content_format"] == "yap" and clip["format_source"] == "ai"

    def test_evidence_is_judged_over_played_spans_only(self):
        """A story's pieces sit in face footage; the screen recording between them does not count."""
        sentences = build_sentences(_talk(200))
        evidence = [VisualEvidence(start=0, end=100, face=0.9), VisualEvidence(start=100, end=700, screen=0.9),
                    VisualEvidence(start=700, end=1000, face=0.9)]
        clips = build_story_clips(
            [{"segments": [{"from": 10, "to": 11}, {"from": 150, "to": 151}], "format": "screen_share", "scores": SCORES}],
            sentences, 1000.0, 5.0, 60.0, 3, "podcast_interview", False, evidence=evidence)
        assert clips[0]["content_format"] == "talking_head"
        assert clips[0]["format_evidence"]["screen"] == 0.0


class TestListItems:
    def test_items_map_to_times_and_are_clipped_to_the_spans(self):
        sentences = build_sentences(_talk(40))
        by_id = {s.id: s for s in sentences}
        items = [{"at": 7, "label": "Second tip", "rank": 0}, {"at": 4, "label": "First tip", "rank": 0},
                 {"at": 30, "label": "Outside", "rank": 0}, {"at": "x", "label": "Garbage", "rank": 0}]
        clip = _clips({"segments": [{"from": 3, "to": 9}], "format": "listicle", "items": items}, [FACE])[0]
        assert clip["content_format"] == "listicle" and clip["layout_hint"] == "auto"
        assert [i["label"] for i in clip["format_items"]] == ["First tip", "Second tip"]
        first, second = clip["format_items"]
        assert first["t"] == pytest.approx(by_id[4].words[0]["start"]) and first["end"] == second["t"]
        assert second["end"] == clip["end_time"] and first["rank"] is None

    def test_ranking_keeps_ranks_as_said(self):
        items = [{"at": 4, "label": "Bronze", "rank": 3}, {"at": 6, "label": "Silver", "rank": 2},
                 {"at": 8, "label": "Gold", "rank": 1}]
        clip = _clips({"segments": [{"from": 3, "to": 9}], "format": "ranking", "items": items}, [FACE])[0]
        assert [i["rank"] for i in clip["format_items"]] == [3, 2, 1]

    def test_a_list_with_one_item_falls_back(self):
        clip = _clips({"segments": [{"from": 3, "to": 9}], "format": "listicle",
                       "items": [{"at": 4, "label": "Only", "rank": 0}, {"at": 30, "label": "Outside", "rank": 0}]},
                      [FACE], video_format="listicle")[0]
        assert clip["content_format"] == "talking_head" and clip["format_items"] == []

    def test_other_formats_carry_no_items(self):
        clip = _clips({"segments": [{"from": 3, "to": 9}], "format": "talking_head",
                       "items": [{"at": 4, "label": "A", "rank": 0}, {"at": 6, "label": "B", "rank": 0}]}, [FACE])[0]
        assert clip["format_items"] == []


class TestFormatPacing:
    def test_yap_cuts_shorter_pauses(self):
        # 0.4s gaps between words: breath for a talking head, dead air for a yap.
        segments = [_segment(i * 6.0, " ".join(["word"] * 10) + f" end{i}.", gap=0.3) for i in range(20)]
        for segment in segments:
            for n, word in enumerate(segment["words"]):
                word["start"] = round(segment["start"] + n * 0.7, 2)
                word["end"] = round(word["start"] + 0.3, 2)
            segment["end"] = segment["words"][-1]["end"]
        plan = {"segments": [{"from": 2, "to": 5}]}
        talking = _clips({**plan, "format": "talking_head"}, [FACE], segments=segments, jump_cuts=True)[0]
        yap = _clips({**plan, "format": "yap"}, [FACE], segments=segments, jump_cuts=True)[0]
        assert yap["content_format"] == "yap"
        assert len(yap["edit_spans"]) > len(talking["edit_spans"])


class TestMapFormats:
    def test_merge_votes_format_by_confidence_and_defaults_bad_values(self):
        sentences = build_sentences(_talk(50))
        merged = _merge_maps([
            {"category": "tech", "format": "screen_share", "format_confidence": 0.9,
             "candidates": [{"from": 3, "to": 9, "hook": 0, "format": "listicle", "why": "x"}]},
            {"category": "tech", "format": "talking_head", "format_confidence": 0.3,
             "candidates": [{"from": 20, "to": 25, "hook": 0, "format": "bogus", "why": "y"}]},
            {"category": "tech", "format": "talking_head", "format_confidence": "high"},
            {"category": "tech", "format": "nonsense"},
        ], sentences)
        assert merged["format"] == "screen_share" and merged["format_confidence"] == 0.23  # 0.9 of 4 windows
        assert [c["format"] for c in merged["candidates"]] == ["listicle", "screen_share"]

    def test_no_format_votes_default_to_talking_head(self):
        merged = _merge_maps([{"category": "tech", "candidates": []}], build_sentences(_talk(10)))
        assert merged["format"] == "talking_head" and merged["format_confidence"] == 0.0


class _Client:
    def __init__(self, replies: list[dict]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    async def chat(self, messages, **kwargs):
        self.systems.append(messages[0]["content"])
        self.prompts.append(messages[-1]["content"])
        return json.dumps(self._replies.pop(0))


class TestPrompts:
    @pytest.mark.asyncio
    async def test_evidence_catalogue_and_playbooks_reach_the_models(self):
        sentences = build_sentences(_talk(40))
        map_client = _Client([{"title": "T", "summary": "S", "category": "tech", "confidence": 0.9, "topics": [],
                               "entities": [], "format": "screen_share", "format_confidence": 0.8,
                               "candidates": [{"from": 3, "to": 9, "hook": 6, "format": "listicle", "why": "w"}]}])
        director_client = _Client([{"clips": []}, {"clips": []}])
        director = VideoDirector(map_client, director_client)
        video_map = await director.map(sentences, 200.0, {}, 10, evidence="screen recording 80% of frames")
        assert "On screen (measured): screen recording" in map_client.prompts[0]
        assert "- ranking:" in map_client.systems[0]

        await director.direct(sentences, video_map, 5, 20.0, 60.0, evidence="webcam bottom right")
        system, prompt = director_client.systems[0], director_client.prompts[0]
        assert RECIPES["screen_share"].playbook in system and RECIPES["listicle"].playbook in system
        assert "On screen (measured): webcam bottom right" in prompt and "Format: screen_share" in prompt
        assert "sentences 3-9 (~" in prompt and "listicle" in prompt

        video_map["candidates"].append({"from": 30, "to": 33, "format": "talking_head", "why": "z"})
        await director.story(sentences, video_map, 2, 15.0, 60.0)
        assert "Ranking:" in director_client.systems[1] and RECIPES["ranking"].playbook in director_client.systems[1]
        assert "On screen" not in director_client.prompts[1]
