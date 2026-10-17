from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.exceptions import CustomException
from edit_engine import compiler, director, music, pricing, reference, script, story
from edit_engine.schema import EditCreateRequest


def words_for(text: str, src: int = 0, start: float = 0.0, gap: float = 0.4) -> list[dict]:
    return [{"src": src, "start": round(start + i * gap, 3), "end": round(start + i * gap + 0.3, 3), "word": w}
            for i, w in enumerate(text.split())]


def analysis_for(*takes: tuple[str, int, float]) -> dict:
    words = [w for text, src, start in takes for w in words_for(text, src, start)]
    sentences = story.sentences_from_words(words)
    return {
        "words": words, "sentences": sentences,
        "shots": [{"id": "v0", "src": 0, "start": 0.0, "end": 60.0, "face_x": 0.4, "faces": 1, "usable": True, "brightness": 120.0},
                  {"id": "v1", "src": 1, "start": 0.0, "end": 8.0, "face_x": None, "faces": 0, "usable": True, "brightness": 90.0}],
        "photos": [{"id": "p0", "src": 2, "description": "red running shoes"}],
        "dropped": sorted(story.dropped_takes(sentences, story.retake_groups(sentences))),
    }


class TestStory:
    def test_sentences_split_at_punctuation_and_files(self):
        words = words_for("Hello there. This is it.") + words_for("New file here.", src=1)
        sentences = story.sentences_from_words(words)
        assert [s["text"] for s in sentences] == ["Hello there.", "This is it.", "New file here."]
        assert [s["src"] for s in sentences] == [0, 0, 1]
        assert sentences[1]["w0"] == 2 and sentences[1]["w1"] == 4

    def test_long_pause_ends_a_sentence(self):
        words = words_for("one two three") + words_for("four five", start=5.0)
        assert len(story.sentences_from_words(words)) == 2

    def test_retakes_keep_the_last_complete_take(self):
        sentences = story.sentences_from_words(
            words_for("The first mistake people make is buying cheap shoes.")
            + words_for("The first mistake people make is", start=6.0)
            + words_for("The first mistake people make is buying cheap running shoes.", start=10.0)
        )
        groups = story.retake_groups(sentences)
        assert groups == [["s0", "s1", "s2"]]
        assert story.dropped_takes(sentences, groups) == {"s0", "s1"}

    def test_restart_lines_are_dropped(self):
        sentences = story.sentences_from_words(words_for("Sorry let me start again.") + words_for("Shoes matter.", start=4))
        assert story.dropped_takes(sentences, []) == {"s0"}

    def test_classify(self):
        faces = [{"start": 0, "end": 60, "faces": 1}]
        assert story.classify(50, 60, faces, has_voiceover=False) == "talking_head"
        assert story.classify(5, 60, faces, has_voiceover=False) == "montage"
        assert story.classify(40, 60, [{"start": 0, "end": 60, "faces": 0}], has_voiceover=False) == "vlog"
        assert story.classify(50, 60, faces, has_voiceover=True) == "montage"


class TestScript:
    def test_lines_split_on_sentences_and_newlines(self):
        assert script.script_lines("One. Two!\nThree") == ["One.", "Two!", "Three"]

    def test_align_prefers_the_later_equal_take_and_flags_missing_lines(self):
        a = analysis_for(("Cheap shoes hurt your knees.", 0, 0.0), ("Cheap shoes hurt your knees.", 0, 5.0),
                         ("Buy a proper pair today.", 0, 10.0))
        aligned = script.align(["Cheap shoes hurt your knees.", "Buy a proper pair today.", "Follow for more tips."],
                               a["sentences"])
        assert aligned[0]["sentences"] == ["s1"]
        assert aligned[1]["sentences"] == ["s2"]
        assert aligned[2]["sentences"] == []
        assert script.coverage(aligned) == pytest.approx(2 / 3)

    def test_mode(self):
        assert script.resolve_mode("auto", False, True, 0.0) == "none"
        assert script.resolve_mode("auto", True, False, 0.0) == "voiceover"
        assert script.resolve_mode("auto", True, True, 0.8) == "spoken"
        assert script.resolve_mode("auto", True, True, 0.1) == "direction"
        assert script.resolve_mode("onscreen", True, True, 0.9) == "onscreen"

    def test_unscripted(self):
        a = analysis_for(("Hello everyone.", 0, 0.0), ("Shoes matter a lot.", 0, 3.0))
        aligned = script.align(["Shoes matter a lot."], a["sentences"])
        assert script.unscripted(aligned, a["sentences"], set()) == ["s0"]


