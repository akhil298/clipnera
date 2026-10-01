"""Exports must never burn a clip with an empty caption track when its words
were simply missing from the stored transcript."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import clip_generation.service as clip_service
from clip_generation.service import ClipService

WORDS = [{"start": 10.0, "end": 12.0, "text": "hello there", "words": [{"word": "hello", "start": 10.0, "end": 10.5}]}]


def _clip(clip_id: str, transcript: str, start: float = 10.0) -> SimpleNamespace:
    return SimpleNamespace(
        id=clip_id, project_id="p1", title=f"Clip {clip_id}", transcript=transcript,
        start_time=start, end_time=start + 20.0, hook_start=None, hook_end=None, edit_spans=None,
        content_category="podcast", s3_bucket="b", analysis_json=None, editor_settings=None,
    )


class _Repo:
    updates: list[dict] = []

    def __init__(self, session) -> None:
        pass

    async def update_clip(self, **fields):
        _Repo.updates.append(fields)


@asynccontextmanager
async def _session():
    yield None


@pytest.fixture
def service(monkeypatch):
    _Repo.updates = []
    monkeypatch.setattr(clip_service, "ClipRepository", _Repo)
    monkeypatch.setattr(clip_service, "AsyncSessionLocal", _session)

    async def _no_event(*args, **kwargs):
        return None

    monkeypatch.setattr(clip_service, "record_clip_event", _no_event)
    return ClipService.__new__(ClipService)


@pytest.mark.asyncio
async def test_clip_stored_as_empty_list_is_transcribed_not_exported_bare(service, monkeypatch):
    clips = [_clip("empty", "[]"), _clip("ok", clip_service._json_dumps(WORDS))]
    rendered: dict[str, list] = {}
    transcribed: list[str] = []

    async def _selection(*args):
        return clips

    async def _recuts(*args):
        return {}

    @asynccontextmanager
    async def _cut(clip, ratio, recuts):
        yield f"{clip.id}.mp4"

    async def _transcribe(clip, cut_path, user_id, progress_callback=None):
        transcribed.append(clip.id)
        return WORDS

    async def _render(clip, cut_path, **kwargs):
        rendered[clip.id] = kwargs["transcript"]
        return f"/tmp/{clip.id}.mp4"

    async def _store(*args, **kwargs):
        return "https://signed"

    async def _project(*args):
        return SimpleNamespace(id="p1")

    monkeypatch.setattr(service, "_get_project", _project)
    monkeypatch.setattr(service, "_export_selection", _selection)
    monkeypatch.setattr(service, "_recut_missing_ratios", _recuts)
    monkeypatch.setattr(service, "_export_cut", _cut)
    monkeypatch.setattr(service, "_transcribe_clip_cut", _transcribe)
    monkeypatch.setattr(service, "_render_export", _render)
    monkeypatch.setattr(service, "_store_render", _store)
    monkeypatch.setattr(service, "hook_transition_for", lambda clip, config: None)

    await service.export_clips_for_social("p1", "u1", ["tiktok"], aspect_ratio="9:16")

    assert transcribed == ["empty"]  # only the clip with no words
    assert rendered["empty"] == WORDS
    assert rendered["ok"] == WORDS


@pytest.mark.asyncio
async def test_cut_transcript_is_moved_to_source_time_and_saved(service, monkeypatch):
    async def _transcribe(project_id, path, progress_callback=None):
        return [{"start": 0.5, "end": 2.0, "text": "hi", "words": [{"word": "hi", "start": 0.5, "end": 0.9}]}]

    monkeypatch.setattr(service, "_transcribe_if_missing", _transcribe)
    transcript = await service._transcribe_clip_cut(_clip("c1", "[]", start=100.0), "c1.mp4", "u1")

    assert transcript[0]["start"] == 100.5 and transcript[0]["end"] == 102.0
    assert transcript[0]["words"][0]["start"] == 100.5
    assert _Repo.updates[0]["clip_id"] == "c1"
    assert clip_service.json.loads(_Repo.updates[0]["transcript"]) == transcript


def _edited(service, transcript, edits):
    clip = _clip("c1", clip_service._json_dumps(transcript))
    clip.editor_settings = clip_service._json_dumps({"transcript_edits": edits}) if edits is not None else None
    return service._edited_transcript(clip)


SPOKEN = [
    {"start": 10.0, "end": 11.5, "text": "um so grow", "words": [
        {"word": "um", "start": 10.0, "end": 10.2},
        {"word": "so", "start": 10.3, "end": 10.6},
        {"word": "grow", "start": 10.7, "end": 11.5},
    ]},
    {"start": 12.0, "end": 12.4, "text": "uh", "words": [{"word": "uh", "start": 12.0, "end": 12.4}]},
]


def test_no_saved_edits_leaves_the_transcript_alone(service):
    assert _edited(service, SPOKEN, None) == SPOKEN


def test_transcript_edits_cut_words_and_set_emphasis(service):
    edited = _edited(service, SPOKEN, {"removed": [10.0, 12.0], "highlighted": [10.7]})

    assert len(edited) == 1  # the segment whose only word was cut is gone, not burned as text
    assert [w["word"] for w in edited[0]["words"]] == ["so", "grow"]
    assert edited[0]["text"] == "so grow"
    assert [w["highlighted"] for w in edited[0]["words"]] == [False, True]


def test_every_word_cut_does_not_trigger_retranscription(service):
    assert _edited(service, SPOKEN, {"removed": [10.0, 10.3, 10.7, 12.0]}) == []


def _emphasised(words) -> set[str]:
    """Caption words burned in the template's emphasis colour on any line."""
    import os
    import re
    import tempfile

    from subtitle_styling.ass_generator import _hex_to_ass_style, build_ass_file

    # An emphasis colour distinct from the spoken word's, so the two can be told apart.
    overrides = {"emphasis_color": "#FF00FF"}
    emphasis = _hex_to_ass_style(overrides["emphasis_color"])
    with tempfile.TemporaryDirectory() as tmp:
        path = build_ass_file(
            transcript_words=words, clip_start=0.0, clip_end=2.0, style_id="karaoke", style_overrides=overrides,
            width=1080, height=1920, output_path=os.path.join(tmp, "c.ass"),
        )
        text = open(path, encoding="utf-8").read()
    # A word with an emoji is followed by a space and the emoji, not its reset.
    return {word for tag, word in re.findall(r"\{([^}]*)\}([A-Z]+)[ {]", text) if emphasis in tag}


PLAIN = [
    {"text": "this", "start": 0.0, "end": 0.4},
    {"text": "insane", "start": 0.5, "end": 0.9},
    {"text": "trick", "start": 1.0, "end": 1.4},
]


def test_editor_highlights_replace_automatic_emphasis():
    assert _emphasised(PLAIN)  # the burner picks some words by itself
    assert _emphasised([{**w, "highlighted": False} for w in PLAIN]) == set()
    assert _emphasised([{**w, "highlighted": w["text"] == "trick"} for w in PLAIN]) == {"TRICK"}
