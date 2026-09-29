from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from clip_generation.hook import body_duration, on_output_timeline, parse_spans, trim_spans, Hook
from content_intelligence.director import CHECK_SCHEMA, DIRECTOR_SCHEMA, MAP_SCHEMA, VideoDirector, _merge_maps, _spread, _windows
from content_intelligence.edit_plan import build_clips, build_story_clips
from content_intelligence.service import story_clip_count
from video_processor.clip_cutter import CutRequest
from content_intelligence.sentences import Sentence, build_sentences, format_table
from content_intelligence.signals import AudioSignals, loudness_signals


def _segment(start: float, text: str, speaker: str | None = "Speaker 1", gap: float = 0.3) -> dict:
    words, t = [], start
    for token in text.split():
        words.append({"start": round(t, 2), "end": round(t + gap, 2), "word": token})
        t += gap + 0.05
    return {"start": words[0]["start"], "end": words[-1]["end"], "text": text, "speaker": speaker, "words": words}


def _talk(count: int, seconds_each: float = 5.0) -> list[dict]:
    """``count`` sentences of ~``seconds_each`` seconds, back to back."""
    segments = []
    for i in range(count):
        n = int(seconds_each / 0.35)
        text = " ".join(["word"] * (n - 1)) + f" end{i}."
        segments.append(_segment(i * seconds_each, text))
    return segments


class TestSentences:
    def test_ids_speakers_and_flags(self):
        segments = [
            _segment(0.0, "Did you ever lose money?", "Speaker 1"),
            _segment(4.0, "Yes. I lost everything in eleven days.", "Speaker 2"),
        ]
        sentences = build_sentences(segments)
        assert [s.id for s in sentences] == [1, 2, 3]
        assert sentences[0].speaker == "A" and sentences[1].speaker == "B"
        assert "Q" in sentences[0].flags
        assert "P" in sentences[1].flags  # a >1.5s pause precedes the answer

    def test_line_format_is_compact(self):
        sentence = Sentence(id=7, start=12.34, end=15.0, text="Hello there.", speaker="A", flags="EQ")
        assert sentence.line() == "7 12.3 A !E!Q Hello there."

    def test_energy_flag_comes_from_loudness(self):
        segments = [_segment(0.0, "quiet line here."), _segment(3.0, "LOUD line here.")]
        z = np.zeros(40)
        z[13] = 3.0  # 3.25s, inside the second sentence
        sentences = build_sentences(segments, AudioSignals(step=0.25, z=z))
        assert "E" not in sentences[0].flags and "E" in sentences[1].flags

    def test_continuation_detection(self):
        assert Sentence(1, 0, 1, "And then it broke.").opens_mid_thought
        assert not Sentence(1, 0, 1, "It broke then.").opens_mid_thought


class TestSignals:
    def test_a_burst_is_a_peak(self):
        rate = 8000
        samples = (np.random.default_rng(0).normal(0, 300, rate * 20)).astype(np.int16)
        samples[rate * 10: rate * 11] = (samples[rate * 10: rate * 11].astype(np.int32) * 20).clip(-32000, 32000)
        signals = loudness_signals(samples, rate)
        assert signals is not None
        assert signals.peak_between(10.0, 11.0) > 1.5
        assert signals.peak_between(2.0, 3.0) < 1.5


