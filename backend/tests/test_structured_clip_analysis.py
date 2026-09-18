from __future__ import annotations

import pytest

from content_intelligence.highlighter import HighlightDetector
from content_intelligence.research import TopicResearcher


class FakeGroq:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def chat(self, messages: list[dict], **kwargs) -> str:
        import json

        return json.dumps(self.payload)


@pytest.mark.asyncio
async def test_research_uses_groq_response() -> None:
    researcher = TopicResearcher(FakeGroq({
        "title": "PM responds to announcement",
        "topics": ["Government", "Announcement"],
        "current_relevance": "Current reaction",
        "sources": [],
    }))

    result = await researcher.research("video.mp4", [])

    assert result["title"] == "PM responds to announcement"
    assert result["topics"] == ["Government", "Announcement"]
    assert result["research_method"] == "groq_llm"


@pytest.mark.asyncio
async def test_highlight_detector_uses_exact_llm_timestamps(monkeypatch) -> None:
    detector = HighlightDetector(FakeGroq({
        "moments": [
            {
                "start_time": 12.5,
                "end_time": 42.0,
                "title": "Key response",
                "reason": "Standalone statement",
                "score": 0.94,
                "scores": {"relevance": 0.96},
            }
        ]
    }))
    monkeypatch.setattr(detector, "_probe_duration", lambda video_path: 100.0)
    transcript = [
        {"start": 0.0, "end": 50.0, "text": "Important statement", "speaker": "Speaker 1"}
    ]

    highlights = await detector.detect("video.mp4", transcript, {"classification": {"category": "news_politics"}})

    assert highlights[0]["start_time"] == 12.5
    assert highlights[0]["end_time"] == 42.0
    assert highlights[0]["score"] == pytest.approx(0.94)
