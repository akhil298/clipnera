"""The model each reel step runs on, and vision calls that survive a provider's content filter.

Judgement (moments, the director, the hook, the review) runs on GPT-6.1 Sol: a fifth of GPT-6 Astra's price.
Simple choices (spelling, icons, photos) run on GPT-4.1 mini. ``REEL_STEP_MODELS`` overrides a step
("provider:model[:effort]") without a release, e.g. to put the director back on Astra.

Safety filters sometimes flag ordinary footage (raw meat, a gym, a crowd). A flagged request is retried with
the first half of the frames, then the second half, then with none at all (text only), so the agent still
answers from the transcript and shot list instead of failing the edit.
"""

from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel

from core.config import get_settings
from core.logging_config import get_logger
from usage.context import llm_scope

log = get_logger(__name__)

M = TypeVar("M", bound=BaseModel)
MODELS = {
    "reel_moments": "openai:gpt-6.1-sol-1:medium",
    "reel_director": "openai:gpt-6.1-sol-1:medium",
    "reel_verify": "openai:gpt-6.1-sol-1:low",
    "reel_review": "openai:gpt-6.1-sol-1:medium",
    "reel_proof": "openai:gpt-4.1-mini-1",
    "reel_icons": "openai:gpt-4.1-mini-1",
    "reel_photos": "openai:gpt-4.1-mini-1",
    "reel_check": "openai:gpt-4.1-mini-1",
}
FLAGGED = ("content_policy", "content_filter", "content safety", "responsibleaipolicy")


def flagged(exc: Exception) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 400:
        return False
    body = exc.response.text.lower()
    return any(word in body for word in FLAGGED)


def client(step: str):
    """The client for a reel step (one of ``MODELS``)."""
    from clients.ai import ModelChoice, get_text_client

    raw = ({**MODELS, **(get_settings().REEL_STEP_MODELS or {})}).get(step, MODELS["reel_director"])
    provider, model, effort = (raw.split(":") + ["", ""])[:3]
    return get_text_client(choice=ModelChoice(provider.strip().lower(), model.strip(), effort.strip() or None))


async def vision_json(system: str, text: str, jpegs: list[bytes], schema: type[M], max_tokens: int, step: str) -> M:
    """``schema`` answered from ``text`` and ``jpegs``; frames a filter refuses are left out rather than failing."""
    client_ = client(step)
    half = len(jpegs) // 2
    attempts = [jpegs, jpegs[:half], jpegs[half:], []] if len(jpegs) > 1 else [jpegs, []]
    last: Exception | None = None
    for n, frames in enumerate(attempts):
        if n and not frames and n < len(attempts) - 1:
            continue
        note = "" if frames is jpegs else ("\n\n(Some frames could not be shown; work from what is here.)" if frames
                                          else "\n\n(No frames could be shown; work from the words and the shot list.)")
        message = client_.image_message(text + note, frames) if frames else {"role": "user", "content": text + note}
        try:
            with llm_scope(step=step):
                return await client_.chat_json([{"role": "system", "content": system}, message], schema, max_tokens=max_tokens)
        except Exception as exc:
            if not flagged(exc):
                raise
            last = exc
            log.warning("Vision request flagged by the provider's filter (%d frames); retrying with fewer", len(frames))
    raise last if last else RuntimeError("vision call failed")
