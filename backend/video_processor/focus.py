"""What the viewer should look at during a stretch of a clip.

Faces alone decide nothing here. A streamer reacting to fan art is about the
art; two people in a cam over a screen share are the reaction, not the story.
For each stretch the focus is one of:

* ``people``: framing follows the people, as it always has;
* ``content``: the thing on screen, shown whole, nobody to show with it;
* ``content_reaction``: the thing on screen on top, the people reacting below.

Content wins only on evidence. A framed rectangle must be strong on its own
(on screen for most of the stretch, big enough, never framing one of the
people) and something must say it matters: the director asked for a screen
layout, the video is a kind that shows screens, the speaker points at it, or
it popped up during the shot the way shared media does. A poster on a studio
wall has none of these and leaves the framing alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from video_processor.regions import Region, main_content
from video_processor.speaker_tracking import SpeakerTrack

# A region must cover this share of the stretch's samples to take the frame...
CONTENT_MIN_PRESENCE = 0.6
# ...and this share of the frame.
CONTENT_MIN_AREA = 0.06
# Shown media appears after the shot starts; this much later counts as popping up.
POP_UP_SECONDS = 0.5
# Kinds of video where something on screen is routinely the subject.
SCREEN_CATEGORIES = frozenset({"reaction", "gaming", "tech", "tutorial_educational", "news_politics"})
# Words that point at something shown. "this" and "that" alone are too common to count.
POINTING_WORDS = re.compile(
    r"\b(look(ing)? at|see (this|that)|watch (this|that)|check (this|that) out|drawing|drew|draw|art|artwork|"
    r"picture|pic|photo|image|meme|video|clip|screen|read (this|that|it)|this one|that one)\b",
    re.IGNORECASE,
)
SCREEN_HINT = "screen_with_speaker"


@dataclass(frozen=True)
class Focus:
    kind: str  # people | content | content_reaction
    content: Region | None = None
    people: tuple[SpeakerTrack, ...] = field(default_factory=tuple)

    @property
    def shows_content(self) -> bool:
        return self.content is not None


PEOPLE = Focus("people")


def decide_focus(
    regions: list[Region],
    people: list[SpeakerTrack],
    start: float,
    hint: str = "auto",
    category: str = "unknown",
    spoken: str = "",
) -> Focus:
    """The focus for a stretch beginning at ``start``.

    ``regions`` are the stretch's content regions (best first), ``people`` the
    tracks there that are people on camera, ``spoken`` the words said during it.
    """
    region = main_content(regions, people)
    if region is None or not _strong(region, people):
        return PEOPLE
    reasons = _reasons(region, start, hint, category, spoken)
    if not reasons:
        return PEOPLE
    return Focus("content_reaction" if people else "content", region, tuple(people))


def _strong(region: Region, people: list[SpeakerTrack]) -> bool:
    if region.presence < CONTENT_MIN_PRESENCE or region.box.area < CONTENT_MIN_AREA:
        return False
    # A rectangle around someone on camera is their camera feed or the wall
    # behind them, not something they are showing.
    return not any(region.contains(s.face.box) for track in people for s in track.samples)


def _reasons(region: Region, start: float, hint: str, category: str, spoken: str) -> list[str]:
    reasons = []
    if hint == SCREEN_HINT:
        reasons.append("hint")
    if (category or "").lower() in SCREEN_CATEGORIES:
        reasons.append("category")
    if POINTING_WORDS.search(spoken or ""):
        reasons.append("pointing")
    if region.first_seen - start >= POP_UP_SECONDS:
        reasons.append("popped_up")
    return reasons
