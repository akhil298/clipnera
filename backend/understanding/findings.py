"""What the AI found in one asset, in the few numbers and lines the studio's chat shows.

Built from the MUD with no model call, and stored on the analysis row so the chat never has to
load the document.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from understanding.mud import MUD

MOMENTS_SHOWN = 3
QUOTE_CHARS = 120
SUGGESTIONS_SHOWN = 3
# Below this many words there is too little speech to cut or caption by.
SPOKEN_WORDS = 30
TIGHTEN_FROM_SECONDS = 3.0
QUALITY_FROM_SECONDS = 2.0
QUALITY_STYLE_SHARE = 0.5
ANALYZER_PROBLEMS = {
    "transcript": "I couldn't make out the speech, so I can't cut by what is said.",
    "reading": "I couldn't judge which lines are the strongest, so my pick of moments is rough.",
    "audio": "I couldn't read the sound.",
    "shots": "I couldn't split the picture into shots.",
    "music": "I couldn't find the beat.",
}
QUALITY_NAMES = {"blur": "out of focus", "dark": "too dark", "bright": "overexposed", "fast_motion": "shaky or very fast"}


class FoundMoment(BaseModel):
    t0: float
    t1: float
    # What is said in it, or why it stood out when nothing is.
    text: str


class AnalysisFindings(BaseModel):
    kind: Literal["video", "image", "audio"]
    duration: float
    # What it is about, in a sentence, and the topics in order.
    summary: str | None = None
    topics: list[str] = Field(default_factory=list)
    language: str | None = None
    words: int = 0
    fillers: int = 0
    # Seconds of silence long enough to cut.
    dead_air: float = 0.0
    shots: int = 0
    tempo_bpm: float | None = None
    moments: list[FoundMoment] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    # Prompts the chat offers as one-click next steps.
    suggestions: list[str] = Field(default_factory=list)


def findings_of(mud: MUD) -> AnalysisFindings:
    found = AnalysisFindings(
        kind=mud.kind, duration=mud.duration, summary=mud.summary, topics=mud.topics, language=mud.language,
        words=len(mud.words),
        fillers=sum(1 for word in mud.words if word.filler),
        dead_air=round(sum(s.t1 - s.t0 for s in mud.silences if s.kind == "dead_air"), 1),
        shots=len(mud.shots), tempo_bpm=mud.music.tempo_bpm if mud.music else None,
        moments=[FoundMoment(t0=m.t0, t1=m.t1, text=_said(mud, m.t0, m.t1) or m.why)
                 for m in sorted(mud.moments, key=lambda m: -m.score)[:MOMENTS_SHOWN]],
        problems=_problems(mud),
    )
    found.suggestions = _suggestions(found)
    return found


def _said(mud: MUD, t0: float, t1: float) -> str:
    text = " ".join(u.text for u in mud.utterances if u.t1 > t0 and u.t0 < t1).strip()
    return text if len(text) <= QUOTE_CHARS else f"{text[:QUOTE_CHARS].rsplit(' ', 1)[0]}…"


def _problems(mud: MUD) -> list[str]:
    problems = [text for name, text in ANALYZER_PROBLEMS.items() if mud.analyzers.get(name) == "failed"]
    for flag, name in QUALITY_NAMES.items():
        seconds = sum(q.t1 - q.t0 for q in mud.quality if q.flag == flag)
        # Over most of the recording it is how it was shot (handheld, a dim room), not a patch to warn about.
        if QUALITY_FROM_SECONDS <= seconds < QUALITY_STYLE_SHARE * mud.duration:
            problems.append(f"About {round(seconds)}s is {name}.")
    return problems


def _suggestions(found: AnalysisFindings) -> list[str]:
    if found.kind == "image":
        return []
    if found.kind == "audio":
        return ["Cut my clips to the beat of this song"] if found.tempo_bpm else []
    spoken = found.words >= SPOKEN_WORDS
    # The whole video comes first: this is an editor, and a cut-down is one thing among several.
    options = [
        (spoken, "Edit the full video"),
        (spoken and (found.dead_air >= TIGHTEN_FROM_SECONDS or found.fillers > 0), "Cut the dead air and filler words"),
        (spoken, "Add captions"),
        (spoken, "Make it more dynamic, with zooms and sound"),
        (not spoken, "Edit the full video to music"),
    ]
    return [text for wanted, text in options if wanted][:SUGGESTIONS_SHOWN]
