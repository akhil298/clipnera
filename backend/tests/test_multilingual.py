from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from content_intelligence.edit_plan import _tighten
from transcription import groq_whisper
from transcription.groq_whisper import dominant_language, group_words
from transcription.language import (
    is_hesitation,
    normalize_language,
    romanize_word,
    script_of,
    spoken_hindi_misread_as_urdu,
)
from transcription.transliterate import romanize_transcript, wants_roman


class TestLanguage:
    @pytest.mark.parametrize(("value", "code"), [("English", "en"), ("hindi", "hi"), ("te", "te"), ("", ""), ("klingon", "")])
    def test_normalize(self, value, code):
        assert normalize_language(value) == code

    def test_urdu_is_retried_as_hindi(self):
        assert spoken_hindi_misread_as_urdu("ur") and not spoken_hindi_misread_as_urdu("hi")

    @pytest.mark.parametrize(("text", "script"), [
        ("hello world", "latin"), ("क्या हाल है", "devanagari"), ("ఎలా ఉన్నావు", "telugu"),
        ("meeting లో ఉన్నాను", "telugu"), ("", "latin"),
    ])
    def test_script(self, text, script):
        assert script_of(text) == script

    @pytest.mark.parametrize("word", ["um", "Umm,", "हम्म", "హ్మ్"])
    def test_hesitations(self, word):
        assert is_hesitation(word)

    @pytest.mark.parametrize("word", ["matlab", "ante", "basically", "so"])
    def test_meaningful_words_are_not_hesitations(self, word):
        assert not is_hesitation(word)


class TestRomanize:
    @pytest.mark.parametrize(("native", "roman"), [
        ("क्या", "kya"), ("हाल", "haal"), ("है", "hai"), ("मैं", "main"), ("ठीक", "theek"),
        ("भी", "bhi"), ("ज़िंदगी", "zindagi"), ("अंदर", "andar"), ("कमल", "kamal"), ("न", "na"),
        ("నేను", "nenu"), ("తెలుగు", "telugu"), ("అందరం", "andaram"), ("మీటింగ్", "meeting"),
    ])
    def test_common_words(self, native, roman):
        assert romanize_word(native) == roman

    def test_latin_words_are_untouched(self):
        assert romanize_word("Meeting") == "Meeting"


class TestGroqWhisper:
    def test_danda_ends_a_segment(self):
        words = [{"start": i, "end": i + 0.5, "word": w} for i, w in enumerate(
            ["यह", "एक", "बहुत", "अच्छा", "दिन", "था", "सच", "में।", "फिर", "हम", "गए"])]
        segments = group_words(words)
        assert segments[0]["text"].endswith("में।") and segments[1]["words"][0]["word"] == "फिर"

    def test_dominant_language_counts_words(self):
        assert dominant_language([([{}] * 3, "hi"), ([{}] * 9, "te")], None) == "te"
        assert dominant_language([], "Hindi") == "hi"
        assert dominant_language([], None) == "en"

    @pytest.mark.asyncio
    async def test_urdu_chunks_are_retranscribed_as_hindi(self, monkeypatch, tmp_path):
        calls = []

        async def encode(audio_path, start, length, out):
            return out

        async def transcribe_chunk(self, path, offset, length, language, prompt=None):
            calls.append(language)
            return [{"start": 0.0, "end": 1.0, "word": "नमस्ते"}], "ur" if language is None else "hi"

        monkeypatch.setattr(groq_whisper, "_encode_chunk", encode)
        monkeypatch.setattr(groq_whisper.GroqWhisperTranscriber, "_transcribe_chunk", transcribe_chunk)
        transcriber = groq_whisper.GroqWhisperTranscriber.__new__(groq_whisper.GroqWhisperTranscriber)
        segments, language = await transcriber.transcribe("a.wav", 30.0)
        assert calls == [None, "hi"] and language == "hi"


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.batches = reply, error, []

    async def chat(self, messages, **kwargs):
        batch = json.loads(messages[-1]["content"].split("\n\n", 1)[1])
        self.batches.append(batch)
        if self.error:
            raise self.error
        return json.dumps({"words": self.reply(batch)})


def segment(*words):
    return SimpleNamespace(text=" ".join(words), words=[{"start": i, "end": i + 1, "word": w} for i, w in enumerate(words)])


