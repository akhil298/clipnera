"""Generated photos for inserts: an exact picture of the thing said when no public-domain photo shows it.

Off unless ``REEL_IMAGE_PROVIDER`` is set ("gemini" or "openai"). Each image is a plain photographic still in 9:16,
made from the insert's search words, with no text, logos or real people; it is ours, so it goes into the asset
registry and later reels reuse it before anything is generated again.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from core.config import get_settings
from core.logging_config import get_logger

log = get_logger(__name__)

PROMPT = ("A natural, photorealistic vertical photo of {subject}. Real-world lighting, shallow depth of field, editorial "
          "stock-photo quality. No text, no letters, no logos, no watermarks, no recognisable real people.")


def enabled() -> bool:
    settings = get_settings()
    return bool(settings.REEL_IMAGE_PROVIDER) and bool(settings.GEMINI_API_KEY if settings.REEL_IMAGE_PROVIDER == "gemini"
                                                        else settings.IMAGE_MODEL)


async def generate(subject: str, out: Path) -> Path | None:
    """A generated photo of ``subject`` at ``out``, or None when off or it fails (the caller falls back)."""
    settings = get_settings()
    prompt = PROMPT.format(subject=subject.strip())
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if settings.REEL_IMAGE_PROVIDER == "gemini":
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_IMAGE_MODEL}:generateContent",
                    headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}})
                response.raise_for_status()
                part = next(p for p in response.json()["candidates"][0]["content"]["parts"] if "inlineData" in p)
                data = base64.b64decode(part["inlineData"]["data"])
            elif settings.REEL_IMAGE_PROVIDER == "openai":
                from clients.ai.openai import OpenAI

                response = await client.post(f"{OpenAI.BASE_URL.rstrip('/')}/images/generations",
                                             headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                                             json={"model": settings.IMAGE_MODEL, "prompt": prompt, "size": "1024x1536", "n": 1,
                                                   "quality": "medium", "output_format": "jpeg"})
                response.raise_for_status()
                data = base64.b64decode(response.json()["data"][0]["b64_json"])
            else:
                return None
    except Exception as exc:  # a picture that cannot be made is left to the kit-object fallback
        log.warning("Generated image failed for %r: %s", subject, str(exc)[:200])
        return None
    out.write_bytes(data)
    return out
