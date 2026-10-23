"""Proof: the captions read what was said. Speech recognition mishears names, English words inside Hindi or Telugu,
and short words ("world the has" for "what the hell"); every review marked captions down for it.

One text call reads the words the reel keeps, in context, and returns only the words that were clearly misheard,
spelled as a local would type them. It never reorders, translates, adds or removes a word: a caption shows the
speech as spoken, code-switching and all.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from core.logging_config import get_logger
from reel_engine.director import sentences
from reel_engine.plan import Word

log = get_logger(__name__)

MAX_WORDS = 1500


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fix(_M):
    id: int
    word: str


class Fixes(_M):
    fixes: list[Fix]


SYSTEM = """You proofread an automatic transcript before it is burned in as captions. The speech is {language}; it is
written in Roman letters as people type it in chats (Hinglish / Tenglish style), English words kept in English.
Fix ONLY words that were clearly misheard: a word that makes no sense where it is, a name or brand spelled wrong, an
English word heard as a lookalike, a Hindi/Telugu word heard as an English one. Use the words around it to decide.
Never reorder, translate, merge, split, add or remove words; never "improve" grammar or style; code-switching is
correct, not an error. Each fix is the word id and the one word that replaces it. When unsure, leave it. JSON only."""


async def proofread(words: list[Word], language: str) -> int:
    """Correct misheard words in place; returns how many were changed (0 when the call fails: captions go as heard)."""
    from clients.ai import get_text_client

    if len(words) < 8:
        return 0
    rows = [" ".join(f"{w.i}:{w.text}" for w in words[a:b + 1]) for a, b in sentences(words[:MAX_WORDS])]
    by_id = {w.i: w for w in words}
    try:
        found = await get_text_client(is_pro=True, step="director").chat_json(
            [{"role": "system", "content": SYSTEM.format(language=language or "the speaker's language")},
             {"role": "user", "content": "Transcript (id:word):\n" + "\n".join(rows) + "\n\nJSON only."}], Fixes, max_tokens=3000)
    except Exception as exc:
        log.warning("Proofread failed, captions kept as heard: %s", exc)
        return 0
    changed = 0
    for fix in found.fixes:
        word = by_id.get(fix.id)
        new = fix.word.strip()
        # One word for one word: anything longer would shift the caption timing.
        if word and new and " " not in new and new != word.text:
            word.text = new
            changed += 1
    log.info("Proofread: %d word(s) corrected", changed)
    return changed
