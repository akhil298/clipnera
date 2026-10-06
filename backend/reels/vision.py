"""What each of a creator's images shows, so the planner can put it in the right scene.

Free runs on Groq's Qwen vision model, Pro on the deployment's OpenAI model; both read the
image and answer in one short JSON object.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from groq import AsyncGroq

from clients.ai import OpenAI
from clients.ai.base import reply_text
from core.config import get_settings
from core.logging_config import get_logger
from usage.recorder import record_llm_call

log = get_logger(__name__)

FREE_MODEL = "qwen/qwen3.8-27b"
PROMPT = (
    'Describe this image for a video editor in JSON only: {"description": "one sentence of what it shows", '
    '"tags": ["3-8 lowercase nouns"], "role": "product|person|place|screenshot|chart|food|other"}. /no_think'
)


def parse(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        return {"description": text.strip()[:200], "tags": [], "role": "other"}
    return {
        "description": str(data.get("description", ""))[:300],
        "tags": [str(t).lower()[:40] for t in data.get("tags") or []][:8],
        "role": str(data.get("role") or "other")[:20],
    }


async def describe_image(image: bytes, media_type: str, is_pro: bool) -> dict[str, Any]:
    """Description, tags and role of one image; a failed call returns an empty description."""
    settings = get_settings()
    encoded = base64.b64encode(image).decode()
    started = time.monotonic()
    content = [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
    ]
    try:
        if is_pro and settings.OPENAI_API_KEY:
            async with OpenAI() as client:
                return parse(await client.chat([{"role": "user", "content": content}], max_tokens=300))
        response = await AsyncGroq(api_key=settings.GROQ_API_KEY).chat.completions.create(
            model=FREE_MODEL, max_tokens=600, temperature=0.2, messages=[{"role": "user", "content": content}],
        )
        usage = response.usage
        await record_llm_call("groq", FREE_MODEL, input_tokens=getattr(usage, "prompt_tokens", 0),
                              output_tokens=getattr(usage, "completion_tokens", 0), latency_ms=int((time.monotonic() - started) * 1000),
                              response=reply_text(response))
        return parse(response.choices[0].message.content or "")
    except Exception as exc:
        log.warning("Image description failed: %s", exc)
        return {"description": "", "tags": [], "role": "other"}