class TestCompiler:
    size = (720, 1280)

    def test_talking_head_cuts_fillers_and_pauses_and_maps_captions(self):
        words = words_for("So um this matters") + words_for("a lot.", start=2.0)
        a = {**analysis_for(), "words": words, "sentences": story.sentences_from_words(words)}
        plan = {"mode": "none", "sentences": ["s0"], "hook": "Listen up"}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=45)
        assert [w["word"] for w in t["words"]] == ["So", "this", "matters", "a", "lot."]
        # The gap left by "um" and the 0.5 s pause before "a" are cut: three pieces, back to back.
        assert len(t["voice"]) == 3
        for first, second in zip(t["voice"], t["voice"][1:]):
            assert second["at"] == pytest.approx(first["at"] + first["out"] - first["in"], abs=1e-3)
        # Each jump cut within one file changes the framing.
        assert [p["zoom"] for p in t["picture"]] == [1.0, compiler.JUMP_ZOOM, 1.0]
        assert t["texts"][0] == {"kind": "hook", "text": "Listen up", "at": 0.0, "dur": pytest.approx(compiler.HOOK_SECONDS)}
        assert t["picture"][0]["crop_x"] == 0.4

    def test_spoken_script_order_and_missing_line_card(self):
        a = analysis_for(("Buy a proper pair.", 0, 0.0), ("Cheap shoes hurt.", 0, 4.0))
        plan = {"mode": "spoken", "script_lines": [
            {"text": "Cheap shoes hurt.", "sentences": ["s1"]},
            {"text": "Here is why.", "sentences": []},
            {"text": "Buy a proper pair.", "sentences": ["s0"]}]}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=45)
        kinds = [p["kind"] for p in t["picture"]]
        assert kinds == ["video", "card", "video"]
        assert t["picture"][1]["text"] == "Here is why."
        assert t["words"][0]["word"] == "Cheap"

    def test_user_removed_and_restored_sentences(self):
        a = analysis_for(("One two three.", 0, 0.0), ("Four five six.", 0, 3.0), ("Seven eight nine.", 0, 6.0))
        plan = {"mode": "none", "sentences": ["s0", "s2"], "restored": ["s1"], "removed": ["s0"]}
        assert compiler.kept_sentences(a, plan) == ["s1", "s2"]

    def test_broll_never_covers_the_hook_and_splits_the_picture(self):
        a = analysis_for(("Running every day changed my whole life for real.", 0, 0.0),
                         ("These shoes are the reason I kept going every morning.", 0, 5.0))
        plan = {"mode": "none", "sentences": ["s0", "s1"], "broll": [{"sentence": "s0", "visual": "v1"},
                                                                    {"sentence": "s1", "visual": "p0"}]}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=45)
        covers = [p for p in t["picture"] if p.get("broll") or p["kind"] == "image"]
        assert covers and all(p["at"] >= compiler.BROLL_NOT_BEFORE for p in covers)
        # The picture still tiles the reel with no gaps or overlaps.
        ends = [p["at"] + compiler._length(p) for p in t["picture"]]
        assert all(abs(e - n["at"]) < 1e-2 for e, n in zip(ends, t["picture"][1:]))
        assert any(c["sound"] == "whoosh" for c in t["sfx"])

    def test_target_length_stops_after_a_whole_sentence(self):
        a = analysis_for(*[(f"Sentence number {i} is here.", 0, i * 3.0) for i in range(10)])
        plan = {"mode": "none", "sentences": [s["id"] for s in a["sentences"]]}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=5, max_seconds=45)
        assert 5 <= t["duration"] < 9

    def test_max_length_is_a_hard_cap(self):
        a = analysis_for(*[(f"Sentence number {i} is here.", 0, i * 3.0) for i in range(10)])
        plan = {"mode": "spoken", "script_lines": [{"text": s["text"], "sentences": [s["id"]]} for s in a["sentences"]]}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=6)
        assert t["duration"] == 6
        assert max(p["at"] + compiler._length(p) for p in t["picture"]) <= 6.001

    def test_montage_cuts_on_the_beat(self):
        a = {"sentences": [], "words": [], "shots": [
            {"id": f"v{i}", "src": 0, "start": i * 5.0, "end": i * 5.0 + 5.0, "usable": True} for i in range(8)], "photos": []}
        plan = {"mode": "none", "montage": [f"v{i}" for i in range(8)], "energy": "high",
                "music": {"track_id": "m1", "bpm": 120}}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=6, max_seconds=45)
        assert t["layout"] == "montage"
        # 120 bpm at high energy: two beats, one second, per shot.
        assert [compiler._length(p) for p in t["picture"]] == [1.0] * 6
        assert t["duration"] == pytest.approx(6.0)
        assert t["music"] == {"track_id": "m1", "offset": 0.0, "gain_db": compiler.MUSIC_ALONE_DB, "duck": False}

    def test_voiceover_gives_every_sentence_a_visual(self):
        voice_words = words_for("Morning runs are magic. Here is my route.")
        a = {"sentences": [], "words": [], "voice_words": voice_words,
             "voice_sentences": story.sentences_from_words(voice_words), "voiceover_src": 3,
             "shots": [{"id": "v0", "src": 0, "start": 0.0, "end": 1.0, "usable": True}],
             "photos": [{"id": "p0", "src": 2}]}
        plan = {"mode": "voiceover", "broll": [{"sentence": "s1", "visual": "p0"}], "music": {"track_id": "m1"}}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=45)
        assert t["voiceover"] == {"src": 3}
        assert t["picture"][0]["kind"] == "video" and t["picture"][-1]["kind"] == "image"
        assert t["music"]["duck"] is True

    def test_onscreen_script_replaces_captions(self):
        a = analysis_for(("Talking about shoes for a while now okay.", 0, 0.0))
        plan = {"mode": "onscreen", "sentences": ["s0"], "script_lines": [{"text": "Line one", "sentences": []}]}
        t = compiler.compile_timeline(a, plan, size=self.size, target_seconds=0, max_seconds=45)
        assert t["words"] == [] and any(x["kind"] == "line" for x in t["texts"])

    def test_sfx_are_spaced(self):
        cues = [{"sound": "pop", "at": 1.0}, {"sound": "pop", "at": 1.5}, {"sound": "hit", "at": 3.0}]
        assert [c["at"] for c in compiler._space_sfx(cues)] == [1.0, 3.0]


