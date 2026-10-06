"""Full stops back into stretches of speech Whisper wrote without any.

Whisper sometimes drops into an unpunctuated mode for minutes at a time ("what's
if i practice gratitude before bed for 10 minutes versus i use my instagram").
Sentences are found from punctuation, so in such a stretch they fall back to
pauses and clips open and close mid-thought. Each such stretch is sent to a small
LLM, which returns the same words with punctuation and capitals added. A word is
only replaced by the same word, punctuated; anything else keeps the original,
so a run never fails or changes what was said here.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from core.logging_config import get_logger
from transcription.language import SENTENCE_TERMINALS
from transcription.transliterate import _set_text, _words

log = get_logger(__name__)

BATCH_WORDS = 150
PARALLEL_BATCHES = 4
# A stretch with fewer sentence ends than one per this many words is unpunctuated;
# spoken sentences run 10-25 words.
WORDS_PER_SENTENCE_END = 40

SYSTEM = (
    "You add punctuation to speech transcribed without any. Return the same words in the same order, "
    "each with its punctuation attached (full stops, question marks, commas) and a capital where a "
    "sentence starts. Never add, drop, merge, split, respell or translate a word. Return valid JSON only."
)


async def punctuate_captions(segments: list[Any], is_pro: bool) -> int:
    """Punctuate ``segments`` in place on the plan's model; returns how many words changed."""
    from clients.ai import get_text_client

    return await punctuate_transcript(segments, get_text_client(is_pro=is_pro, step="punctuation"))


async def punctuate_transcript(segments: list[Any], client: Any) -> int:
    """Punctuate the unpunctuated stretches of ``segments`` in place; returns how many words changed."""
    words = [word for segment in segments for word in (_words(segment) or [])]
    batches = [words[start:start + BATCH_WORDS] for start in range(0, len(words), BATCH_WORDS)]
    bare = [batch for batch in batches if _unpunctuated(batch)]
    if not bare:
        return 0
    limit = asyncio.Semaphore(PARALLEL_BATCHES)

    async def punctuate(batch: list[dict]) -> int:
        async with limit:
            try:
                spelled = await _ask([w["word"] for w in batch], client)
            except Exception as exc:
                log.warning("Punctuation batch failed, keeping the words as heard: %s", exc)
                return 0
        changed = 0
        for word, new in zip(batch, spelled):
            if new != word["word"] and _bare(new) == _bare(word["word"]):
                word["word"] = new
                changed += 1
        return changed

    changed = sum(await asyncio.gather(*(punctuate(batch) for batch in bare)))
    if changed:
        for segment in segments:
            segment_words = _words(segment)
            if segment_words:
                _set_text(segment, " ".join(w["word"] for w in segment_words))
    return changed


def _unpunctuated(batch: list[dict]) -> bool:
    ends = sum(1 for w in batch if str(w["word"]).endswith(SENTENCE_TERMINALS))
    return ends * WORDS_PER_SENTENCE_END < len(batch)


def _bare(word: str) -> str:
    return re.sub(r"[^\w']", "", word).lower()


async def _ask(batch: list[str], client: Any) -> list[str]:
    prompt = (
        f"Punctuate these {len(batch)} words. Return {{\"words\": [...]}} with exactly {len(batch)} "
        f"strings, in the same order.\n\n{json.dumps(batch, ensure_ascii=False)}"
    )
    response = await client.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=8 * len(batch) + 100, json_mode=True,
    )
    data = json.loads(response[response.find("{"): response.rfind("}") + 1])
    words = data.get("words") if isinstance(data, dict) else None
    if not isinstance(words, list) or len(words) != len(batch):
        raise ValueError(f"expected {len(batch)} words, got {len(words) if isinstance(words, list) else 'none'}")
    return [str(word).strip() for word in words]
