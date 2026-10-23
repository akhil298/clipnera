"""Direct: one vision call that turns everything the understanding agents found into the story of the reel.

The director sees the contact sheets, every word (fillers and earlier takes marked by the clean pass),
the shots and the recipe library, and returns: the recipe, the hook options, the story as clips
(word ranges when someone talks, source seconds when the picture carries it), the sections, the
graphic beats anchored to words or moments, the caption keywords, the music plan and spelling fixes.
Code then validates every value (compile.py); the model never writes a frame time it can't back up.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.ai import vision_json
from reel_engine.effects import DEffect
from reel_engine.effects import prompt as effects_prompt
from reel_engine.plan import AudioReport, Shot, Source, Word

log = get_logger(__name__)

RECIPES = json.loads((Path(__file__).parent / "data" / "recipes.json").read_text())
BEAT_KINDS = ("two", "tag", "list", "count_up", "keyword", "statement", "chart", "flow", "name")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DClip(_M):
    src: int
    start: float
    end: float
    w0: int
    w1: int
    role: Literal["hook", "montage", "step", "body", "payoff", "cta"]
    section: int
    zoom: Literal["in", "out", "punch", "hold"]
    money: bool
    sound: Literal["none", "sizzle", "chop", "sparkle", "whoosh", "pop", "pour"]
    what: str


class DBeat(_M):
    kind: Literal["two", "tag", "list", "count_up", "keyword", "statement", "chart", "flow", "name"]
    w0: int
    w1: int
    src: int
    at: float
    until: float
    lead: str
    text: str
    items: list[str]
    number: str
    prefix: str
    suffix: str
    mark: Literal["none", "check", "cross"]
    trend: Literal["up", "down", "none"]
    icon: str
    why: str


class DInsert(_M):
    kind: Literal["broll", "photo", "footage"]
    w0: int
    w1: int
    src: int
    at: float
    query: str
    label: str
    why: str


class DHook(_M):
    clip: DClip
    word: str
    why: str


class DSection(_M):
    lead: str
    text: str
    short: str
    icon: str


class DFix(_M):
    id: int
    word: str


class DirectorPlan(_M):
    audio_view: Literal["voice", "song", "voice_song", "silent"]
    recipe: str
    target_seconds: float
    title_lead: str
    title_text: str
    cta: str
    caption_mode: Literal["every_word", "keyword", "none"]
    burned_captions: bool
    music: Literal["bed", "score", "none"]
    text_style: Literal["punch", "editorial", "neon", "highlight", "bubble", "script", "comic", "minimal"]
    mood: Literal["upbeat", "energetic", "chill", "lofi", "cinematic", "inspiring", "dramatic", "corporate", "funny", "urban"]
    sections: list[DSection]
    hooks: list[DHook]
    story: list[DClip]
    beats: list[DBeat]
    inserts: list[DInsert]
    keywords: list[int]
    drop_word: int
    spelling: list[DFix]
    effects: list[DEffect]
    notes: str


SYSTEM = """You are the senior editor of a premium short-form studio. From raw footage you plan a vertical reel
that matches the best $120 human edits: ten layers - selection, hook, story, picture, rhythm, captions, motion
graphics, depth, sound, finish. Code renders exactly what you plan, so every number must come from what you see
and read. Return JSON only.

RECIPES (pick the one that fits; its notes are the house style):
{recipes}

AUDIO: the listen agent measured the audio as "{audio_kind}" ({audio_why}). Set audio_view to your own judgement
from the words and frames. If someone talks (voice or voice_song), the voice is the spine: never cut inside a word,
never speed it up, keep sentences whole; the original music under a voice is replaced. If it is a song or silence,
the original audio is discarded and the picture carries the edit: speeds are free.

STORY (story: the clips in output order):
- target_seconds: {target}. Hook first (1.5-3 s): the strongest claim, line or payoff visual. Then the body in a
  clear shape (setup -> steps/points -> payoff -> CTA). Drop everything weak, repeated, off-topic or blurry.
- Talking: each clip is a word range w0..w1 (whole sentences or clauses, inclusive word ids), with start/end = -1.
  Skip words marked ~ (fillers) and lines marked [take] (an earlier take that is said again later). You may
  reorder sentences only when the meaning survives (e.g. move the best line up as the hook).