class TestEditPlan:
    def _clips(self, plans, count=40, min_s=20.0, max_s=60.0, jump_cuts=False):
        sentences = build_sentences(_talk(count))
        return build_clips(plans, sentences, duration=count * 5.0, min_seconds=min_s, max_seconds=max_s,
                           max_clips=10, category="podcast_interview", jump_cuts=jump_cuts), sentences

    def test_ids_become_word_exact_spans(self):
        clips, sentences = self._clips([{"segments": [{"from": 3, "to": 8}], "hook": 6, "title": "T",
                                         "scores": {"hook": 8, "payoff": 8, "standalone": 8, "emotion": 6, "pacing": 7}}])
        clip = clips[0]
        by_id = {s.id: s for s in sentences}
        assert clip["start_time"] == pytest.approx(by_id[3].start - 0.08, abs=0.01)
        assert clip["end_time"] <= by_id[9].start + 1e-6
        assert clip["hook_start"] == pytest.approx(by_id[6].start, abs=0.01)
        assert clip["title"] == "T"
        assert 0 < clip["score"] <= 1

    def test_stitched_segments_skip_the_middle(self):
        clips, sentences = self._clips([{"segments": [{"from": 10, "to": 13}, {"from": 16, "to": 19}], "hook": 0}])
        spans = clips[0]["edit_spans"]
        by_id = {s.id: s for s in sentences}
        assert len(spans) == 2
        assert spans[0][1] <= by_id[14].start + 1e-6
        assert spans[1][0] >= by_id[15].end - 1e-6

    def test_too_long_is_trimmed_and_too_short_is_grown(self):
        long_clips, _ = self._clips([{"segments": [{"from": 1, "to": 30}]}])
        short_clips, _ = self._clips([{"segments": [{"from": 5, "to": 5}]}])
        for clip in long_clips + short_clips:
            body = sum(e - s for s, e in clip["edit_spans"])
            assert 19.0 <= body <= 61.0

    def test_first_line_is_never_the_hook(self):
        clips, _ = self._clips([{"segments": [{"from": 3, "to": 8}], "hook": 3}])
        assert clips[0]["hook_start"] is None

    def test_duplicates_keep_the_better_clip(self):
        plans = [
            {"segments": [{"from": 3, "to": 8}], "scores": {"hook": 4, "payoff": 4, "standalone": 4, "emotion": 4, "pacing": 4}},
            {"segments": [{"from": 4, "to": 9}], "scores": {"hook": 9, "payoff": 9, "standalone": 9, "emotion": 9, "pacing": 9}},
        ]
        clips, _ = self._clips(plans)
        assert len(clips) == 1 and clips[0]["rubric"]["hook"] == 9

    def test_opening_mid_thought_walks_back(self):
        segments = _talk(10)
        segments[4] = _segment(20.0, "And " + " ".join(["word"] * 12) + " end4.")
        sentences = build_sentences(segments)
        clips = build_clips([{"segments": [{"from": 5, "to": 9}]}], sentences, 50.0, 10.0, 60.0, 5, "vlog", False)
        assert clips[0]["start_time"] < sentences[4].start

    def test_jump_cuts_remove_long_pauses_and_fillers(self):
        segments = [_segment(0.0, "This is the first part of the thought"),
                    _segment(6.0, "um"),
                    _segment(9.0, "and this is the second part of it.")]
        sentences = build_sentences(segments)
        clips = build_clips([{"segments": [{"from": 1, "to": sentences[-1].id}]}], sentences, 20.0, 1.0, 60.0, 3, "vlog", True)
        spans = clips[0]["edit_spans"]
        assert len(spans) >= 2
        body = sum(e - s for s, e in spans)
        assert body < (spans[-1][1] - spans[0][0]) - 2.0

    def test_garbage_plans_are_dropped_not_raised(self):
        clips, _ = self._clips([{"segments": "nope"}, {"segments": [{"from": 999, "to": 1000}]}, "x"])
        assert clips == []


class TestTimelineWithSpans:
    def test_words_pack_onto_the_stitched_timeline(self):
        words = [{"start": 10.0, "end": 10.5}, {"start": 15.0, "end": 15.5}, {"start": 30.0, "end": 30.5}]
        spans = [(10.0, 12.0), (30.0, 32.0)]
        origin, placed = on_output_timeline(words, 10.0, 32.0, None, spans=spans)
        assert origin == 10.0
        assert [(w["start"] - origin) for w in placed] == [0.0, 2.0]  # the 15s word was cut out
        assert body_duration(10.0, 32.0, spans) == 4.0

    def test_teaser_then_stitched_body(self):
        words = [{"start": 31.0, "end": 31.5}, {"start": 10.0, "end": 10.5}]
        hook = Hook(30.0, 32.0)
        origin, placed = on_output_timeline(words, 10.0, 32.0, hook, spans=[(10.0, 12.0), (30.0, 32.0)])
        offsets = sorted(round(w["start"] - origin, 2) for w in placed)
        # teaser word at 1.0s, body words at 2.0 (10.0) and 2 + 2 + 1.0 (31.0)
        assert offsets == [1.0, 2.0, 5.0]

    def test_no_spans_keeps_old_behaviour(self):
        words = [{"start": 10.0, "end": 10.5}]
        assert on_output_timeline(words, 10.0, 20.0, None) == (10.0, words)

    def test_parse_and_trim(self):
        assert parse_spans(json.dumps([[1, 2], [3, 5]])) == [(1.0, 2.0), (3.0, 5.0)]
        assert parse_spans(None) is None and parse_spans("") is None
        assert trim_spans([(0.0, 10.0), (20.0, 30.0)], 12.0) == [(0.0, 10.0), (20.0, 22.0)]


