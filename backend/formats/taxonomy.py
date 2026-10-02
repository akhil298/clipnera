"""The short-form formats Clipnera cuts, and the recipe each one is edited with.

A format is decided by AI from the content, never picked by the user: the
visual probe (:mod:`formats.visual_probe`) measures what is on screen, the Map
and Director passes choose a format per video and per clip from that evidence
and the transcript, and :func:`resolve_format` refuses any choice the picture
cannot support. Everything downstream (framing, pacing, overlays, B-roll)
reads the clip's :class:`Recipe`, so adding a format means adding one entry
here and, if it needs one, a layout in ``video_processor.editing``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ContentFormat = Literal[
    "talking_head", "yap", "split_screen", "green_screen", "voice_over", "broll",
    "listicle", "ranking", "reaction", "screen_share", "clone",
]

FORMATS: tuple[str, ...] = (
    "talking_head", "yap", "split_screen", "green_screen", "voice_over", "broll",
    "listicle", "ranking", "reaction", "screen_share", "clone",
)
DEFAULT_FORMAT = "talking_head"

# Layouts the cutter understands (video_processor.editing.choose_layout).
# "follow" is the always-safe crop on whoever is talking.
CutLayout = Literal[
    "follow", "two_speaker_stack", "split_gameplay", "screen_with_speaker",
    "reaction_stack", "screen_focus", "green_screen", "voice_over", "clone_stack",
]
Overlay = Literal["none", "list_counter", "rank_board"]
BrollDensity = Literal["off", "light", "heavy"]


@dataclass(frozen=True)
class Recipe:
    format: str
    label: str
    # What the format looks and sounds like, for the AI prompts.
    describe: str
    # How the director should cut a clip of this format.
    playbook: str
    layout: str = "follow"
    # Silences longer than this are cut out of the body (edit_plan jump cuts).
    jump_cut_min_pause: float = 0.5
    # Alternate wide and tight framing on sentence starts (editing._rhythm).
    rhythm: bool = True
    broll: str = "off"
    overlay: str = "none"
    # Evidence the picture must show for the format to be used; see supports().
    needs: frozenset[str] = field(default_factory=frozenset)


RECIPES: dict[str, Recipe] = {r.format: r for r in (
    Recipe(
        "talking_head", "Talking head",
        "One person speaking to camera or to someone off screen; their face carries the clip.",
        "Frame the speaker tight. Keep one complete thought; cut false starts and dead air.",
        needs=frozenset({"face"}),
    ),
    Recipe(
        "yap", "Yap",
        "A creator rambling or ranting straight to camera, fast and opinionated, often selfie-style.",
        "Pace it hard: no breath between lines, punch in on every new sentence, open on the hottest take.",
        jump_cut_min_pause=0.3, needs=frozenset({"face"}),
    ),
    Recipe(
        "split_screen", "Split screen",
        "Two people on screen at once in conversation, or gameplay with a facecam.",
        "The exchange is the clip: keep both sides of the back-and-forth, question and answer.",
        layout="two_speaker_stack", rhythm=False, needs=frozenset({"two_faces_or_facecam"}),
    ),
    Recipe(
        "green_screen", "Green screen",
        "A creator in front of a green screen, or composited over an image, article, tweet or chart they talk about.",
        "Keep the graphic the creator is talking about on screen with them; open on the claim the graphic proves.",
        layout="green_screen", rhythm=False, broll="light", needs=frozenset({"green_or_graphic"}),
    ),
    Recipe(
        "voice_over", "Voice over",
        "Narration over footage; the narrator is rarely or never on screen.",
        "The words drive the clip and the footage illustrates them. Favour vivid lines that the picture shows.",
        layout="voice_over", rhythm=False, broll="heavy", needs=frozenset({"voice_without_face"}),
    ),
    Recipe(
        "broll", "B-roll",
        "A speaker whose points are illustrated with cutaway footage of what they describe.",
        "Favour concrete, visual lines (places, objects, numbers, actions) that cutaways can show.",
        broll="heavy", needs=frozenset({"face"}),
    ),
    Recipe(
        "listicle", "Listicle",
        "A numbered list of tips, reasons or facts: 'five things', 'the first...', 'number two...'.",
        "Every item is one complete line with its point. Keep the items in the order spoken; label each.",
        jump_cut_min_pause=0.35, overlay="list_counter",
    ),
    Recipe(
        "ranking", "Ranking",
        "Items ranked or rated against each other: tier lists, worst to best, top N, 'this is a 9/10'.",
        "Build to the top pick: each item with its verdict, best saved for last. Label each with its rank.",
        jump_cut_min_pause=0.35, overlay="rank_board",
    ),
    Recipe(
        "reaction", "Reaction",
        "A creator watching and reacting to another video, clip or post shown on screen with their face.",
        "Show what is being reacted to, then the reaction. The biggest reaction line is the hook.",
        layout="reaction_stack", rhythm=False, needs=frozenset({"content_with_face"}),
    ),
    Recipe(
        "screen_share", "Screen share",
        "A screen recording, slides or a demo, usually with the presenter's webcam.",
        "Favour a demo with a visible result. Keep the part of the screen being explained readable.",
        layout="screen_focus", rhythm=False, needs=frozenset({"screen"}),
    ),
    Recipe(
        "clone", "Clone",
        "One creator playing several characters who talk to each other, cut shot to shot or side by side.",
        "Keep the whole exchange between the characters, setup to punchline.",
        layout="clone_stack", rhythm=False, needs=frozenset({"same_person_twice"}),
    ),
)}


@dataclass
class VisualEvidence:
    """What the visual probe measured over a stretch of video, as 0-1 shares
    of sampled frames unless noted. Boxes are normalised ``(x, y, w, h)``."""

    start: float = 0.0
    end: float = 0.0
    face: float = 0.0
    two_faces: float = 0.0
    # A small, still face in a fixed corner: a webcam bubble or facecam.
    facecam: float = 0.0
    facecam_box: tuple[float, float, float, float] | None = None
    # The part of the frame that is not the facecam: gameplay, a screen, a reacted-to video.
    content_box: tuple[float, float, float, float] | None = None
    screen: float = 0.0
    green: float = 0.0
    # A person in front of a still graphic (a composited green screen).
    graphic_backdrop: float = 0.0
    # Share of speech during which a visible mouth moves; low means a voice over.
    lip_sync: float = 1.0
    # Share of frames where two face tracks look like the same person.
    same_person: float = 0.0
    cuts_per_minute: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return {key: (list(value) if isinstance(value, tuple) else value) for key, value in self.__dict__.items()}


# Thresholds for the evidence each format needs. Kept generous: the AI picks
# the format, and these only refuse a choice the picture plainly contradicts.
EVIDENCE_RULES: dict[str, object] = {
    "face": lambda e: e.face >= 0.35,
    "two_faces_or_facecam": lambda e: e.two_faces >= 0.3 or e.facecam >= 0.4,
    "green_or_graphic": lambda e: e.green >= 0.25 or e.graphic_backdrop >= 0.35,
    "voice_without_face": lambda e: e.face < 0.35 or e.lip_sync < 0.3,
    "content_with_face": lambda e: (e.facecam >= 0.35 or e.face >= 0.35) and e.content_box is not None,
    "screen": lambda e: e.screen >= 0.35,
    "same_person_twice": lambda e: e.same_person >= 0.3,
}


def supports(content_format: str, evidence: VisualEvidence | None) -> bool:
    """Whether the picture can carry ``content_format``. Without evidence (the
    probe failed or was skipped) only formats that need nothing pass."""
    recipe = RECIPES.get(content_format)
    if recipe is None:
        return False
    if evidence is None:
        return not recipe.needs
    return all(EVIDENCE_RULES[need](evidence) for need in recipe.needs)  # type: ignore[operator]


def visual_format(evidence: VisualEvidence | None) -> str:
    """The format the picture alone points to, used when the AI's choice is refused."""
    if evidence is None:
        return DEFAULT_FORMAT
    for candidate in ("reaction", "screen_share", "green_screen", "clone", "split_screen", "voice_over"):
        if supports(candidate, evidence) and _strong(candidate, evidence):
            return candidate
    return DEFAULT_FORMAT if supports(DEFAULT_FORMAT, evidence) else "voice_over"