class TestTransliterate:
    def test_auto_romanizes_only_indic_speech(self):
        assert wants_roman("auto", [segment("क्या", "हाल")])
        assert not wants_roman("auto", [segment("hello")])
        assert not wants_roman("native", [segment("क्या")])
        assert wants_roman("roman", [segment("hello")])
        assert wants_roman(None, [segment("నేను")])

    @pytest.mark.asyncio
    async def test_llm_spellings_replace_words_and_keep_the_original(self):
        spell = {"మీటింగ్": "meeting", "నేను": "nenu", "లో": "lo"}
        seg = segment("నేను", "meeting", "మీటింగ్", "లో")
        client = FakeClient(reply=lambda batch: [spell[w] for w in batch])
        changed = await romanize_transcript([seg], client)
        assert changed == 3
        assert seg.text == "nenu meeting meeting lo"
        assert seg.words[2] == {"start": 2, "end": 3, "word": "meeting", "native": "మీటింగ్"}
        # Each distinct word is asked about once, English ones not at all.
        assert sorted(client.batches[0]) == sorted(spell)

    @pytest.mark.asyncio
    async def test_bad_llm_answers_fall_back_to_rules(self):
        seg = segment("क्या", "हाल", "है")
        answers = {"क्या": "kyaa", "हाल": "हाल", "है": "two words"}
        await romanize_transcript([seg], FakeClient(reply=lambda batch: [answers[w] for w in batch]))
        # The clean answer is used; a native-script one and a two-word one fall back to the rules.
        assert seg.text == "kyaa haal hai"

    @pytest.mark.asyncio
    async def test_a_failed_call_never_fails_the_run(self):
        seg = segment("क्या", "हाल")
        await romanize_transcript([seg], FakeClient(error=RuntimeError("down")))
        assert seg.text == "kya haal"

    @pytest.mark.asyncio
    async def test_wrong_length_reply_is_rejected(self):
        seg = segment("क्या", "हाल")
        await romanize_transcript([seg], FakeClient(reply=lambda batch: ["x"]))
        assert seg.text == "kya haal"


class TestHesitationCuts:
    def test_hindi_hesitation_is_cut_from_a_span(self):
        words = [
            {"start": 0.0, "end": 0.5, "word": "तो"},
            {"start": 0.6, "end": 1.6, "word": "हम्म"},
            {"start": 2.6, "end": 3.0, "word": "सुनो"},
        ]
        spans = _tighten([(0.0, 3.0)], words)
        assert all(not (start <= 1.1 <= end) for start, end in spans)


class TestCaptionFonts:
    def _style_font(self, words, title=None):
        from subtitle_styling.ass_generator import AssGenerator

        ass = AssGenerator().build_ass(words, 0.0, 3.0, width=1080, height=1920, title=title)
        return next(line for line in ass.splitlines() if line.startswith("Style: Caption,")).split(",")[1]

    def test_telugu_and_hindi_captions_use_noto(self):
        assert self._style_font([{"start": 0.0, "end": 1.0, "text": "నేను"}]) == "Noto Sans Telugu"
        assert self._style_font([{"start": 0.0, "end": 1.0, "text": "नमस्ते"}]) == "Noto Sans Devanagari"

    def test_roman_captions_keep_the_style_font(self):
        from subtitle_styling.templates import get_template

        assert self._style_font([{"start": 0.0, "end": 1.0, "text": "nenu"}]) == get_template("default")["font_family"]

    def test_bundled_fonts_exist(self):
        from subtitle_styling.ass_generator import FONTS_DIR

        assert (FONTS_DIR / "NotoSansTelugu-Bold.ttf").is_file() and (FONTS_DIR / "NotoSansDevanagari-Bold.ttf").is_file()


class TestCaptionScriptSetting:
    @pytest.mark.parametrize(("requested", "kept"), [("roman", "roman"), ("native", "native"), ("klingon", "auto"), (None, "auto")])
    def test_unknown_values_become_auto(self, monkeypatch, requested, kept):
        import pipeline.service as pipeline_service

        monkeypatch.setattr(pipeline_service, "require_caption_style", lambda *_: None)
        entitlements = SimpleNamespace(max_clips_per_video=5)
        settings = pipeline_service._clamp_clip_settings(entitlements, {"caption_script": requested})
        assert settings["caption_script"] == kept