class _Client:
    def __init__(self, replies: list[dict]):
        self._replies = list(replies)
        self.prompts: list[str] = []

    def input_token_budget(self, output_tokens: int) -> int:
        return 100_000

    async def chat(self, messages, **kwargs):
        self.prompts.append(messages[-1]["content"])
        self.system = messages[0]["content"]
        return json.dumps(self._replies.pop(0))


class TestDirector:
    def test_schemas_are_closed(self):
        for schema in (MAP_SCHEMA, DIRECTOR_SCHEMA, CHECK_SCHEMA):
            assert schema["additionalProperties"] is False

    def test_windows_overlap_and_cover_everything(self):
        sentences = build_sentences(_talk(300))
        windows = _windows(sentences, budget=1500)
        assert len(windows) > 1
        covered = {s.id for w in windows for s in w}
        assert covered == {s.id for s in sentences}
        assert windows[1][0].id <= windows[0][-1].id  # overlap

    def test_merge_votes_category_and_dedupes(self):
        sentences = build_sentences(_talk(50))
        merged = _merge_maps([
            {"title": "T", "summary": "a", "category": "tech", "confidence": 0.9,
             "candidates": [{"from": 3, "to": 9, "hook": 5, "why": "x"}]},
            {"title": "T2", "summary": "b", "category": "vlog", "confidence": 0.2,
             "candidates": [{"from": 4, "to": 9, "hook": 0, "why": "dup"}, {"from": 20, "to": 25, "hook": 0, "why": "y"}]},
        ], sentences)
        assert merged["category"] == "tech"
        assert [(c["from"], c["to"]) for c in merged["candidates"]] == [(3, 9), (20, 25)]

    @pytest.mark.asyncio
    async def test_end_to_end_map_then_direct(self):
        sentences = build_sentences(_talk(40))
        map_client = _Client([{"title": "T", "summary": "S", "category": "podcast_interview", "confidence": 0.9,
                               "topics": [], "entities": [], "candidates": [{"from": 3, "to": 9, "hook": 6, "why": "w"}]}])
        director_client = _Client([{"clips": [{"segments": [{"from": 3, "to": 9}], "hook": 6, "title": "Title",
                                               "description": "d", "hashtags": ["#a"], "layout": "single_speaker",
                                               "beats": [{"at": 5, "fx": "punch_in", "word": "word"}],
                                               "scores": {"hook": 8, "payoff": 8, "standalone": 8, "emotion": 7, "pacing": 7},
                                               "why": "w"}]}])
        director = VideoDirector(map_client, director_client)
        video_map = await director.map(sentences, 200.0, {"A": "Speaker 1"}, 10)
        plans = await director.direct(sentences, video_map, 5, 20.0, 60.0)
        clips = build_clips(plans, sentences, 200.0, 20.0, 60.0, 5, video_map["category"])
        assert len(clips) == 1
        assert clips[0]["beats"] and clips[0]["beats"][0]["fx"] == "punch_in"
        assert "podcast" in director_client.system.lower()  # the category playbook rode along
        assert format_table(sentences[:1]) in map_client.prompts[0]


class TestCutToSource:
    def test_teaser_is_dropped_and_body_maps_through_spans(self):
        from clip_generation.hook import cut_to_source

        hook = Hook(30.0, 32.0)
        spans = [(10.0, 12.0), (30.0, 34.0)]
        assert cut_to_source(1.0, 10.0, 34.0, hook, spans) is None
        assert cut_to_source(2.5, 10.0, 34.0, hook, spans) == pytest.approx(10.5)
        assert cut_to_source(5.0, 10.0, 34.0, hook, spans) == pytest.approx(31.0)

    def test_plain_clip_is_a_shift(self):
        from clip_generation.hook import cut_to_source

        assert cut_to_source(3.0, 100.0, 130.0, None, None) == pytest.approx(103.0)


_SCORES = {"hook": 8, "payoff": 8, "standalone": 8, "emotion": 7, "pacing": 7}