- Picture only: each clip is src + start/end in source seconds (1-4 s each, w0 = w1 = -1). Repetitive work gets
  the long range (code speeds it up); money shots (the pour, the flip, the reveal, a reaction) get money = true and
  a short range (code slows them down).
- zoom: alternate "in" and "out" clip to clip; "punch" on hooks, section starts and key lines; "hold" for wide context.
- role: hook | montage (0.5 s flashes from across the video, picture-only reels; for these, what = ONE word naming
  what is shown) | step | body | payoff | cta.
- section: index into sections for step clips, else -1. sound: foley the picture calls for (sizzle when food hits
  a hot pan, chop on knife work, pour, sparkle on a beauty shot), else none.

HOOKS: give 3 hook options (different moments or lines); code picks the best and puts it first. hook word = one
English word to set huge behind the person over the hook.

SECTIONS: 0-5 chapters (recipe steps, points of an argument): lead (1-3 small words) + text (1-2 words) + short
(<= 8 chars, for a progress bar) + icon (search words for a 3D icon, e.g. "fried egg").

GRAPHICS (beats): about one every {graphic_every} s of output, never two at once. Choose the kind by the
sentence's SHAPE, not by keyword spotting:
- a number said -> count_up (number, prefix like "$" or "₹", suffix like "%" or "k", text = what it counts)
- a list said ("X, Y and Z", "first... second...") -> list (items said, mark "check"; a "not X, not Y" list -> mark "cross")
- a change or trend -> chart (trend up/down, text = what changes)
- a process or sequence -> flow (items)
- the reveal / turning point line -> keyword (text = 1-2 words, shown huge)
- a claim worth a full card -> statement (text <= 7 words)
- a person named -> name (text = name, lead = who they are)
- a thing, place or ingredient named or shown -> tag (text = its name, icon = search words)
- an action or money shot -> two (lead = 1-3 small words, text = 1-2 word keyword, icon = search words)
Anchor talking beats to word ids w0..w1 (the words that say it; at = until = -1, src = -1). Anchor picture beats
to src + at..until source seconds (w0 = w1 = -1). Every text must match what is said or clearly visible then.

INSERTS (what the viewer SEES while someone talks; premium edits cut away every few seconds): when a person
talks, add an insert about every 4-7 s of output on the words that name something showable - a place, object,
food, product, animal, event, person's work, a number made visual. kind "photo" or "broll" (a short video; public-
domain video exists mainly for space, science, nature, cities' landmarks and history - ask for a photo for
everyday things like food, products, gadgets or people's activities) with
query = 3-6 concrete English search words for a real photo or clip (e.g. "international space station exterior
earth", "fresh croissants bakery tray"); label = 0-3 words to print on a photo card, or "". kind "footage" = a
moment of the user's OWN footage that shows what is said (src + at in source seconds) - only when that footage
has OTHER shots (B-roll, a different scene); a single talking take has nothing to cut to, so ask for photos then.
Anchor on word ids w0..w1 (src = -1, at = -1) or for footage give src + at too. No inserts on the hook or when
the speaker's face IS the point (a reaction, a punchline). Picture-only reels: inserts = [] (the clips are the
pictures). Never ask for logos of real brands or photos of private people.

