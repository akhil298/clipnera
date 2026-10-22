"""When a file arrives the AI describes it; the strongest moments are picked only when an edit asks.

Skipped unless TEST_DATABASE_URL points at a disposable database (see test_editor_db.py).
"""

from __future__ import annotations

import pytest

from auth.model import User
from editor.schema import EditorProjectCreate
from editor.service import EditorService
from understanding import reading, service as understanding_service
from understanding.findings import findings_of
from understanding.model import AnalysisStatus, MediaAnalysis
from understanding.mud import MUD
from understanding.service import UnderstandingService
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")


def _mud() -> MUD:
    words = [{"i": n, "t0": n * 0.5, "t1": n * 0.5 + 0.4, "text": w} for n, w in enumerate("We went from 200 to 40,000 followers .".split())]
    return MUD.model_validate({
        "asset_id": "a1", "kind": "video", "duration": 10.0, "words": words,
        "utterances": [{"id": "u0", "w0": 0, "w1": len(words) - 1, "t0": 0.0, "t1": words[-1]["t1"], "text": "We went from 200 to 40,000 followers."}],
        "chapters": [{"t0": 0.0, "t1": 4.0, "text": "She explains how her account grew"}],
    })


def test_the_card_says_what_happens_not_which_parts_are_best():
    found = findings_of(_mud())
    assert [(c.t0, c.text) for c in found.chapters] == [(0.0, "She explains how her account grew")]
    assert "moments" not in found.model_dump()


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get_object(self, bucket: str, key: str) -> bytes:
        return self.objects[key]

    def put_object(self, bucket: str, key: str, body, ContentType: str = "") -> None:  # noqa: N803
        self.objects[key] = body.encode() if isinstance(body, str) else body


@pytest.mark.asyncio
async def test_moments_are_picked_once_when_an_edit_asks_and_kept(db, monkeypatch) -> None:
    s3 = FakeS3()
    s3.objects["editor/u/p/a.mud.json"] = _mud().model_dump_json().encode()
    calls = []

    async def pick_moments(utterances):
        calls.append(len(utterances))
        return reading.Picks(moments=[reading.Pick(first="u0", last="u0", score=0.9, why="a surprising number")])

    monkeypatch.setattr(reading, "pick_moments", pick_moments)
    understanding_service._cache.clear()
    async with db() as session:
        owner = User(email="moments@example.com", full_name="M", is_verified=True)
        session.add(owner)
        await session.commit()
        project = await EditorService(session).create(owner.id, EditorProjectCreate())
        session.add(MediaAnalysis(project_id=project.id, user_id=owner.id, asset_id="a1", asset_key="editor/u/p/a.mp4", kind="video",
                                  status=AnalysisStatus.READY, mud_key="editor/u/p/a.mud.json"))
        await session.commit()
        service = UnderstandingService(session, s3)
        # Arriving: no moments were picked.
        assert (await service.muds(project.id))["a1"].moments == []
        first = (await service.ensure_moments(project.id))["a1"]
        again = (await service.ensure_moments(project.id))["a1"]
    assert calls == [1]
    assert [m.why for m in first.moments][:1] == ["a surprising number"] and again.moments == first.moments
    saved = MUD.model_validate_json(s3.objects["editor/u/p/a.mud.json"])
    assert saved.analyzers["moments"] == "ok" and saved.moments
