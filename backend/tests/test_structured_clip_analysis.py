from __future__ import annotations

import pytest

from content_intelligence.highlighter import HighlightDetector
from content_intelligence.reframing import build_smart_output_formats
from content_intelligence.research import TopicResearcher


class FakeGroq:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def chat(self, messages: list[dict], **kwargs) -> str:
        import json

        return json.dumps(self.payload)


def test_smart_output_formats_with_scene_changes() -> None:
    frames = [
        {
            "timestamp": 10.0,
            "subjects": [
                {
                    "label": "Speaker",
                    "confidence": 0.95,
                    "is_speaker": True,
                    "bounding_box": {"x": 0.25, "y": 0.1, "width": 0.3, "height": 0.8},
                }
            ],
            "faces": [],
            "objects": [],
            "description": "Single speaker",
        },
        {
            "timestamp": 14.0,
            "subjects": [
                {
                    "label": "Speaker",
                    "confidence": 0.95,
                    "is_speaker": True,
                    "bounding_box": {"x": 0.55, "y": 0.1, "width": 0.3, "height": 0.8},
                }
            ],
            "faces": [],
            "objects": [],
            "description": "Single speaker moving",
        },
    ]

    outputs = build_smart_output_formats(
        frames, 1920, 1080,
        aspect_ratios=["9:16", "16:9"],
        content_category="unknown",
        scene_changes=[0.0, 16.0],
        video_path=None,
    )

    assert "9:16" in outputs
    assert "16:9" in outputs
    assert outputs["9:16"]["tracking"] is True
    assert outputs["16:9"]["tracking"] is False
    assert outputs["9:16"]["crop"]["height"] == 1.0


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
