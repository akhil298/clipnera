"""Map and Direct: two AI passes that turn a sentence table into edit plans.

Map (cheap model, low effort) reads the whole video once, in windows sized to
the provider, and answers with what the video is and where the candidate
moments are, by sentence id. Direct (strong model) reads only those candidates
with a little context and returns a complete edit plan per clip: which
sentence ranges to stitch, the teaser line, headline copy, format, layout,
and beats for the renderer. An optional Story pass stitches moments from
across the whole video into one clip, and a Check pass reads each stitched story as a
viewer would before it is kept. Everything the models answer is ids and short strings; code
turns ids into word-exact times and enforces every rule the models are asked
to follow (see :mod:`content_intelligence.edit_plan`).
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any

from content_intelligence.classifier import CONTENT_TAXONOMY
from content_intelligence.sentences import Sentence, format_table
from core.logging_config import get_logger
from formats import DEFAULT_FORMAT, FORMATS, RECIPES, prompt_catalogue

log = get_logger(__name__)

# Bump when a prompt, model choice or edit rule changes, so clips made by each
# version can be compared on how users treat them (see feedback/).
DIRECTOR_VERSION = "2026-10-02.1"

LAYOUTS = ("auto", "single_speaker", "two_speaker_stack", "split_gameplay", "screen_with_speaker", "wide")
BEAT_EFFECTS = ("punch_in", "react_cut", "emphasis")
RUBRIC = ("hook", "payoff", "standalone", "emotion", "pacing")
# Formats whose clip is a run of spoken items, each labelled (and ranked) by the director.
LIST_FORMATS = ("listicle", "ranking")
# Formats the picture must show; the words alone never make a clip one of these.
VISUAL_FORMATS = tuple(r.format for r in RECIPES.values() if r.needs - {"face"})

MAP_OUTPUT_TOKENS = 3000
DIRECT_OUTPUT_TOKENS_PER_CLIP = 300
CHECK_OUTPUT_TOKENS_PER_CLIP = 60
# Instruction text wrapped around each window, reserved out of the input budget.
PROMPT_OVERHEAD_TOKENS = 1300
# Sentences shown before and after each candidate so the director can extend it.
CONTEXT_SENTENCES = 3
# Sentences repeated between Map windows so a moment on a boundary is whole in one.
WINDOW_OVERLAP_SENTENCES = 8

_STR_LIST = {"type": "array", "items": {"type": "string"}}
_ID = {"type": "integer"}
_FORMAT = {"type": "string", "enum": list(FORMATS)}

MAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "category": {"type": "string", "enum": list(CONTENT_TAXONOMY)},
        "confidence": {"type": "number"},
        "topics": _STR_LIST,
        "entities": _STR_LIST,
        "format": _FORMAT,
        "format_confidence": {"type": "number"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"from": _ID, "to": _ID, "hook": _ID, "format": _FORMAT, "why": {"type": "string"}},
                "required": ["from", "to", "hook", "format", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "category", "confidence", "topics", "entities", "format", "format_confidence",
                 "candidates"],
    "additionalProperties": False,
}

_SCORE_10 = {"type": "number"}
DIRECTOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"from": _ID, "to": _ID},
                            "required": ["from", "to"],
                            "additionalProperties": False,
                        },
                    },
                    "hook": _ID,
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "hashtags": _STR_LIST,
                    "format": _FORMAT,
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"at": _ID, "label": {"type": "string"}, "rank": _ID},
                            "required": ["at", "label", "rank"],
                            "additionalProperties": False,
                        },
                    },
                    "layout": {"type": "string", "enum": list(LAYOUTS)},
                    "beats": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "at": _ID,
                                "fx": {"type": "string", "enum": list(BEAT_EFFECTS)},
                                "word": {"type": "string"},
                            },
                            "required": ["at", "fx", "word"],
                            "additionalProperties": False,
                        },
                    },
                    "scores": {
                        "type": "object",
                        "properties": {key: _SCORE_10 for key in RUBRIC},
                        "required": list(RUBRIC),
                        "additionalProperties": False,
                    },
                    "why": {"type": "string"},
                },
                "required": ["segments", "hook", "title", "description", "hashtags", "format", "items", "layout",
                             "beats", "scores", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["clips"],
    "additionalProperties": False,
}

CHECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"clip": _ID, "ok": {"type": "boolean"}, "issue": {"type": "string"}},
                "required": ["clip", "ok", "issue"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

# Shown in the prompt for providers that do not enforce the schema (Groq).
MAP_EXAMPLE = (
    '{"title":"...","summary":"...","category":"podcast_interview","confidence":0.8,'
    '"topics":["..."],"entities":["..."],"format":"talking_head","format_confidence":0.7,'
    '"candidates":[{"from":12,"to":24,"hook":18,"format":"talking_head","why":"..."}]}'
)
DIRECTOR_EXAMPLE = (
    '{"clips":[{"segments":[{"from":12,"to":17},{"from":20,"to":24}],"hook":18,"title":"...",'
    '"description":"...","hashtags":["#..."],"format":"talking_head","items":[],"layout":"single_speaker",'
    '"beats":[{"at":18,"fx":"punch_in","word":"..."}],'
    '"scores":{"hook":8,"payoff":7,"standalone":8,"emotion":6,"pacing":7},"why":"..."}]}'
)
CHECK_EXAMPLE = '{"verdicts":[{"clip":1,"ok":true,"issue":""},{"clip":2,"ok":false,"issue":"..."}]}'

# Joins a story clip's pieces in its transcript, for the Check pass and for display.
STORY_SEPARATOR = " … "

TABLE_LEGEND = """Transcript lines read: id start_second speaker flags text.
Flags: !E louder than the surrounding minute (energy peak), !Q question, !P follows a long pause, !R loud reaction right after (laughter, applause, gasp).
[sees: ...], when present, is what is on screen during the line. Favour moments that are strong to watch as well as to hear, and never pick a line whose words point at something the picture does not show."""

# Shared by every prompt that reads a transcript or writes viewer-facing copy.
LANGUAGE_RULE = """The transcript may be in any language or a mix, including Hindi, Telugu, Hinglish and Tenglish, in native or Roman script. Judge meaning, hooks and humour in the language actually spoken, never through a literal English reading. Write every title, description and hashtag in the language mix the speaker uses, in the transcript's script: Roman script for a Roman-script transcript."""

