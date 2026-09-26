"""Map and Direct: two AI passes that turn a sentence table into edit plans.

Map (cheap model, low effort) reads the whole video once, in windows sized to
the provider, and answers with what the video is and where the candidate
moments are, by sentence id. Direct (strong model) reads only those candidates
with a little context and returns a complete edit plan per clip: which
sentence ranges to stitch, the teaser line, headline copy, layout, and beats
for the renderer. Everything the models answer is ids and short strings; code
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

log = get_logger(__name__)

# Bump when a prompt, model choice or edit rule changes, so clips made by each
# version can be compared on how users treat them (see feedback/).
DIRECTOR_VERSION = "2026-09-27.1"

LAYOUTS = ("auto", "single_speaker", "two_speaker_stack", "split_gameplay", "screen_with_speaker", "wide")
BEAT_EFFECTS = ("punch_in", "react_cut", "emphasis")
RUBRIC = ("hook", "payoff", "standalone", "emotion", "pacing")

MAP_OUTPUT_TOKENS = 3000
DIRECT_OUTPUT_TOKENS_PER_CLIP = 260
# Instruction text wrapped around each window, reserved out of the input budget.
PROMPT_OVERHEAD_TOKENS = 900
# Sentences shown before and after each candidate so the director can extend it.
CONTEXT_SENTENCES = 3
# Sentences repeated between Map windows so a moment on a boundary is whole in one.
WINDOW_OVERLAP_SENTENCES = 8

_STR_LIST = {"type": "array", "items": {"type": "string"}}
_ID = {"type": "integer"}

MAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "category": {"type": "string", "enum": list(CONTENT_TAXONOMY)},
        "confidence": {"type": "number"},
        "topics": _STR_LIST,
        "entities": _STR_LIST,
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"from": _ID, "to": _ID, "hook": _ID, "why": {"type": "string"}},
                "required": ["from", "to", "hook", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "category", "confidence", "topics", "entities", "candidates"],
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
                "required": ["segments", "hook", "title", "description", "hashtags", "layout", "beats", "scores", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["clips"],
    "additionalProperties": False,
}

# Shown in the prompt for providers that do not enforce the schema (Groq).
MAP_EXAMPLE = (
    '{"title":"...","summary":"...","category":"podcast_interview","confidence":0.8,'
    '"topics":["..."],"entities":["..."],"candidates":[{"from":12,"to":24,"hook":18,"why":"..."}]}'
)
DIRECTOR_EXAMPLE = (
    '{"clips":[{"segments":[{"from":12,"to":17},{"from":20,"to":24}],"hook":18,"title":"...",'
    '"description":"...","hashtags":["#..."],"layout":"single_speaker",'
    '"beats":[{"at":18,"fx":"punch_in","word":"..."}],'
    '"scores":{"hook":8,"payoff":7,"standalone":8,"emotion":6,"pacing":7},"why":"..."}]}'
)

TABLE_LEGEND = """Transcript lines read: id start_second speaker flags text.
Flags: !E louder than the surrounding minute (energy peak), !Q question, !P follows a long pause, !R loud reaction right after (laughter, applause, gasp)."""

# Shared by every prompt that reads a transcript or writes viewer-facing copy.
LANGUAGE_RULE = """The transcript may be in any language or a mix, including Hindi, Telugu, Hinglish and Tenglish, in native or Roman script. Judge meaning, hooks and humour in the language actually spoken, never through a literal English reading. Write every title, description and hashtag in the language mix the speaker uses, in the transcript's script: Roman script for a Roman-script transcript."""

MAP_SYSTEM = f"""You scout long videos for a short-form video editor. You read a transcript and point at the moments worth turning into standalone vertical shorts. You answer with sentence ids, never timestamps, and return valid JSON only.

{TABLE_LEGEND}

{LANGUAGE_RULE}

A strong candidate is one complete thought a stranger scrolling past would stop for and understand without the rest of the video: a story with a turn, a surprising claim with its explanation, a sharp disagreement, a joke with its punchline, a concrete how-to with its result, an emotional admission. Setup and payoff must both be inside it. Weak candidates: greetings, housekeeping, sponsor reads, "as I said earlier", lists with no point, anything that needs earlier context.

!E, !R and !Q often mark the heart of a good moment, but judge the words, not the flags."""