class TestStoryClips:
    """Sentences are 5s each, so sentence n starts at (n - 1) * 5s."""

    def _stories(self, plans, count=200, min_s=15.0, max_s=60.0):
        sentences = build_sentences(_talk(count))
        return build_story_clips(plans, sentences, duration=count * 5.0, min_seconds=min_s, max_seconds=max_s,
                                 max_clips=3, category="podcast_interview", jump_cuts=False)

    def test_far_apart_pieces_become_one_clip_in_source_order(self):
        clips = self._stories([{"segments": [{"from": 150, "to": 151}, {"from": 10, "to": 11}, {"from": 80, "to": 81}],
                                "hook": 151, "title": "T", "scores": _SCORES}])
        assert len(clips) == 1
        spans = clips[0]["edit_spans"]
        assert len(spans) == 3 and spans == sorted(spans)
        assert spans[1][0] - spans[0][1] > 60
        assert clips[0]["detection_source"] == "director_story"
        assert clips[0]["transcript_excerpt"].count(" … ") == 2

    def test_pieces_close_together_are_not_a_story(self):
        assert self._stories([{"segments": [{"from": 10, "to": 12}, {"from": 15, "to": 17}], "scores": _SCORES}]) == []

    def test_a_single_piece_is_not_a_story(self):
        assert self._stories([{"segments": [{"from": 10, "to": 20}], "scores": _SCORES}]) == []

    def test_too_long_trims_the_middle_and_keeps_the_payoff(self):
        clips = self._stories([{"segments": [{"from": 10, "to": 11}, {"from": 60, "to": 66}, {"from": 150, "to": 151}],
                                "scores": _SCORES}], max_s=40.0)
        assert len(clips) == 1
        spans = clips[0]["edit_spans"]
        assert spans[-1][1] == pytest.approx(151 * 5.0 - 0.05 + 0.15, abs=0.5)  # payoff kept whole
        assert sum(e - s for s, e in spans) <= 40.0 + 3 * 0.25  # plus speech padding at each cut

    def test_too_short_is_refused(self):
        assert self._stories([{"segments": [{"from": 10, "to": 10}, {"from": 150, "to": 150}], "scores": _SCORES}],
                             min_s=30.0) == []

    def test_story_count_needs_the_setting_and_skips_news(self):
        assert story_clip_count({}, 8, "podcast_interview") == 0
        assert story_clip_count({"story_clips": True}, 8, "podcast_interview") == 2
        assert story_clip_count({"story_clips": True}, 40, "comedy") == 3
        assert story_clip_count({"story_clips": True}, 8, "news_politics") == 0
        assert story_clip_count({"story_clips": True}, 1, "comedy") == 0

    def test_spread_keeps_order_and_covers_the_video(self):
        blocks = [f"block {i} " + "x" * 400 for i in range(20)]
        kept = _spread(blocks, budget=1000)
        assert 1 < len(kept) < 20
        assert kept == sorted(kept, key=blocks.index)
        assert kept[0] == blocks[0] and blocks.index(kept[-1]) >= 10

    @pytest.mark.asyncio
    async def test_story_then_check_end_to_end(self):
        sentences = build_sentences(_talk(200))
        video_map = {"title": "T", "summary": "S", "category": "podcast_interview",
                     "candidates": [{"from": 10, "to": 12, "why": "q"}, {"from": 150, "to": 152, "why": "a"}]}
        director_client = _Client([{"clips": [{"segments": [{"from": 10, "to": 11}, {"from": 150, "to": 151}],
                                               "hook": 151, "title": "T", "description": "d", "hashtags": [],
                                               "layout": "auto", "beats": [], "scores": _SCORES, "why": "w"}]}])
        map_client = _Client([{"verdicts": [{"clip": 1, "ok": True, "issue": ""}, {"clip": 2, "ok": False, "issue": "x"}]}])
        director = VideoDirector(map_client, director_client)
        plans = await director.story(sentences, video_map, 2, 15.0, 60.0)
        assert "far apart" in director_client.system and "Moment 1" not in director_client.prompts[0]
        assert "Candidate 2: sentences 150-152" in director_client.prompts[0]
        clips = build_story_clips(plans, sentences, 1000.0, 15.0, 60.0, 2, "podcast_interview")
        assert len(clips) == 1
        assert await director.check([clips[0]["transcript_excerpt"], "other"]) == [True, False]


class TestCutWindows:
    def _request(self, spans, hook=None):
        return CutRequest(source_path="x.mp4", output_dir=Path("."), clip_id="c", start=spans[0][0], end=spans[-1][1],
                          aspect_ratios=["9:16"], spans=spans, hook=hook)

    def test_jump_cut_gaps_are_bridged_into_one_window(self):
        assert self._request([(10.0, 14.0), (14.6, 20.0), (21.0, 30.0)]).windows == [(10.0, 30.0)]

    def test_story_pieces_are_sampled_apart(self):
        request = self._request([(10.0, 20.0), (900.0, 915.0)], hook=Hook(905.0, 908.0))
        assert request.windows == [(10.0, 20.0), (900.0, 915.0)]
        from video_processor.clip_cutter import _tracking_timestamps

        stamps = _tracking_timestamps(request)
        assert all(10.0 <= t <= 20.0 or 900.0 <= t <= 915.0 for t in stamps)
        assert len(stamps) < 120
