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
from reel_engine import scenes, styles, typekits
from reel_engine.ai import vision_json
from reel_engine.effects import DEffect
from reel_engine.effects import prompt as effects_prompt
from reel_engine.plan import AudioReport, Shot, Source, Word
from reel_engine.scenes import DScene

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


class DDesign(_M):
    """A moment whose graphic a motion designer writes from scratch (motion_code.py) instead of a template."""

    w0: int
    w1: int
    why: str


class DInsert(_M):
    kind: Literal["broll", "photo", "footage"]
    w0: int
    w1: int
    src: int
    at: float
    query: str
    show: str
    label: str
    why: str


class DHook(_M):
    clip: DClip
    word: str
    why: str


Case = Literal["none", "uppercase", "lowercase"]


class DTextStyle(_M):
    """The reel's own type design (typekits.designed checks it; the catalogue kit stands in when it breaks a rule)."""

    lead_font: str
    lead_weight: int
    lead_case: Case
    key_font: str
    key_weight: int
    key_case: Case
    title_font: str
    title_weight: int
    title_case: Case
    treatment: Literal["block", "bubble", "comic", "glow", "gradient", "outline", "plate", "shadow", "softglow", "sticker", "tilt", "underline"]
    lead_treatment: Literal["glow", "plain", "shadow", "stroke"]
    accent: str
    alt: str
    ink: str
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
    hook_text: str
    cta: str
    caption_mode: Literal["every_word", "keyword", "none"]
    burned_captions: bool
    music: Literal["bed", "score", "none"]
    type_kit: str
    mix_kits: list[str]
    text_style: DTextStyle
    mood: Literal["upbeat", "energetic", "chill", "lofi", "cinematic", "inspiring", "dramatic", "corporate", "funny", "urban"]
    sections: list[DSection]
    hooks: list[DHook]
    story: list[DClip]
    beats: list[DBeat]
    designs: list[DDesign]
    inserts: list[DInsert]
    scenes: list[DScene]
    keywords: list[int]
    drop_word: int
    spelling: list[DFix]
    style: str
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

HOOKS: give 3 hook options (different moments or lines); code picks the best and puts it first. Each must be a
complete thought a stranger understands cold (never a line starting "and", "so", "because", or a reply to an unheard
question). hook word = one English word to set huge behind the person (used only when nobody talks).
hook_text = the on-screen hook over the first seconds when someone talks: 3-7 words, a specific question or bold
claim this reel answers ("Athletes body hair kyun hatate hain?", "Your rent is making you poor"), in the speaker's
language as spoken (romanized Hindi stays romanized), never one generic topic word ("HAIR", "ENERGY", "MONEY").

LENGTH AND SELECTION: a reel makes ONE point. Cut the warm-up, small talk, the host's long setup and any line that
repeats a point already made; 35-45 s beats 55 s unless the story truly needs more.

SECTIONS: 0-5 chapters (recipe steps, points of an argument): lead (1-3 small words) + text (1-2 words) + short
(<= 8 chars, for a progress bar) + icon (search words for a 3D icon, e.g. "fried egg").

GRAPHICS (beats): about one every {graphic_every} s of output, never two at once. Choose the kind by the
sentence's SHAPE, not by keyword spotting:
- a number said -> count_up (number, prefix like "$" or "₹", suffix like "%" or "k", text = what it counts)
- a list said ("X, Y and Z", "first... second...") -> list (items said; mark "check" only for good things, steps or
  benefits, "cross" for mistakes, risks, bad outcomes or "not X, not Y", "none" for neutral facts - a green tick
  beside a bad outcome reads as a mistake)
- a change or trend -> chart (trend up/down, text = what changes)
- a process or sequence -> flow (items)
- the reveal / turning point line -> keyword (text = 1-2 words, shown huge)
- a claim worth a full card -> statement (text <= 7 words)
- a person named -> name (text = name, lead = who they are)
- a thing, place or ingredient named or shown -> tag (text = its name, icon = search words)
- an action or money shot -> two (lead = 1-3 small words, text = 1-2 word keyword, icon = search words)
Anchor talking beats to word ids w0..w1 (the words that say it; at = until = -1, src = -1). Anchor picture beats
to src + at..until source seconds (w0 = w1 = -1). Every text must match what is said or clearly visible then.

DESIGNS (designs): the 1-3 strongest moments of a talking reel, where a graphic designed from scratch for this exact
line beats any template - a striking number with context ("50 times revenue"), a list or a before/after, a myth
being knocked down, the key claim. w0..w1 = the words that say it (1.5-5 s of speech); why = the idea the graphic
should show. A motion designer builds it; it replaces any beat on those words, so do not also put a beat there.
Empty for a picture-only reel.

