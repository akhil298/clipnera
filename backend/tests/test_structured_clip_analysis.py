from __future__ import annotations

import pytest

from content_intelligence.highlighter import HighlightDetector
from content_intelligence.reframing import (
    build_crop_tracking,
    build_output_formats,
    crop_for_subject,
    normalize_box,
)
from content_intelligence.research import TopicResearcher


class FakeGroq:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def chat(self, messages: list[dict], **kwargs) -> str:
        import json

        return json.dumps(self.payload)


def test_crop_for_subject_keeps_speaker_inside_vertical_frame() -> None:
    frame = {
        "subjects": [
            {
                "label": "Prime Minister",
                "confidence": 0.98,
                "is_speaker": True,
                "bounding_box": {"x": 0.35, "y": 0.12, "width": 0.28, "height": 0.72},
            }
        ]
    }

    crop = crop_for_subject(frame, 1920, 1080, "9:16")

    assert crop["height"] == 1.0
    assert crop["width"] == pytest.approx(608 / 1920, abs=0.001)
    assert crop["x"] >= 0
    assert crop["x"] + crop["width"] >= 0.49
    assert crop["x"] <= 0.49


def test_crop_tracking_and_output_formats_are_normalized() -> None:
    frames = [
        {
            "timestamp": 10.0,
            "subjects": [
                {
                    "label": "Speaker",
                    "confidence": 0.95,
                    "bounding_box": {"x": 0.25, "y": 0.1, "width": 0.3, "height": 0.8},
                }
            ],
        },
        {
            "timestamp": 14.0,
            "subjects": [
                {
                    "label": "Speaker",
                    "confidence": 0.95,
                    "bounding_box": {"x": 0.55, "y": 0.1, "width": 0.3, "height": 0.8},
                }
            ],
        },
    ]

    tracking = build_crop_tracking(frames, 1920, 1080, "9:16")
    outputs = build_output_formats(frames, 1920, 1080)

    assert len(tracking) == 2
    assert tracking[0]["bbox"]["x"] < tracking[1]["bbox"]["x"]
    assert outputs["9:16"]["tracking"] is True
    assert outputs["16:9"]["tracking"] is False
    assert normalize_box(outputs["9:16"]["crop"])["height"] == 1.0


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
