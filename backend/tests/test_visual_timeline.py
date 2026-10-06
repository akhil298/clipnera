from __future__ import annotations

import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from content_intelligence.sentences import Sentence
from visual_timeline import attach_scenes, describe_video
from visual_timeline import timeline

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _settings(**changes):
    base = dict(VISUAL_TIMELINE_ENABLED=True, GEMINI_API_KEY="test-key",
                VISUAL_TIMELINE_MODEL="gemini-3.1-flash-lite", VISUAL_TIMELINE_MEDIA_RESOLUTION="MEDIA_RESOLUTION_LOW")
    return SimpleNamespace(**{**base, **changes})


class TestParsing:
    def test_times_become_source_seconds_inside_the_piece(self):
        reply = json.dumps({"moments": [
            {"from": "00:05", "to": "00:12", "shows": "host  holds up a phone"},
            {"from": "1:50", "to": "2:30", "shows": "guest walks out"},
        ]})
        assert timeline.parse_moments(reply, 120.0, 120.0) == [
            {"start": 125.0, "end": 132.0, "shows": "host holds up a phone"},
            {"start": 230.0, "end": 240.0, "shows": "guest walks out"},
        ]

    def test_malformed_entries_are_dropped(self):
        reply = json.dumps({"moments": [{"from": "soon", "to": "00:02", "shows": "x"},
                                        {"from": "00:01", "to": "00:02", "shows": ""}]})
        assert timeline.parse_moments(reply, 0.0, 60.0) == []
        assert timeline.parse_moments("not json", 0.0, 60.0) == []

    def test_cut_off_reply_keeps_its_complete_entries(self):
        reply = ('{"moments": [{"from": "00:00", "to": "00:01", "shows": "host talks"}, '
                 '{"from": "00:01", "to": "00:04", "shows": "An')
        assert timeline.parse_moments(reply, 0.0, 60.0) == [{"start": 0.0, "end": 1.0, "shows": "host talks"}]

    def test_clock_forms(self):
        assert timeline._seconds("01:15") == 75.0
        assert timeline._seconds("1:02:03") == 3723.0
        assert timeline._seconds("42") == 42.0


class TestChunks:
    def test_pieces_cover_the_video_and_absorb_a_short_tail(self):
        assert timeline.chunks(250.0) == [(0.0, 120.0), (120.0, 130.0)]
        assert timeline.chunks(300.0) == [(0.0, 120.0), (120.0, 120.0), (240.0, 60.0)]


class TestAttach:
    def test_each_line_gets_what_is_on_screen_while_it_is_spoken(self):
        sentences = [Sentence(1, 0.0, 4.0, "Look at this."), Sentence(2, 4.0, 9.0, "It is tiny."),
                     Sentence(3, 30.0, 32.0, "Anyway.")]
        attach_scenes(sentences, [{"start": 0.0, "end": 5.0, "shows": "host holds up a phone"},
                                  {"start": 5.0, "end": 10.0, "shows": "close-up of the phone"}])
        assert sentences[0].scene == "host holds up a phone"
        assert sentences[1].scene == "host holds up a phone; close-up of the phone"
        assert sentences[2].scene == ""
        assert sentences[0].line() == "1 0.0 - [sees: host holds up a phone] Look at this."
        assert sentences[2].line() == "3 30.0 - Anyway."


class TestDescribe:
    @pytest.mark.asyncio
    async def test_disabled_or_keyless_does_nothing(self, monkeypatch):
        for settings in (_settings(VISUAL_TIMELINE_ENABLED=False), _settings(GEMINI_API_KEY="")):
            monkeypatch.setattr(timeline, "get_settings", lambda s=settings: s)
            assert await describe_video("missing.mp4", 600.0) == []

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
    async def test_pieces_are_described_and_costed(self, monkeypatch, tmp_path):
        source = tmp_path / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=640x360:rate=25:duration=30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(source)], check=True)
        monkeypatch.setattr(timeline, "get_settings", _settings)
        monkeypatch.setattr(timeline, "CHUNK_SECONDS", 15.0)
        monkeypatch.setattr(timeline, "MIN_CHUNK_SECONDS", 5.0)
        requests, costs = [], []
        reply = json.dumps({"moments": [{"from": "00:00", "to": "00:15", "shows": "colour bars"}]})

        class FakeClient:
            def __init__(self, **_):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, url, headers, **body):
                requests.append((url, body["json"]))
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"candidates": [{"content": {"parts": [{"text": reply}]}}],
                                  "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 40}},
                )

        async def record(provider, model, **usage):
            costs.append((provider, model, usage["input_tokens"], usage["output_tokens"]))
            return 0.0

        monkeypatch.setattr(timeline.httpx, "AsyncClient", FakeClient)
        monkeypatch.setattr(timeline, "record_llm_call", record)

        moments = await describe_video(str(source), 30.0)
        assert [m["start"] for m in moments] == [0.0, 15.0]
        assert len(requests) == 2 and "gemini-3.1-flash-lite" in requests[0][0]
        config = requests[0][1]["generationConfig"]
        assert config["mediaResolution"] == "MEDIA_RESOLUTION_LOW"
        assert requests[0][1]["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "video/mp4"
        assert costs == [("gemini", "gemini-3.1-flash-lite", 1000, 40)] * 2

    @pytest.mark.asyncio
    async def test_a_failing_piece_yields_fewer_notes_not_an_error(self, monkeypatch):
        monkeypatch.setattr(timeline, "get_settings", _settings)

        async def boom(*_):
            raise RuntimeError("provider down")

        monkeypatch.setattr(timeline, "_describe_chunk", boom)
        assert await describe_video("any.mp4", 60.0) == []