TEXT STYLE (text_style, the look of every caption and label, like the reference editors' type systems):
punch (condensed bold amber, energy: advice, hype, sport), editorial (serif, cream and red: lifestyle, interviews,
stories, fashion), neon (glowing: tech, night, gaming, urban), highlight (black on an amber block: explainers,
tips, business), bubble (bold words on white bubbles: food, vlogs, everyday, friendly), script (marker pen: food,
travel, warm and personal), comic (bold outlined, tilted: funny, kids, reactions), minimal (clean lowercase:
beauty, premium, calm). Pick the one that fits the footage's colours and mood, not always the same.

BURNED CAPTIONS: set burned_captions = true when the footage already shows subtitles or captions burned into the
picture (text along the bottom that follows the speech); then caption_mode must be "none" - two caption tracks
read as a mistake.

CAPTIONS: caption_mode from the recipe (every_word whenever someone talks to camera or narrates, keyword only for ads and demos, none
when nobody talks). keywords = word ids shown big (nouns, numbers, punch words; about one per 3-6 words).
MUSIC: music "bed" under a voice, "score" for picture-only reels, mood to match. drop_word = id of the reveal word
(the music drops there), or -1. ACCENT stays the brand amber.
SPELLING: speech recognition mishears names, dishes and dialect. For each wrong word id give the correct spelling
as a local would type it (romanized for Indic languages).
TITLE: title_lead + title_text name the result or the idea (shown over the payoff). cta <= 34 chars, promises
nothing the video does not have. notes: two sentences on your plan."""


def sentences(words: list[Word]) -> list[tuple[int, int]]:
    """Word-id ranges of sentences: split on end punctuation or a pause of 0.6 s."""
    out, first = [], 0
    for k, word in enumerate(words):
        last = k == len(words) - 1
        gap = (words[k + 1].t0 - word.t1) if not last else 99.0
        if last or word.text.rstrip().endswith((".", "?", "!", "।")) or gap > 0.6 or words[k + 1].src != word.src:
            out.append((first, k))
            first = k + 1
    return out


def earlier_takes(words: list[Word]) -> set[int]:
    """Word ids of lines said again almost word for word in the next few lines (the clean pass drops them)."""
    from understanding.analyzers import find_retakes
    from understanding.mud import Utterance

    spans = sentences(words)
    utterances = [Utterance(id=f"u{n}", t0=words[a].t0, t1=words[b].t1, w0=a, w1=b, text=" ".join(w.text for w in words[a:b + 1]))
                  for n, (a, b) in enumerate(spans)]
    dropped = {(t.t0, t.t1) for t in find_retakes(utterances)}
    return {i for u in utterances if (u.t0, u.t1) in dropped for i in range(u.w0, u.w1 + 1)}


def word_listing(words: list[Word], takes: set[int]) -> str:
    lines = []
    for a, b in sentences(words):
        mark = " [take]" if a in takes else ""
        body = " ".join(f"{w.i}:{w.text}{'~' if w.filler else ''}" for w in words[a:b + 1])
        lines.append(f"[s{words[a].src} {words[a].t0:.1f}-{words[b].t1:.1f}]{mark} {body}")
    return "\n".join(lines)


def shot_listing(shots: list[Shot]) -> str:
    rows = []
    for s in shots:
        flags = ",".join(f for f, on in (("blurry", not s.sharp), ("dark", s.dark), ("faces", bool(s.faces)), ("moving", s.motion > 25)) if on)
        rows.append(f"{s.id} src{s.src} {s.t0:.1f}-{s.t1:.1f}s {flags}")
    return "\n".join(rows[:400])


def recipe_text() -> str:
    return "\n".join(f"- {r['id']}: {r['name']} - {r['when']}. {r['notes']}" for r in RECIPES)


async def direct(sources: list[Source], audio: AudioReport, shots: list[Shot], jpegs: list[bytes], how: str,
                 brief_text: str, target_seconds: float) -> DirectorPlan:
    takes = earlier_takes(audio.words) if audio.words else set()
    graphic_every = 2.5
    system = SYSTEM.format(recipes=recipe_text(), audio_kind=audio.kind, audio_why=audio.why,
                           target=f"{target_seconds:.0f}" if target_seconds else "30-60 (pick what holds attention)",
                           graphic_every=graphic_every)
    source_rows = "\n".join(f"src{s.index}: {s.name} {s.kind} {s.duration:.1f}s {s.width}x{s.height}{' audio' if s.has_audio else ''}"
                            for s in sources)
    user = (f"Sources:\n{source_rows}\n\nUser brief: {brief_text or '(none: make the best reel from this footage)'}\n\n"
            f"Shots:\n{shot_listing(shots)}\n\n"
            f"Words (id:word, ~ = filler, [take] = earlier take):\n{word_listing(audio.words, takes) if audio.words else '(nobody speaks)'}\n\n"
            f"Frames: {how}.\n\nPlan the reel. JSON only.")
    plan = await vision_json(system + "\n\n" + effects_prompt(), user, jpegs, DirectorPlan, max_tokens=16000)
    log.info("Director: recipe=%s audio=%s %d clips %d beats %d sections %d effects", plan.recipe, plan.audio_view,
             len(plan.story), len(plan.beats), len(plan.sections), len(plan.effects))
    return plan


def recipe(recipe_id: str) -> dict:
    return next((r for r in RECIPES if r["id"] == recipe_id), RECIPES[0])
