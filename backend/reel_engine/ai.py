"""Vision calls that survive a provider's content filter.

Safety filters sometimes flag ordinary footage (raw meat, a gym, a crowd). A flagged request is retried with
the first half of the frames, then the second half, then with none at all (text only), so the agent still
answers from the transcript and shot list instead of failing the edit.
"""

from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel

from core.logging_config import get_logger

log = get_logger(__name__)

M = TypeVar("M", bound=BaseModel)
FLAGGED = ("content_policy", "content_filter", "content safety", "responsibleaipolicy")


def flagged(exc: Exception) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 400:
        return False
    body = exc.response.text.lower()
    return any(word in body for word in FLAGGED)


async def vision_json(system: str, text: str, jpegs: list[bytes], schema: type[M], max_tokens: int) -> M:
    """``schema`` answered from ``text`` and ``jpegs``; frames a filter refuses are left out rather than failing."""
    from clients.ai import get_text_client

    client = get_text_client(is_pro=True, step="director")
    half = len(jpegs) // 2
    attempts = [jpegs, jpegs[:half], jpegs[half:], []] if len(jpegs) > 1 else [jpegs, []]
    last: Exception | None = None
    for n, frames in enumerate(attempts):
        if n and not frames and n < len(attempts) - 1:
            continue
        note = "" if frames is jpegs else ("\n\n(Some frames could not be shown; work from what is here.)" if frames
                                          else "\n\n(No frames could be shown; work from the words and the shot list.)")
        message = client.image_message(text + note, frames) if frames else {"role": "user", "content": text + note}
        try:
            return await client.chat_json([{"role": "system", "content": system}, message], schema, max_tokens=max_tokens)
        except Exception as exc:
            if not flagged(exc):
                raise
            last = exc
            log.warning("Vision request flagged by the provider's filter (%d frames); retrying with fewer", len(frames))
    raise last if last else RuntimeError("vision call failed")