# How a format is chosen, for every prompt that chooses one.
FORMAT_RULES = f"""Formats (what a clip is):
{prompt_catalogue()}
Judge the format from the words together with the measured on-screen evidence and the [sees: ...] notes. {", ".join(VISUAL_FORMATS)} need the picture to show it; never choose them from the words alone. {" and ".join(LIST_FORMATS)} need the spoken words to enumerate or rank the items. A clip's format can differ from the video's: a podcast clip that is a numbered list of three tips is a listicle; a clip of a reaction video is a reaction. If unsure, {DEFAULT_FORMAT}."""

MAP_SYSTEM = f"""You scout long videos for a short-form video editor. You read a transcript and point at the moments worth turning into standalone vertical shorts. You answer with sentence ids, never timestamps, and return valid JSON only.

{TABLE_LEGEND}

{LANGUAGE_RULE}

A strong candidate is one complete thought a stranger scrolling past would stop for and understand without the rest of the video: a story with a turn, a surprising claim with its explanation, a sharp disagreement, a joke with its punchline, a concrete how-to with its result, an emotional admission. Setup and payoff must both be inside it. Weak candidates: greetings, housekeeping, sponsor reads, "as I said earlier", lists with no point, anything that needs earlier context.

!E, !R and !Q often mark the heart of a good moment, but judge the words, not the flags.

{FORMAT_RULES}"""

