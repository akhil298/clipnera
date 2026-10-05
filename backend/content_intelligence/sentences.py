"""The sentence table: the compact, id-addressed transcript both AI passes read.

Every line is one sentence, addressed by an integer id so the model answers
with ids instead of copying timestamps. That is shorter in both directions and
cannot drift off a word boundary. A line reads::

    118 1412.3 B !E So I lost everything. Every dollar, in eleven days.

id, start second, speaker letter, cue flags, text. Flags are computed here from
word timings and loudness, so the model "hears" what the transcript alone
cannot tell it:

    !E  energy peak: louder than the surrounding minute
    !Q  a question
    !P  follows a long pause (a new thought usually starts here)
    !R  a loud burst with no speech right after it (laughter, applause, reaction)
    !C  continues the line before it: that line stopped mid-sentence, at a
        short pause or the word limit, so this one is not where a thought opens
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any

from content_intelligence.signals import PEAK_Z, AudioSignals
from transcription.language import CONTINUATION_WORDS, SENTENCE_TERMINALS

# A sentence ends at terminal punctuation, at a pause this long, or at this many words.
SENTENCE_PAUSE_SECONDS = 0.7
MAX_SENTENCE_WORDS = 35
LONG_PAUSE_SECONDS = 1.5
# A reaction is a loud stretch this soon after a sentence with no words in it.
REACTION_WINDOW_SECONDS = 1.5
REACTION_Z = 1.8
# A transcript is punctuated, so a line without a terminal mark really is
# unfinished, when at least this share of its lines end on one. Below it
# (a model or script that writes no full stops) punctuation says nothing.
PUNCTUATED_SHARE = 0.3

_TERMINAL = SENTENCE_TERMINALS
_CONTINUATION = CONTINUATION_WORDS


@dataclass
class Sentence:
    id: int
    start: float
    end: float
    text: str
    speaker: str = "-"
    flags: str = ""
    words: list[dict[str, Any]] = field(default_factory=list)
    # What is on screen while it is spoken, when a visual pass supplied it.
    scene: str = ""
    # The line before stopped mid-sentence and this one carries it on.
    continues: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def finished(self) -> bool:
        return self.text.rstrip().rstrip("\"')\u201d").endswith(_TERMINAL)

    @property
    def opens_mid_thought(self) -> bool:
        if self.continues:
            return True
        first = self.text.split(" ", 1)[0].strip(string.punctuation).lower()
        return first in _CONTINUATION

    def line(self) -> str:
        flags = "".join(f"!{flag}" for flag in self.flags)
        scene = f"[sees: {self.scene}]" if self.scene else ""
        return " ".join(
            part for part in (str(self.id), f"{self.start:.1f}", self.speaker, flags, scene, self.text) if part
        )


def build_sentences(segments: list[dict[str, Any]], audio: AudioSignals | None = None) -> list[Sentence]:
    words = _words(segments)
    letters: dict[str, str] = {}
    sentences: list[Sentence] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        speaker = current[0].get("speaker")
        letter = "-"
        if speaker:
            letter = letters.setdefault(speaker, string.ascii_uppercase[len(letters) % 26])
        sentences.append(Sentence(
            id=len(sentences) + 1,
            start=round(current[0]["start"], 2),
            end=round(current[-1]["end"], 2),
            text=" ".join(w["word"] for w in current),
            speaker=letter,
            words=list(current),
        ))
        current.clear()

    for word in words:
        if current:
            last = current[-1]
            pause = word["start"] - last["end"]
            if (
                last["word"].endswith(_TERMINAL)
                or pause >= SENTENCE_PAUSE_SECONDS
                or len(current) >= MAX_SENTENCE_WORDS
                or word.get("speaker") != last.get("speaker")
            ):
                flush()
        current.append(word)
    flush()

    punctuated = sum(s.finished for s in sentences) >= PUNCTUATED_SHARE * len(sentences)
    for previous, sentence in zip(sentences, sentences[1:]):
        sentence.continues = (
            punctuated and not previous.finished and sentence.speaker == previous.speaker
            and sentence.start - previous.end < LONG_PAUSE_SECONDS
        )
    for index, sentence in enumerate(sentences):
        sentence.flags = _flags(sentence, sentences[index - 1] if index else None,
                                sentences[index + 1] if index + 1 < len(sentences) else None, audio)
    return sentences


def speaker_legend(segments: list[dict[str, Any]]) -> dict[str, str]:
    """Letter -> diarization label, in order of first appearance."""
    legend: dict[str, str] = {}
    for segment in segments:
        speaker = segment.get("speaker")
        if speaker and speaker not in legend.values():
            legend[string.ascii_uppercase[len(legend) % 26]] = speaker
    return legend


def format_table(sentences: list[Sentence]) -> str:
    return "\n".join(sentence.line() for sentence in sentences)


def _flags(sentence: Sentence, previous: Sentence | None, following: Sentence | None, audio: AudioSignals | None) -> str:
    flags = ""
    if audio is not None and audio.peak_between(sentence.start, sentence.end) >= PEAK_Z:
        flags += "E"
    if sentence.text.rstrip().endswith("?"):
        flags += "Q"
    if previous is not None and sentence.start - previous.end >= LONG_PAUSE_SECONDS:
        flags += "P"
    if audio is not None:
        window_end = sentence.end + REACTION_WINDOW_SECONDS
        if following is not None:
            window_end = min(window_end, following.start)
        if window_end - sentence.end >= 0.4 and audio.peak_between(sentence.end, window_end) >= REACTION_Z:
            flags += "R"
    if sentence.continues:
        flags += "C"
    return flags


def _words(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in segments:
        speaker = segment.get("speaker")
        raw = segment.get("words") or []
        if raw:
            for w in raw:
                text = str(w.get("word", w.get("text", ""))).strip()
                if text:
                    words.append({"start": float(w.get("start", 0.0)), "end": float(w.get("end", 0.0)),
                                  "word": text, "speaker": speaker})
            continue
        # No word timings: spread the segment's words evenly across it.
        tokens = re.findall(r"\S+", str(segment.get("text", "")))
        start, end = float(segment.get("start", 0.0)), float(segment.get("end", 0.0))
        step = (end - start) / max(1, len(tokens))
        words.extend(
            {"start": start + i * step, "end": start + (i + 1) * step, "word": token, "speaker": speaker}
            for i, token in enumerate(tokens)
        )
    words.sort(key=lambda w: w["start"])
    return words