def _strong(content_format: str, e: VisualEvidence) -> bool:
    """Evidence clear enough to choose a format without the AI asking for it."""
    return {
        "reaction": e.facecam >= 0.5 and e.screen < 0.5,
        "screen_share": e.screen >= 0.5,
        "green_screen": e.green >= 0.4 or e.graphic_backdrop >= 0.5,
        "clone": e.same_person >= 0.5,
        "split_screen": e.two_faces >= 0.5 or e.facecam >= 0.5,
        "voice_over": e.face < 0.2,
    }.get(content_format, False)


def resolve_format(proposed: str | None, evidence: VisualEvidence | None) -> tuple[str, bool]:
    """The format to cut with, and whether the AI's proposal was kept."""
    if proposed in RECIPES and supports(proposed, evidence):
        return proposed, True
    return visual_format(evidence), False


def recipe_for(content_format: str | None) -> Recipe:
    return RECIPES.get(content_format or "", RECIPES[DEFAULT_FORMAT])


def merge_evidence(windows: list[VisualEvidence], start: float, end: float) -> VisualEvidence | None:
    """Evidence over ``[start, end)``, weighting each probe window by its overlap."""
    weighted = [(w, min(end, w.end) - max(start, w.start)) for w in windows]
    weighted = [(w, overlap) for w, overlap in weighted if overlap > 0]
    total = sum(overlap for _, overlap in weighted)
    if not total:
        return None
    merged = VisualEvidence(start=start, end=end)
    for key in ("face", "two_faces", "facecam", "screen", "green", "graphic_backdrop", "lip_sync",
                "same_person", "cuts_per_minute"):
        setattr(merged, key, sum(getattr(w, key) * overlap for w, overlap in weighted) / total)
    by_overlap = [w for w, _ in sorted(weighted, key=lambda item: -item[1])]
    merged.facecam_box = next((w.facecam_box for w in by_overlap if w.facecam_box), None)
    merged.content_box = next((w.content_box for w in by_overlap if w.content_box), None)
    return merged


def evidence_from_dict(data: dict[str, object] | None) -> VisualEvidence | None:
    """The inverse of :meth:`VisualEvidence.as_dict`, for evidence stored as JSON."""
    if not data:
        return None
    known = {key: value for key, value in data.items() if key in VisualEvidence.__dataclass_fields__}
    for key in ("facecam_box", "content_box"):
        if known.get(key) is not None:
            known[key] = tuple(known[key])  # type: ignore[arg-type]
    return VisualEvidence(**known)  # type: ignore[arg-type]


def prompt_catalogue() -> str:
    """The formats as the AI prompts list them."""
    return "\n".join(f"- {r.format}: {r.describe}" for r in RECIPES.values())