# How every clip's fields are filled in, whether it is one moment or a story.
CLIP_FIELD_RULES = """- hook: the id of the single most gripping line inside the clip, played first as a teaser: a bold claim, a number, a punchline, an emotional peak. 5-15 words, from the middle or end of the clip, never its first line, and it must make sense heard alone. 0 if no line qualifies.
- title: one sentence, at most 60 characters, about the payoff, not the setup. It is burned above the captions. Do not quote the transcript. description: 1-2 sentences. hashtags: 3-5.
- format: what this clip is (see Formats). items: for listicle or ranking, at least 2, in the order spoken: at is the id of the line where the item starts, label names the item in at most 5 words, rank is its rank as said (a countdown 5 to 1 gives 5, 4, 3, 2, 1) or 0 when unranked. [] for every other format.
- layout: single_speaker (one person talking), two_speaker_stack (a back-and-forth between two people on screen), split_gameplay (gameplay with a facecam), screen_with_speaker (slides or a screen share with a presenter), wide (a group or a scene), or auto if unsure.
- beats (at most 4, only where they help): punch_in on the line where the peak lands, with the key word; react_cut on a line whose listener's reaction is worth showing; emphasis on a key word or number to highlight in captions.
- scores: 1-10 per criterion, honestly. A 9 is a clip that would go viral on its own; most good clips are 6-8.
- why: one short sentence on what makes it work."""

DIRECTOR_SYSTEM = f"""You are the lead editor of a short-form video team. From candidate moments of one long video you choose the clips worth posting and write a complete edit plan for each. Your clips are judged on: hook (the first two seconds stop the scroll), payoff (it lands the answer, reveal or punchline), standalone (a stranger understands it), emotion, and pacing (no dead air, no tangents). You return valid JSON only.

{TABLE_LEGEND}

{LANGUAGE_RULE}

How to edit:
- segments: the sentence id ranges the clip is stitched from, in ascending order, inclusive. Use one range unless cutting a tangent, a repetition, a false start or a slow stretch out of the middle clearly improves it; then use up to four. Never reorder sentences and never splice together separate topics.
- Start on the sentence that opens the thought: a question, a claim, a surprise, the first line of a story. Never start on a line that continues a previous one ("And...", "So...", "Which...").
- End right after the payoff. Never end on a setup line that promises what comes next.
- The stitched length must fall inside the requested range. Estimate it from the start seconds shown: a line lasts until the next line starts.
{CLIP_FIELD_RULES}

{FORMAT_RULES}

Choose the best clips, not the most. Fewer excellent clips beat a padded list. Never return two clips about the same moment."""

STORY_SYSTEM = f"""You are the lead editor of a short-form video team. Besides single moments, you cut story clips: one vertical short stitched from moments far apart in the same long video, the way a human editor cuts a recap. Your clips are judged on: hook, payoff, standalone (a stranger understands it), emotion, and pacing. You return valid JSON only.

{TABLE_LEGEND}

{LANGUAGE_RULE}

Story shapes that work:
- Arc: a question, problem or promise from one part of the video, the struggle or turning point from another, and the answer, result or punchline from a later one.
- List: 2-4 short points on one theme gathered from across the video, each a complete line. Format listicle, one item per point.
- Ranking: 2-5 items rated across the video (a countdown, verdicts building to the best), each with its verdict. Format ranking, items ranked as said.
- Change: how a view, plan or mood shifts over the video, the early statement then the later one.

How to edit:
- segments: 2-8 sentence id ranges, in ascending order, inclusive. At least two must be more than a minute apart in the video, or it is not a story clip. Each range is one complete thought: it starts on a line that opens it and ends on a finished sentence. 1-3 sentences per range is typical.
- Each piece must follow naturally from the one before, as if it had been said in that order. Leave out lines that point outside the clip: "as I said earlier", "that guy", "this one" with nothing to refer to.
- Keep every speaker's meaning. Never join lines so a claim reads differently than it was said, and never pair a question with the answer to a different question.
- The stitched length must fall inside the requested range. Estimate it from the start seconds shown: a line lasts until the next line starts.
{CLIP_FIELD_RULES}

{FORMAT_RULES}

Only return a story when it is clearly worth watching on its own. Return an empty list rather than a forced one, and never two stories built from the same moments."""

CHECK_SYSTEM = f"""You review stitched short-form clips before they are posted. Each clip is the transcript of pieces of one long video joined together; "{STORY_SEPARATOR.strip()}" marks a cut. A viewer sees only the clip.

{LANGUAGE_RULE}

Mark a clip ok false when any of these hold: a line refers to something or someone the clip never shows; a piece begins or ends so it sounds cut off; a join makes a speaker seem to say something they did not mean; the pieces do not add up to one point or story. Otherwise ok true. issue: under 12 words, empty when ok. Return valid JSON only."""

