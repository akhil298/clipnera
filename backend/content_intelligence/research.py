from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.logging_config import get_logger

log = get_logger(__name__)


class TopicResearcher:
    def __init__(self, text_client: Any) -> None:
        self._text_client = text_client

    async def research(self, video_path: str, transcript_segments: list[dict[str, Any]]) -> dict[str, Any]:
        transcript = self._format_transcript(transcript_segments)
        current_date = datetime.now(timezone.utc).date().isoformat()
        prompt = f"""You are researching a video for AI clip selection. Use only the supplied transcript and your general knowledge. Do not invent facts or sources.

Current date: {current_date}
Video path: {video_path}

Transcript:
{transcript}

Return only valid JSON with this shape:
{{
  "title": "concise video title",
  "summary": "two or three sentence summary",
  "topics": ["topic"],
  "entities": ["person, organization, or entity"],
  "important_statements": ["statement and timestamp if available"],
  "events": ["event being discussed"],
  "key_moments": ["moment and timestamp if available"],
  "context_required": ["context a viewer needs"],
  "current_relevance": "explain whether the video reacts to a current event and why it matters",
  "research_queries": ["search query for current information"],
  "sources": []
}}

If the video mentions a prime minister or another public official reacting to something happening today, identify the official, event, date, likely significance, and the current information that should be verified. Keep unverified claims clearly marked.
"""
        try:
            response = await self._text_client.chat([
                {"role": "system", "content": "You are a factual video research assistant. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ], temperature=0.1, max_tokens=1800)
            data = self._parse_json(response)
        except Exception as exc:
            log.warning(f"Groq topic research failed: {exc}")
            data = {}

        title = str(data.get("title") or video_path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        return {
            "title": title,
            "summary": str(data.get("summary") or ""),
            "topics": self._string_list(data.get("topics")),
            "entities": self._string_list(data.get("entities")),
            "important_statements": self._string_list(data.get("important_statements")),
            "events": self._string_list(data.get("events")),
            "key_moments": self._string_list(data.get("key_moments")),
            "context_required": self._string_list(data.get("context_required")),
            "current_relevance": str(data.get("current_relevance") or ""),
            "research_queries": self._string_list(data.get("research_queries")),
            "sources": data.get("sources", []) if isinstance(data.get("sources", []), list) else [],
            "research_method": "groq_llm",
            "research_date": current_date,
        }

    @staticmethod
    def _format_transcript(segments: list[dict[str, Any]]) -> str:
        if not segments:
            return "[No transcript segments were supplied.]"
        lines = []
        for segment in segments:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            speaker = segment.get("speaker") or "Unknown speaker"
            text = str(segment.get("text", "")).strip()
            lines.append(f"[{start:.3f}-{end:.3f}] {speaker}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split("\n") if item.strip()]
        return []

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