class TestSmartCuts:
    def test_a_short_um_is_still_cut_at_its_edges(self):
        words = [
            {"start": 0.0, "end": 0.8, "word": "So"},
            {"start": 0.85, "end": 1.15, "word": "um"},
            {"start": 1.2, "end": 1.8, "word": "listen"},
        ]
        spans = _tighten([(0.0, 1.8)], words)
        assert spans == [(0.0, 0.85), (1.15, 1.8)]

    def test_breaths_under_half_a_second_are_kept(self):
        words = [{"start": 0.0, "end": 1.0, "word": "one"}, {"start": 1.4, "end": 2.0, "word": "two"}]
        assert _tighten([(0.0, 2.0)], words) == [(0.0, 2.0)]

    def test_dead_air_is_cut_with_breath_either_side(self):
        words = [{"start": 0.0, "end": 1.0, "word": "one"}, {"start": 2.0, "end": 2.5, "word": "two"}]
        assert _tighten([(0.0, 2.5)], words) == [(0.0, 1.12), (1.88, 2.5)]

    def test_no_cut_ever_lands_inside_a_word(self):
        import random

        rng = random.Random(7)
        for _ in range(200):
            t, words = 0.0, []
            for _ in range(rng.randint(2, 12)):
                t += rng.uniform(0.0, 1.2)
                length = rng.uniform(0.1, 0.7)
                words.append({"start": t, "end": t + length, "word": rng.choice(["word", "um", "हम्म", "nenu"])})
                t += length
            spans = _tighten([(0.0, t)], words)
            kept = [w for w in words if not is_hesitation(w["word"])]
            for a, b in spans:
                for w in kept:
                    assert not (w["start"] < a < w["end"]) and not (w["start"] < b < w["end"]), (a, b, w)


class TestWordTimings:
    def test_a_word_stretched_over_silence_is_trimmed(self):
        from transcription.word_timing import clean_word_timings, plausible_length

        words = clean_word_timings([{"start": 0.0, "end": 4.0, "word": "so"}, {"start": 4.0, "end": 4.3, "word": "yes"}])
        assert words[0]["end"] == round(plausible_length("so"), 3) and words[1]["start"] == 4.0

    def test_overlaps_trim_the_earlier_word(self):
        from transcription.word_timing import clean_word_timings

        words = clean_word_timings([{"start": 0.0, "end": 1.0, "word": "hello"}, {"start": 0.8, "end": 1.2, "word": "there"}])
        assert words[0]["end"] == 0.8 and words[1]["start"] == 0.8

    def test_zero_length_words_get_a_few_frames(self):
        from transcription.word_timing import MIN_WORD_SECONDS, clean_word_timings

        words = clean_word_timings([{"start": 1.0, "end": 1.0, "word": "a"}])
        assert words[0]["end"] - words[0]["start"] == pytest.approx(MIN_WORD_SECONDS)

    def test_output_is_ordered_and_never_overlaps(self):
        import random

        from transcription.word_timing import clean_word_timings

        rng = random.Random(3)
        for _ in range(100):
            raw = [{"start": s, "end": s + rng.uniform(-0.2, 3.0), "word": "w" * rng.randint(1, 9)}
                   for s in (rng.uniform(0, 30) for _ in range(20))]
            out = clean_word_timings(raw)
            assert all(w["end"] > w["start"] for w in out)
            assert all(b["start"] >= a["end"] for a, b in zip(out, out[1:]))

    @pytest.mark.asyncio
    async def test_title_reaches_groq_as_the_prompt(self, monkeypatch):
        seen = {}

        class Audio:
            class transcriptions:
                @staticmethod
                async def create(**kwargs):
                    seen.update(kwargs)
                    return SimpleNamespace(model_dump=lambda: {"words": [], "language": "english"})

        async def record(*args, **kwargs):
            return None

        monkeypatch.setattr(groq_whisper, "record_llm_call", record)
        transcriber = groq_whisper.GroqWhisperTranscriber.__new__(groq_whisper.GroqWhisperTranscriber)
        transcriber.model, transcriber._client = "whisper", SimpleNamespace(audio=Audio)
        from pathlib import Path
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            await transcriber._transcribe_chunk(Path(f.name), 0.0, 10.0, None, "Alex Hormozi on $100M Leads")
        assert seen["prompt"] == "Alex Hormozi on $100M Leads"