CATEGORY_PLAYBOOKS: dict[str, str] = {
    "podcast_interview": "Podcasts: favour stories with a turn, contrarian opinions with their reasoning, and confessions. A guest's answer usually needs the host's question as its opening line. Use two_speaker_stack when the exchange itself is the point; react_cut when the host's face sells the moment.",
    "gaming": "Gaming: favour clutch plays, fails, rage and hype moments, and funny commentary. !E and !R lines matter more than words here. Layout split_gameplay when a streamer talks over gameplay. Keep clips tight; cut dead gameplay stretches out of the middle.",
    "tutorial_educational": "Tutorials: favour one tip with its result, a common mistake and its fix, or a surprising fact with its proof. The payoff is the outcome, not the steps. Use screen_with_speaker when the presenter shows a screen. Cut repeated explanations.",
    "comedy": "Comedy: the punchline and the reaction are the clip. Start at the setup's first line, end after the laugh (!R). Never cut inside a bit.",
    "reaction": "Reactions: show what is being reacted to, then the reaction. Hooks are the biggest reaction lines.",
    "news_politics": "News and politics: favour clear claims with evidence, sharp exchanges, and explainers of what happened and why it matters. Keep the speaker's words in context; do not stitch lines so a claim reads differently than it was said.",
    "vlog": "Vlogs: favour moments with a clear emotion or surprise, and stories with a result.",
    "tech": "Tech: favour verdicts, comparisons with a winner, surprising numbers, and demos with a visible result.",
    "fitness_health": "Fitness and health: favour one actionable tip with why it works, myths busted, and transformations.",
    "food": "Food: favour the reveal, the taste reaction, and one technique with its result.",
    "music": "Music: favour performances with a peak, and stories behind songs.",
    "sports": "Sports: favour the decisive play, the reaction, and hot takes with reasoning.",
}

FORMAT_PLAYBOOKS: dict[str, str] = {r.format: f"{r.label}: {r.playbook}" for r in RECIPES.values()}


