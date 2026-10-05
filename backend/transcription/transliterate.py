"""Roman-script captions for Hindi, Telugu, Hinglish and Tenglish.

Each distinct Hindi or Telugu word in the transcript is sent once to a small
LLM, which spells it the way the language is typed online ("kya", "bagunnava")
and gives English words their English spelling even when Whisper wrote them in
Hindi or Telugu script ("మీటింగ్" -> "meeting"). Words keep their timings; the
original spelling stays on the word as ``native``. Anything the model does not
return cleanly falls back to the rule-based romaniser, so a run never fails
here.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from typing import Any, Literal, get_args

from core.logging_config import get_logger
from transcription.language import is_indic, romanize_word

log = get_logger(__name__)

CaptionScript = Literal["auto", "roman", "native"]
CAPTION_SCRIPTS = frozenset(get_args(CaptionScript))
BATCH_WORDS = 300
PARALLEL_BATCHES = 4

SYSTEM = (
    "You transliterate Hindi and Telugu words into Roman script the way Indians type Hinglish and "
    "Tenglish on WhatsApp and Instagram: simple spellings, no diacritics. A word that is really English "
    "written in Hindi or Telugu script gets its normal English spelling. Return valid JSON only."
)


def wants_roman(caption_script: str | None, segments: Iterable[Any]) -> bool:
    """Whether captions should be romanised. Auto: yes whenever the speech is in Hindi or Telugu script."""
    if caption_script == "native":
        return False
    if caption_script == "roman":
        return True
    return any(is_indic(_text(segment)) for segment in segments)


async def romanize_transcript(segments: list[Any], client: Any) -> int:
    """Rewrite Hindi and Telugu words in Roman script in place; returns how many words changed."""
    words = [word for segment in segments for word in (_words(segment) or [])]
    spellings = await _spellings(sorted({w["word"] for w in words if is_indic(w["word"])}), client)
    changed = 0
    for word in words:
        roman = spellings.get(word["word"])
        if roman:
            word["native"], word["word"] = word["word"], roman
            changed += 1
    for segment in segments:
        segment_words = _words(segment)
        text = (
            " ".join(w["word"] for w in segment_words)
            if segment_words
            else " ".join(spellings.get(t) or romanize_word(t) for t in _text(segment).split())
        )
        _set_text(segment, text)
    return changed


async def _spellings(unique: list[str], client: Any) -> dict[str, str]:
    """Roman spellings for ``unique``, its batches asked at once.

    One after another, a long Telugu or Hindi video spent minutes here; the
    client's rate limiter still paces concurrent batches to the account's limits.
    """
    limit = asyncio.Semaphore(PARALLEL_BATCHES)

    async def spell(batch: list[str]) -> dict[str, str]:
        async with limit:
            try:
                found = await _ask(batch, client)
            except Exception as exc:
                log.warning("Transliteration batch failed, using rule-based spelling: %s", exc)
                found = {}
        return {word: found.get(word) or romanize_word(word) for word in batch}

    spellings: dict[str, str] = {}
    batches = [unique[start:start + BATCH_WORDS] for start in range(0, len(unique), BATCH_WORDS)]
    for result in await asyncio.gather(*(spell(batch) for batch in batches)):
        spellings.update(result)
    return spellings


async def _ask(batch: list[str], client: Any) -> dict[str, str]:
    prompt = (
        f"Transliterate these {len(batch)} words. Return {{\"words\": [...]}} with exactly {len(batch)} "
        f"strings, in the same order.\n\n{json.dumps(batch, ensure_ascii=False)}"
    )
    response = await client.chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=12 * len(batch) + 100, json_mode=True,
    )
    data = json.loads(response[response.find("{"): response.rfind("}") + 1])
    roman = data.get("words") if isinstance(data, dict) else None
    if not isinstance(roman, list) or len(roman) != len(batch):
        raise ValueError(f"expected {len(batch)} words, got {len(roman) if isinstance(roman, list) else 'none'}")
    # Keep only clean answers: a non-empty Latin-script spelling of one word.
    return {
        native: spelling.strip()
        for native, spelling in zip(batch, roman)
        if isinstance(spelling, str) and spelling.strip() and not is_indic(spelling) and " " not in spelling.strip()
    }


def _words(segment: Any) -> list[dict] | None:
    return segment.get("words") if isinstance(segment, dict) else getattr(segment, "words", None)


def _text(segment: Any) -> str:
    return str(segment.get("text", "") if isinstance(segment, dict) else getattr(segment, "text", ""))


def _set_text(segment: Any, text: str) -> None:
    if isinstance(segment, dict):
        segment["text"] = text
    else:
        segment.text = text