INSERTS (what the viewer SEES while someone talks; premium edits show something related every few seconds, never
just the talking head for long): when a person talks, add an insert about every 3-4 s of output on the words that
name or imply something showable - a place, object, food, product, animal, body part, event, person's work, a
feeling or idea made concrete (stress -> a ticking clock, money -> a stack of cash, breathing -> lungs, success ->
a trophy), a number made visual. show = 1-2 plain English words for ONE concrete object or symbol that pictures
it (what an emoji or a 3D icon would show: "lungs", "alarm clock", "trophy", "brain", "money bag", "rocket"); it is
shown as an animated 3D object beside the speaker when no photo exists, so every insert needs a good show. kind "photo" or "broll" (a short
stock video clip: real footage of everyday life exists for almost anything - people working, a lawn being mowed, a
dentist with a patient, cash being counted, a car lot, city traffic; prefer broll whenever the thing moves or is an
action, photo for objects and places) with query = 3-6 concrete English search words a stock site would match,
naming what is SEEN, not the idea (e.g. "gardener laying fresh sod lawn", "dentist examining patient teeth",
"fresh croissants bakery tray"); label = 0-3 words to print on a photo card, or "". kind "footage" = a
moment of the user's OWN footage that shows what is said (src + at in source seconds) - only when that footage
has OTHER shots (B-roll, a different scene); a single talking take has nothing to cut to, so ask for photos then.
Anchor on word ids w0..w1 (src = -1, at = -1) or for footage give src + at too. No inserts on the hook or when
the speaker's face IS the point (a reaction, a punchline). Picture-only reels: inserts = [] (the clips are the
pictures). Never ask for logos of real brands or photos of private people.

BURNED CAPTIONS: set burned_captions = true when the footage already shows the creator's own text burned into the
picture: subtitles or captions that follow the speech, or text cards and labels explaining something (not a sign or
packaging that is part of the scene); then caption_mode must be "none" - two caption tracks read as a mistake.

CAPTIONS: caption_mode from the recipe (every_word whenever someone talks to camera or narrates, keyword only for ads and demos, none
when nobody talks). keywords = word ids shown big (nouns, numbers, punch words; about one per 3-6 words).
MUSIC: music "bed" under a voice, "score" for picture-only reels, mood to match. drop_word = id of the reveal word
(the music drops there), or -1.
SPELLING: speech recognition mishears names, dishes and dialect. For each wrong word id give the correct spelling
as a local would type it (romanized for Indic languages).
TITLE: title_lead + title_text name the result or the idea (shown over the payoff). cta <= 34 chars: one action the
viewer can take right now, tied to this video ("Follow for part 2", "Save this for your next trip", "Comment YES for
the recipe"); never vague ("Thanks for watching") and it promises nothing the video does not have. notes: two sentences on your plan."""


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
                 brief_text: str, target_seconds: float, window: tuple[int, float, float] | None = None) -> DirectorPlan:
    """The plan for the reel; with ``window`` (source, start, end) only that stretch is offered: one moment, seen closely."""
    words = audio.words
    if window:
        src, t0, t1 = window
        words = [w for w in words if w.src == src and t0 <= w.t0 <= t1]
        shots = [s for s in shots if s.src != src or (s.t0 < t1 and t0 < s.t1)]
    takes = earlier_takes(words) if words else set()
    graphic_every = 2.5
    system = SYSTEM.format(recipes=recipe_text(), audio_kind=audio.kind, audio_why=audio.why,
                           target=f"{target_seconds:.0f}" if target_seconds else "30-60 (pick what holds attention)",
                           graphic_every=graphic_every)
    source_rows = "\n".join(f"src{s.index}: {s.name} {s.kind} {s.duration:.1f}s {s.width}x{s.height}{' audio' if s.has_audio else ''}"
                            for s in sources)
    user = (f"Sources:\n{source_rows}\n\nUser brief: {brief_text or '(none: make the best reel from this footage)'}\n\n"
            f"Shots:\n{shot_listing(shots)}\n\n"
            f"Words (id:word, ~ = filler, [take] = earlier take):\n{word_listing(words, takes) if words else '(nobody speaks)'}\n\n"
            f"Frames: {how}.\n\nPlan the reel. JSON only.")
    plan = await vision_json(system + "\n\n" + styles.prompt() + "\n\n" + typekits.prompt() + "\n\n" + effects_prompt() + "\n\n" + scenes.prompt()
                             + "\n\n" + typekits.design_prompt(),
                             user, jpegs,
                             DirectorPlan, max_tokens=16000, step="reel_director")
    log.info("Director: recipe=%s audio=%s %d clips %d beats %d sections %d effects %d scenes", plan.recipe, plan.audio_view,
             len(plan.story), len(plan.beats), len(plan.sections), len(plan.effects), len(plan.scenes))
    return plan


def recipe(recipe_id: str) -> dict:
    return next((r for r in RECIPES if r["id"] == recipe_id), RECIPES[0])