class VideoDirector:
    def __init__(self, map_client: Any, director_client: Any) -> None:
        self._map_client = map_client
        self._director_client = director_client

    # ---- Map -------------------------------------------------------------

    async def map(
        self,
        sentences: list[Sentence],
        duration: float,
        speakers: dict[str, str],
        target_candidates: int,
        *,
        evidence: str = "",
    ) -> dict[str, Any]:
        """What the video is, and candidate moments across all of it.

        ``evidence`` summarises what the visual probe measured on screen.
        """
        windows = _windows(sentences, _budget(self._map_client, MAP_OUTPUT_TOKENS))
        per_window = max(4, min(15, math.ceil(target_candidates / len(windows)) + 2))
        log.info("Map pass: %d sentence(s) in %d window(s), %d candidate(s) each", len(sentences), len(windows), per_window)
        results = await asyncio.gather(
            *(self._map_window(window, index, len(windows), duration, speakers, per_window, evidence)
              for index, window in enumerate(windows)),
            return_exceptions=True,
        )
        parts = [r for r in results if isinstance(r, dict)]
        for r in results:
            if isinstance(r, BaseException):
                log.warning("Map window failed: %s", r)
        if not parts:
            raise RuntimeError("Every Map window failed")
        return _merge_maps(parts, sentences)

    async def _map_window(
        self,
        window: list[Sentence],
        index: int,
        count: int,
        duration: float,
        speakers: dict[str, str],
        wanted: int,
        evidence: str,
    ) -> dict[str, Any]:
        legend = ", ".join(f"{letter} = {name}" for letter, name in speakers.items()) or "not identified"
        prompt = f"""Video length: {duration / 60:.1f} minutes. Speakers: {legend}.{_on_screen(evidence)}
This is part {index + 1} of {count}: sentences {window[0].id}-{window[-1].id}.

Return:
- title: a concise title for the whole video as far as this part shows it.
- summary: 2-3 sentences on this part.
- category: the video's category. confidence: 0-1.
- topics, entities: short lists.
- format: what the video mostly is. format_confidence: 0-1.
- candidates: up to {wanted} moments, best first. from/to are sentence ids inside this part, one complete thought of roughly 15-75 seconds. hook is the id of its most gripping sentence (not its first) or 0. format is what that clip would be. why is under 12 words.

JSON shape: {MAP_EXAMPLE}

Transcript:
{format_table(window)}"""
        reply = await self._map_client.chat([
            {"role": "system", "content": MAP_SYSTEM},
            {"role": "user", "content": prompt},
        ], temperature=0.2, max_tokens=MAP_OUTPUT_TOKENS, json_mode=True, json_schema=MAP_SCHEMA)
        return _parse_json(reply)

    # ---- Direct ----------------------------------------------------------

    async def direct(
        self,
        sentences: list[Sentence],
        map_result: dict[str, Any],
        max_clips: int,
        min_seconds: float,
        max_seconds: float,
        *,
        evidence: str = "",
    ) -> list[dict[str, Any]]:
        """Edit plans for the best clips among the Map's candidates."""
        candidates = map_result.get("candidates") or []
        if not candidates:
            return []
        by_id = {s.id: s for s in sentences}
        blocks = [_candidate_block(n + 1, c, sentences, by_id) for n, c in enumerate(candidates)]
        blocks = [b for b in blocks if b]

        budget = _budget(self._director_client, DIRECT_OUTPUT_TOKENS_PER_CLIP * max_clips + 400)
        groups = _pack(blocks, budget)
        per_group = max(2, math.ceil(max_clips / len(groups)) + (1 if len(groups) > 1 else 0))
        category = str(map_result.get("category") or "unknown")
        system = DIRECTOR_SYSTEM + _playbooks(map_result, category)
        log.info("Director pass: %d candidate(s) in %d group(s), up to %d clip(s) each", len(blocks), len(groups), per_group)

        async def run(group: list[str]) -> list[dict[str, Any]]:
            prompt = f"""{_video_header(map_result, category, evidence)}

Choose up to {per_group} clips. Each clip's stitched length must be {min_seconds:.0f}-{max_seconds:.0f} seconds.

JSON shape: {DIRECTOR_EXAMPLE}

Candidates (with a few lines of context around each; you may use context lines):

{chr(10).join(group)}"""
            return await self._plans(system, prompt, per_group)

        results = await asyncio.gather(*(run(group) for group in groups), return_exceptions=True)
        plans: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, BaseException):
                log.warning("Director group failed: %s", result)
                continue
            plans.extend(result)
        return plans

    # ---- Story -----------------------------------------------------------

    async def story(
        self,
        sentences: list[Sentence],
        map_result: dict[str, Any],
        count: int,
        min_seconds: float,
        max_seconds: float,
        *,
        evidence: str = "",
    ) -> list[dict[str, Any]]:
        """Edit plans for clips stitched from moments across the whole video.

        Unlike Direct, one call sees every candidate at once, since a story's
        pieces can sit anywhere in the video. Candidates are shown without
        context and, when they overflow the budget, thinned evenly so the
        whole video stays in view.
        """
        candidates = map_result.get("candidates") or []
        if len(candidates) < 2 or count <= 0:
            return []
        by_id = {s.id: s for s in sentences}
        blocks = [_candidate_block(n + 1, c, sentences, by_id, context=0) for n, c in enumerate(candidates)]
        blocks = _spread(
            [b for b in blocks if b],
            _budget(self._director_client, DIRECT_OUTPUT_TOKENS_PER_CLIP * count + 400),
        )
        category = str(map_result.get("category") or "unknown")
        log.info("Story pass: %d moment(s) shown, up to %d story clip(s)", len(blocks), count)
        prompt = f"""{_video_header(map_result, category, evidence)}

Choose up to {count} story clips. Each clip's stitched length must be {min_seconds:.0f}-{max_seconds:.0f} seconds.

JSON shape: {DIRECTOR_EXAMPLE}

Moments across the video, in order:

{chr(10).join(blocks)}"""
        return await self._plans(STORY_SYSTEM + _playbooks(map_result, category, LIST_FORMATS), prompt, count)

    async def check(self, transcripts: list[str]) -> list[bool]:
        """Whether each stitched clip reads as one natural clip to a viewer."""
        if not transcripts:
            return []
        clips = "\n\n".join(f"Clip {n + 1}: {text}" for n, text in enumerate(transcripts))
        reply = await self._map_client.chat([
            {"role": "system", "content": CHECK_SYSTEM},
            {"role": "user", "content": f"JSON shape: {CHECK_EXAMPLE}\n\n{clips}"},
        ], temperature=0.0, max_tokens=CHECK_OUTPUT_TOKENS_PER_CLIP * len(transcripts) + 100,
            json_mode=True, json_schema=CHECK_SCHEMA)
        verdicts: dict[int, dict[str, Any]] = {}
        for verdict in _parse_json(reply).get("verdicts") or []:
            try:
                verdicts[int(verdict.get("clip"))] = verdict
            except (AttributeError, TypeError, ValueError):
                continue
        results = []
        for n in range(1, len(transcripts) + 1):
            verdict = verdicts.get(n) or {}
            ok = verdict.get("ok") is True
            if not ok:
                log.info("Story clip %d rejected by the check: %s", n, verdict.get("issue") or "no verdict")
            results.append(ok)
        return results

    async def _plans(self, system: str, prompt: str, count: int) -> list[dict[str, Any]]:
        reply = await self._director_client.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ], temperature=0.3, max_tokens=DIRECT_OUTPUT_TOKENS_PER_CLIP * count + 300,
            json_mode=True, json_schema=DIRECTOR_SCHEMA)
        clips = _parse_json(reply).get("clips")
        return [c for c in clips if isinstance(c, dict)] if isinstance(clips, list) else []