class TestDirector:
    def test_validate_drops_unknown_ids_and_fills_gaps(self):
        a = analysis_for(("Hello there friends.", 0, 0.0), ("Shoes matter.", 0, 3.0))
        raw = {"sentences": ["s1", "s9", "s1"], "broll": [{"sentence": "s1", "visual": "v1"}, {"sentence": "s1", "visual": "p0"},
                                                          {"sentence": "s0", "visual": "v7"}],
               "pops": [{"sentence": "s1", "text": "two words only please"}], "look": "neon", "music_mood": "chill",
               "hook": "one two three four five six seven", "hashtags": ["running", "#shoes tips"]}
        plan = director.validate(raw, a, "none")
        assert plan["sentences"] == ["s1"]
        assert plan["broll"] == [{"sentence": "s1", "visual": "v1"}]
        assert plan["pops"] == [{"sentence": "s1", "text": "two words only"}]
        assert plan["look"] == "natural"
        assert plan["hook"] == "one two three four five six"
        assert plan["hashtags"] == ["#running", "#shoestips"]

    def test_fallback_plan_keeps_good_takes(self):
        a = analysis_for(("Sorry let me start again.", 0, 0.0), ("Shoes matter.", 0, 3.0))
        assert director.fallback_plan(a, "none")["sentences"] == ["s1"]
        assert director.validate({}, a, "none")["sentences"] == ["s1"]

    def test_footage_log_marks_fixed_scripts_and_weak_takes(self):
        a = {**analysis_for(("Sorry let me start again.", 0, 0.0), ("Shoes matter.", 0, 3.0)), "content_type": "talking_head"}
        text = director.footage_log(a, "spoken", "Shoes matter.", "funny", 30, 45, fixed=["s1"])
        assert "SCRIPT: FIXED" in text and "[weaker take or restart]" in text and "CREATOR'S INTENT: funny" in text

    def test_footage_log_describes_the_reference_reel(self):
        style = {"duration_s": 28.0, "shots": 14, "seconds_per_shot": 2.0, "energy": "high", "style": "Yellow word-by-word captions."}
        a = {**analysis_for(("Shoes matter.", 0, 0.0)), "reference": style}
        text = director.footage_log(a, "none", None, None, 0, 45)
        assert "REFERENCE REEL: 28 s, 14 shots (a cut every 2.0 s), high energy. Style: Yellow word-by-word captions." in text
        assert "REFERENCE REEL" not in director.footage_log(analysis_for(("Shoes matter.", 0, 0.0)), "none", None, None, 0, 45)


class TestReference:
    def test_energy_follows_the_cut_rate(self):
        assert [reference._energy(s) for s in (0.8, 2.5, 5.0)] == ["high", "medium", "low"]

    def test_only_youtube_links_and_web_urls(self):
        assert reference.is_supported_link("https://youtube.com/shorts/abcdefghijk")
        assert not reference.is_supported_link("https://www.instagram.com/reel/abc/")
        with pytest.raises(ValueError):
            EditCreateRequest(reference_url="javascript:alert(1)")


class TestPricing:
    def test_reel_credits(self):
        assert pricing.reel_credits(45, 300) == 26
        assert pricing.reel_credits(30, 180) == 19  # fits Free's 20 monthly credits
        assert pricing.reel_credits(45, 300, opus=True) == 39
        assert pricing.rerender_credits(26) == 7


class TestMusic:
    def test_licence_allowlist(self):
        assert music.validate_licence("CC0", True, True, "") == music.ALLOWED_LICENCES["CC0"][0]
        with pytest.raises(CustomException):
            music.validate_licence("CC-BY-NC-4.0", True, True, "credit")
        with pytest.raises(CustomException):
            music.validate_licence("CC-BY-4.0", True, True, "")
        with pytest.raises(CustomException):
            music.validate_licence("CC0", False, True, "")

    def test_pick_track_prefers_mood_then_energy(self):
        tracks = [SimpleNamespace(id="a", mood="chill", energy=0.2), SimpleNamespace(id="b", mood="chill", energy=0.9),
                  SimpleNamespace(id="c", mood="upbeat", energy=0.8)]
        assert music.pick_track(tracks, "chill", "high", "x").id == "b"
        assert music.pick_track(tracks, "funny", "high", "x").id in {"b", "c"}
        assert music.pick_track([], "chill", "low", "x") is None