DIRECTOR_SYSTEM = f"""You are the lead editor of a short-form video team. From candidate moments of one long video you choose the clips worth posting and write a complete edit plan for each. Your clips are judged on: hook (the first two seconds stop the scroll), payoff (it lands the answer, reveal or punchline), standalone (a stranger understands it), emotion, and pacing (no dead air, no tangents). You return valid JSON only.

{TABLE_LEGEND}

{LANGUAGE_RULE}

How to edit:
- segments: the sentence id ranges the clip is stitched from, in ascending order, inclusive. Use one range unless cutting a tangent, a repetition, a false start or a slow stretch out of the middle clearly improves it; then use up to four. Never reorder sentences and never splice together separate topics.
- Start on the sentence that opens the thought: a question, a claim, a surprise, the first line of a story. Never start on a line that continues a previous one ("And...", "So...", "Which...").
- End right after the payoff. Never end on a setup line that promises what comes next.
- The stitched length must fall inside the requested range. Estimate it from the start seconds shown: a line lasts until the next line starts.
- hook: the id of the single most gripping line inside the clip, played first as a teaser: a bold claim, a number, a punchline, an emotional peak. 5-15 words, from the middle or end of the clip, never its first line, and it must make sense heard alone. 0 if no line qualifies.
- title: one sentence, at most 60 characters, about the payoff, not the setup. It is burned above the captions. Do not quote the transcript. description: 1-2 sentences. hashtags: 3-5.
- layout: single_speaker (one person talking), two_speaker_stack (a back-and-forth between two people on screen), split_gameplay (gameplay with a facecam), screen_with_speaker (slides or a screen share with a presenter), wide (a group or a scene), or auto if unsure.
- beats (at most 4, only where they help): punch_in on the line where the peak lands, with the key word; react_cut on a line whose listener's reaction is worth showing; emphasis on a key word or number to highlight in captions.
- scores: 1-10 per criterion, honestly. A 9 is a clip that would go viral on its own; most good clips are 6-8.
- why: one short sentence on what makes it work.

Choose the best clips, not the most. Fewer excellent clips beat a padded list. Never return two clips about the same moment."""

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
    ) -> dict[str, Any]:
        """What the video is, and candidate moments across all of it."""
        windows = _windows(sentences, _budget(self._map_client, MAP_OUTPUT_TOKENS))
        per_window = max(4, min(15, math.ceil(target_candidates / len(windows)) + 2))
        log.info("Map pass: %d sentence(s) in %d window(s), %d candidate(s) each", len(sentences), len(windows), per_window)
        results = await asyncio.gather(
            *(self._map_window(window, index, len(windows), duration, speakers, per_window)
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
    ) -> dict[str, Any]:
        legend = ", ".join(f"{letter} = {name}" for letter, name in speakers.items()) or "not identified"
        prompt = f"""Video length: {duration / 60:.1f} minutes. Speakers: {legend}.
This is part {index + 1} of {count}: sentences {window[0].id}-{window[-1].id}.

Return:
- title: a concise title for the whole video as far as this part shows it.
- summary: 2-3 sentences on this part.
- category: the video's category. confidence: 0-1.
- topics, entities: short lists.
- candidates: up to {wanted} moments, best first. from/to are sentence ids inside this part, one complete thought of roughly 15-75 seconds. hook is the id of its most gripping sentence (not its first) or 0. why is under 12 words.

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
        system = DIRECTOR_SYSTEM
        if category in CATEGORY_PLAYBOOKS:
            system += f"\n\n{CATEGORY_PLAYBOOKS[category]}"
        log.info("Director pass: %d candidate(s) in %d group(s), up to %d clip(s) each", len(blocks), len(groups), per_group)

        async def run(group: list[str]) -> list[dict[str, Any]]:
            prompt = f"""Video: {map_result.get('title', '')}. Category: {category}.
Summary: {map_result.get('summary', '')}

Choose up to {per_group} clips. Each clip's stitched length must be {min_seconds:.0f}-{max_seconds:.0f} seconds.

JSON shape: {DIRECTOR_EXAMPLE}

Candidates (with a few lines of context around each; you may use context lines):

{chr(10).join(group)}"""
            reply = await self._director_client.chat([
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ], temperature=0.3, max_tokens=DIRECT_OUTPUT_TOKENS_PER_CLIP * per_group + 300,
                json_mode=True, json_schema=DIRECTOR_SCHEMA)
            clips = _parse_json(reply).get("clips")
            return [c for c in clips if isinstance(c, dict)] if isinstance(clips, list) else []

        results = await asyncio.gather(*(run(group) for group in groups), return_exceptions=True)
        plans: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, BaseException):
                log.warning("Director group failed: %s", result)
                continue
            plans.extend(result)
        return plans


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


def _candidate_block(number: int, candidate: dict[str, Any], sentences: list[Sentence], by_id: dict[int, Sentence]) -> str:
    try:
        first, last = int(candidate.get("from")), int(candidate.get("to"))
    except (TypeError, ValueError):
        return ""
    if first not in by_id or last not in by_id or last < first:
        return ""
    lo = max(1, first - CONTEXT_SENTENCES)
    hi = min(len(sentences), last + CONTEXT_SENTENCES)
    lines = [by_id[i].line() for i in range(lo, hi + 1) if i in by_id]
    span = by_id[last].end - by_id[first].start
    return (
        f"Candidate {number}: sentences {first}-{last} (~{span:.0f}s). Scout's note: {candidate.get('why', '')}\n"
        + "\n".join(lines)
    )


def _merge_maps(parts: list[dict[str, Any]], sentences: list[Sentence]) -> dict[str, Any]:
    """One video-level map from per-window maps."""
    votes: dict[str, float] = {}
    for part in parts:
        category = str(part.get("category") or "unknown")
        if category in CONTENT_TAXONOMY:
            votes[category] = votes.get(category, 0.0) + float(part.get("confidence") or 0.5)
    category = max(votes, key=votes.get) if votes else "unknown"

    valid_ids = {s.id for s in sentences}
    candidates: list[dict[str, Any]] = []
    for part in parts:
        for c in part.get("candidates") or []:
            try:
                first, last = int(c.get("from")), int(c.get("to"))
            except (TypeError, ValueError):
                continue
            if first in valid_ids and last in valid_ids and last >= first:
                candidates.append({"from": first, "to": last, "hook": int(c.get("hook") or 0), "why": str(c.get("why", ""))})
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
        "category": category,
        "confidence": round(min(1.0, votes.get(category, 0.5) / max(1, len(parts))), 2),
        "topics": merged_list("topics", 12),
        "entities": merged_list("entities", 12),
        "candidates": kept,
    }


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