def _video_header(map_result: dict[str, Any], category: str, evidence: str) -> str:
    return (
        f"Video: {map_result.get('title', '')}. Category: {category}. Format: {map_result.get('format') or DEFAULT_FORMAT}."
        f"{_on_screen(evidence)}\nSummary: {map_result.get('summary', '')}"
    )


def _on_screen(evidence: str) -> str:
    return f"\nOn screen (measured): {evidence.strip()}" if evidence.strip() else ""


def _playbooks(map_result: dict[str, Any], category: str, extra: tuple[str, ...] = ()) -> str:
    """The category's playbook and those of the formats the clips are likely
    to take: the video's, its candidates', and ``extra``."""
    formats = [map_result.get("format"), *(c.get("format") for c in map_result.get("candidates") or []), *extra]
    books = [CATEGORY_PLAYBOOKS.get(category), *(FORMAT_PLAYBOOKS.get(f) for f in dict.fromkeys(formats) if f)]
    return "".join(f"\n\n{book}" for book in books if book)


def _budget(client: Any, output_tokens: int) -> int:
    getter = getattr(client, "input_token_budget", None)
    budget = 6000
    if callable(getter):
        try:
            budget = int(getter(output_tokens))
        except Exception as exc:
            log.warning("Provider did not report a token budget (%s); using the default", exc)
    return max(1000, budget - PROMPT_OVERHEAD_TOKENS)


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _windows(sentences: list[Sentence], budget: int) -> list[list[Sentence]]:
    windows: list[list[Sentence]] = []
    current: list[Sentence] = []
    used = 0
    for sentence in sentences:
        cost = _tokens(sentence.line()) + 1
        if current and used + cost > budget:
            windows.append(current)
            current = current[-WINDOW_OVERLAP_SENTENCES:]
            used = sum(_tokens(s.line()) + 1 for s in current)
        current.append(sentence)
        used += cost
    if current:
        windows.append(current)
    return windows


def _pack(blocks: list[str], budget: int) -> list[list[str]]:
    groups: list[list[str]] = [[]]
    used = 0
    for block in blocks:
        cost = _tokens(block) + 2
        if groups[-1] and used + cost > budget:
            groups.append([])
            used = 0
        groups[-1].append(block)
        used += cost
    return groups


def _spread(blocks: list[str], budget: int) -> list[str]:
    """``blocks`` thinned evenly, keeping their order, to fit ``budget``."""
    total = sum(_tokens(block) + 2 for block in blocks)
    if total <= budget:
        return blocks
    keep = max(1, len(blocks) * budget // total)
    step = len(blocks) / keep
    return [blocks[int(i * step)] for i in range(keep)]


def _candidate_block(
    number: int,
    candidate: dict[str, Any],
    sentences: list[Sentence],
    by_id: dict[int, Sentence],
    context: int = CONTEXT_SENTENCES,
) -> str:
    try:
        first, last = int(candidate.get("from")), int(candidate.get("to"))
    except (TypeError, ValueError):
        return ""
    if first not in by_id or last not in by_id or last < first:
        return ""
    lo = max(1, first - context)
    hi = min(len(sentences), last + context)
    lines = [by_id[i].line() for i in range(lo, hi + 1) if i in by_id]
    span = by_id[last].end - by_id[first].start
    return (
        f"Candidate {number}: sentences {first}-{last} (~{span:.0f}s), {candidate.get('format') or DEFAULT_FORMAT}. "
        f"Scout's note: {candidate.get('why', '')}\n"
        + "\n".join(lines)
    )


def _merge_maps(parts: list[dict[str, Any]], sentences: list[Sentence]) -> dict[str, Any]:
    """One video-level map from per-window maps.

    Category and format are each the value most windows vote for, weighted by
    their confidence; a missing or unknown value casts no vote.
    """
    category, category_confidence = _vote(parts, "category", CONTENT_TAXONOMY, "confidence")
    video_format, format_confidence = _vote(parts, "format", FORMATS, "format_confidence")
    video_format = video_format or DEFAULT_FORMAT

    valid_ids = {s.id for s in sentences}
    candidates: list[dict[str, Any]] = []
    for part in parts:
        for c in part.get("candidates") or []:
            try:
                first, last = int(c.get("from")), int(c.get("to"))
            except (TypeError, ValueError):
                continue
            if first in valid_ids and last in valid_ids and last >= first:
                candidates.append({
                    "from": first, "to": last, "hook": int(c.get("hook") or 0),
                    "format": c.get("format") if c.get("format") in FORMATS else video_format,
                    "why": str(c.get("why", "")),
                })
    # Window overlap can surface the same moment twice; keep the first, which
    # its window ranked higher.
    kept: list[dict[str, Any]] = []
    for c in candidates:
        if not any(min(c["to"], k["to"]) - max(c["from"], k["from"]) >= 0.5 * (c["to"] - c["from"] + 1) for k in kept):
            kept.append(c)
    kept.sort(key=lambda c: c["from"])

    def merged_list(key: str, limit: int) -> list[str]:
        seen: list[str] = []
        for part in parts:
            for item in part.get(key) or []:
                if isinstance(item, str) and item.strip() and item.strip() not in seen:
                    seen.append(item.strip())
        return seen[:limit]

    return {
        "title": str(parts[0].get("title") or ""),
        "summary": " ".join(str(p.get("summary") or "").strip() for p in parts)[:1200],
        "category": category or "unknown",
        "confidence": category_confidence if category else round(min(1.0, 0.5 / len(parts)), 2),
        "topics": merged_list("topics", 12),
        "entities": merged_list("entities", 12),
        "format": video_format,
        "format_confidence": format_confidence,
        "candidates": kept,
    }


def _vote(parts: list[dict[str, Any]], key: str, allowed: Any, weight_key: str) -> tuple[str | None, float]:
    """The ``allowed`` value of ``key`` with the most confidence-weighted votes
    across ``parts``, and its share of all parts (0-1)."""
    votes: dict[str, float] = {}
    for part in parts:
        value = part.get(key)
        if isinstance(value, str) and value in allowed:
            votes[value] = votes.get(value, 0.0) + _confidence(part.get(weight_key))
    if not votes:
        return None, 0.0
    best = max(votes, key=votes.__getitem__)
    return best, round(min(1.0, votes[best] / len(parts)), 2)


def _confidence(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _parse_json(text: str) -> dict[str, Any]:
    candidate = (text or "").strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start:end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
