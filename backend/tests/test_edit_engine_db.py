"""A footage reel end to end against a real Postgres and real FFmpeg, with S3 and the AI calls faked.

Skipped unless TEST_DATABASE_URL points at a disposable database (every table
in it is dropped and recreated), e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clipnera_edit_test pytest tests/test_edit_engine_db.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import edit_engine.jobs as jobs
import edit_engine.service as service_module
import notifications.service as notifications
from auth.model import User
from core.exceptions import CustomException
from edit_engine import vision
from edit_engine.model import EditProject, EditStatus, MusicTrack
from edit_engine.schema import EditChange, EditCreateRequest, EditSourceFile, EditSourcesCompleteRequest, EditSourcesInitRequest
from edit_engine.service import EditService
from subscription.service import SubscriptionService
from test_plans_db import TEST_DATABASE_URL, db  # noqa: F401  the shared database fixture

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg"),
]

SPOKEN = "Stop buying cheap running shoes. They hurt your knees. Buy one proper pair instead."


class FakeS3:
    """S3 on local disk: presigned URLs are paths, uploads and downloads are copies."""

    root: Path

    def __init__(self, *args, **kwargs) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def presign_put(self, bucket, key, content_type, expires_in=3600):
        return f"file://{self._path(key)}"

    def generate_presigned_url(self, bucket, key, expires_in=3600, **kwargs):
        return f"file://{self._path(key)}"

    def object_size(self, bucket, key):
        return self._path(key).stat().st_size

    def download_file(self, bucket, key, file_path):
        shutil.copy(self._path(key), file_path)

    def upload_file(self, bucket, key, file_path, content_type=None, callback=None):
        shutil.copy(file_path, self._path(key))

    def put_object(self, bucket, key, body, **kwargs):
        self._path(key).write_bytes(body if isinstance(body, bytes) else body.encode())


class FakeDirector:
    model = "fake-director"
    # The last footage log the director was given.
    seen = ""

    async def chat(self, messages, **kwargs):
        text = FakeDirector.seen = messages[-1]["content"]
        # Keep every sentence the log offers, put a pop-up on the last and B-roll on the second.
        ids = [line.split(" | ")[0] for line in text.splitlines() if line.startswith("s") and " | " in line]
        return json.dumps({
            "title": "Shoe advice", "hook": "Stop buying these", "content_type": "talking_head", "sentences": ids,
            "broll": [{"sentence": ids[1], "visual": "p0"}] if len(ids) > 1 else [],
            "pops": [{"sentence": ids[-1], "text": "One pair"}], "punch_ins": [], "montage": [],
            "music_mood": "chill", "energy": "medium", "look": "warm_film", "caption": "Save your knees", "hashtags": ["running"],
        })


def _media(folder: Path) -> tuple[Path, Path]:
    video, photo = folder / "talk.mp4", folder / "shoes.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=9",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=9", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(video)], check=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "smptebars=size=800x600",
                    "-frames:v", "1", str(photo)], check=True)
    return video, photo


def _words() -> list[dict]:
    return [{"word": w, "start": round(0.3 + i * 0.5, 2), "end": round(0.3 + i * 0.5 + 0.4, 2)} for i, w in enumerate(SPOKEN.split())]


@pytest.fixture
def world(db, monkeypatch, tmp_path):  # noqa: F811
    FakeS3.root = tmp_path / "s3"
    queued = []

    class Queue:
        async def enqueue(self, job):
            queued.append(job)

    async def transcribe(self, path, duration, language=None, prompt=None):
        return [{"text": SPOKEN, "words": _words()}], "en"

    async def caption_sheet(sheet):
        return {1: "coloured test pattern"}

    async def describe_image(image, media_type, is_pro):
        return {"description": "red running shoes", "tags": ["shoes"], "role": "product"}

    for module in (jobs, notifications):
        monkeypatch.setattr(module, "AsyncSessionLocal", db)
    monkeypatch.setattr(jobs, "S3", FakeS3)
    monkeypatch.setattr(jobs, "get_queue", lambda: Queue())
    monkeypatch.setattr(service_module, "get_queue", lambda: Queue())
    background = []
    monkeypatch.setattr(service_module, "in_background", background.append)
    monkeypatch.setattr(jobs.GroqWhisperTranscriber, "__init__", lambda self, model=None: None)
    monkeypatch.setattr(jobs.GroqWhisperTranscriber, "transcribe", transcribe)
    monkeypatch.setattr(vision, "caption_sheet", caption_sheet)
    monkeypatch.setattr(jobs, "describe_image", describe_image)
    monkeypatch.setattr(jobs.director, "director_client", lambda is_pro, opus, model=None, effort=None: FakeDirector())
    return {"db": db, "queued": queued, "background": background, "tmp": tmp_path}


async def _user(maker) -> str:
    async with maker() as session:
        user = User(email="creator@example.com")
        session.add(user)
        await session.commit()
        await SubscriptionService.for_session(session).activate_free_plan(user.id)
        return user.id


async def _run(world) -> None:
    while world["background"]:
        await world["background"].pop(0)
    while world["queued"]:
        job = world["queued"].pop(0)
        await {jobs.ANALYZE_JOB: jobs.analyze_edit, jobs.PLAN_JOB: jobs.plan_edit, jobs.RENDER_JOB: jobs.render_edit}[job.kind](job)


async def _uploaded_edit(world, script: str | None, reference: bool = False, **request) -> tuple[str, str]:
    """A reel with a talking video and a photo (and the same video again as a reference reel), analysed and planned."""
    maker = world["db"]
    user_id = await _user(maker)
    video, photo = _media(world["tmp"])
    files = [
        EditSourceFile(filename="talk.mp4", content_type="video/mp4", size_bytes=video.stat().st_size, duration_s=9),
        EditSourceFile(filename="shoes.jpg", content_type="image/jpeg", size_bytes=photo.stat().st_size),
    ]
    if reference:
        files.append(EditSourceFile(filename="style.mp4", content_type="video/mp4", size_bytes=video.stat().st_size,
                                    duration_s=9, reference=True))
    async with maker() as session:
        service = EditService(session, FakeS3())
        edit = await service.create(user_id, EditCreateRequest(title="Untitled reel", script=script, **request))
        uploads = await service.init_sources(user_id, edit.id, EditSourcesInitRequest(files=files))
        for upload, local in zip(uploads.uploads, (video, photo, video)):
            shutil.copy(local, upload.url.removeprefix("file://"))
        await service.complete_sources(user_id, edit.id, EditSourcesCompleteRequest(keys=[u.key for u in uploads.uploads]))
        await service.analyze(user_id, edit.id)
    await _run(world)
    return user_id, edit.id


async def test_footage_to_rendered_reel(world):
    maker = world["db"]
    user_id, edit_id = await _uploaded_edit(world, script=None)
    async with maker() as session:
        service = EditService(session, FakeS3())
        edit = await service.get(user_id, edit_id)
        assert edit.status == "planned", edit.error
        assert edit.title == "Shoe advice"
        assert edit.plan.script_mode == "none" and edit.plan.layout == "talking"
        assert edit.plan.hook == "Stop buying these" and edit.plan.look == "warm_film"
        assert edit.plan.broll_count == 1 and edit.plan.pop_count == 1
        assert [w.word for w in edit.timeline.words][:2] == ["Stop", "buying"]
        assert edit.sources[0].url and edit.sources[0].url.endswith("_proxy.mp4")
        assert edit.credits_estimate == 6 + 3 + 1  # base + ceil(~8 s / 3) + 1 raw minute

        edit = await service.apply_changes(user_id, edit_id, [
            EditChange(op="set_hook", value="Save your knees"), EditChange(op="set_look", value="vivid"),
            EditChange(op="remove_line", value="s1"),
        ])
        assert edit.plan.hook == "Save your knees" and edit.plan.look == "vivid"
        assert "s1" in [line.id for line in edit.plan.removed_lines]
        assert "They" not in [w.word for w in edit.timeline.words]

        edit = await service.render(user_id, edit_id)
        assert edit.status == "rendering"
    await _run(world)

    async with maker() as session:
        service = EditService(session, FakeS3())
        edit = await service.get(user_id, edit_id)
        assert edit.status == "done", edit.error
        assert Path(edit.output_url.removeprefix("file://")).stat().st_size > 10_000
        assert await SubscriptionService.for_session(session).get_user_credit_balance(user_id) == 20 - edit.credits_charged
        # A re-render after edits costs a quarter.
        assert edit.credits_estimate == 3


async def test_spoken_script_is_followed_and_missing_lines_are_flagged(world):
    maker = world["db"]
    script = "They hurt your knees. Stop buying cheap running shoes. Follow for more."
    user_id, edit_id = await _uploaded_edit(world, script=script)
    async with maker() as session:
        edit = await EditService(session, FakeS3()).get(user_id, edit_id)
    assert edit.plan.script_mode == "spoken"
    assert edit.plan.script_lines_found == 2 and edit.plan.missing_lines == ["Follow for more."]
    # Script order, not recording order; the unscripted line is offered for restoring.
    assert [w.word for w in edit.timeline.words][:3] == ["They", "hurt", "your"]
    assert [line.text for line in edit.plan.removed_lines] == ["Buy one proper pair instead."]
    assert edit.timeline.picture[-1].kind == "card" and edit.timeline.picture[-1].text == "Follow for more."


async def test_failed_render_is_refunded(world, monkeypatch):
    maker = world["db"]
    user_id, edit_id = await _uploaded_edit(world, script=None)

    async def broken(*args, **kwargs):
        raise RuntimeError("encoder crashed")

    monkeypatch.setattr(jobs.render, "render", broken)
    async with maker() as session:
        await EditService(session, FakeS3()).render(user_id, edit_id)
    await _run(world)
    async with maker() as session:
        edit = await session.get(EditProject, edit_id)
        assert edit.status == EditStatus.PLANNED and "refunded" in edit.error
        assert edit.credits_charged == 0
        assert await SubscriptionService.for_session(session).get_user_credit_balance(user_id) == 20


async def test_free_plan_limits(world):
    maker = world["db"]
    user_id = await _user(maker)
    async with maker() as session:
        service = EditService(session, FakeS3())
        with pytest.raises(CustomException) as too_long:
            await service.create(user_id, EditCreateRequest(target_seconds=90))
        assert too_long.value.status_code == 403
        edit = await service.create(user_id, EditCreateRequest())
        with pytest.raises(CustomException) as footage:
            await service.init_sources(user_id, edit.id, EditSourcesInitRequest(files=[
                EditSourceFile(filename="long.mp4", content_type="video/mp4", size_bytes=10, duration_s=600)]))
        assert footage.value.code == "FOOTAGE_LIMIT"


async def test_music_licence_is_recorded_and_pulled_tracks_are_dropped(world, monkeypatch):
    maker = world["db"]
    music = world["tmp"] / "track.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=20",
                    str(music)], check=True)

    async def snapshot(url):
        return b"<html>CC BY 4.0</html>"

    monkeypatch.setattr(service_module.MusicLibraryService, "_snapshot", staticmethod(snapshot))
    async with maker() as session:
        admin = User(email="admin@example.com")
        session.add(admin)
        await session.commit()
        library = service_module.MusicLibraryService(session, FakeS3())
        fields = {"title": "Morning Run", "artist": "Jane Doe", "source": "fma", "source_url": "https://example.com/t/1",
                  "source_id": "1", "licence": "CC-BY-4.0", "mood": "chill", "commercial_ok": True, "edit_ok": True,
                  "energy": 0.4, "bpm": 100.0, "credit_text": ""}
        track = await library.add(admin.id, music.read_bytes(), "track.mp3", fields)
        assert track.credit_text.startswith("Music: “Morning Run” by Jane Doe, CC BY 4.0")
        with pytest.raises(CustomException):
            await library.add(admin.id, music.read_bytes(), "track.mp3", fields)  # the same file twice
        with pytest.raises(CustomException):
            await library.add(admin.id, b"x" * 100, "other.mp3", {**fields, "licence": "CC-BY-NC-4.0"})

    user_id, edit_id = await _uploaded_edit(world, script=None)
    async with maker() as session:
        service = EditService(session, FakeS3())
        edit = await service.get(user_id, edit_id)
        assert edit.plan.music and edit.plan.music.licence == "CC-BY-4.0"
        await service.render(user_id, edit_id)
    await _run(world)
    async with maker() as session:
        edit = await EditService(session, FakeS3()).get(user_id, edit_id)
        assert edit.status == "done" and edit.music_credit.startswith("Music: “Morning Run”")
        pulled = await service_module.MusicLibraryService(session, FakeS3()).set_status(track.id, "pulled")
        assert pulled.used_by == 1
        assert (await session.get(MusicTrack, track.id)).status.value == "pulled"


async def test_short_credits_keep_the_plan_and_the_days_renders(world):
    maker = world["db"]
    user_id, edit_id = await _uploaded_edit(world, script=None)
    async with maker() as session:
        subscriptions = SubscriptionService.for_session(session)
        await subscriptions.deduct_credits(user_id=user_id, amount=15, reason="spent elsewhere")
        with pytest.raises(CustomException) as short:
            await EditService(session, FakeS3()).render(user_id, edit_id)
        assert short.value.status_code == 402 and short.value.extra == {"required": 10}
        summary = await subscriptions.get_plan_summary(user_id)
        assert summary.usage_today.get("reel_renders", 0) == 0
        assert (await session.get(EditProject, edit_id)).status == EditStatus.PLANNED


async def test_retrying_a_failed_analysis_is_free(world, monkeypatch):
    maker = world["db"]

    real_probe = jobs.perception.probe_media
    broken = {"on": True}

    async def probe(path):
        if broken["on"]:
            raise ValueError("not a video")
        return await real_probe(path)

    monkeypatch.setattr(jobs.perception, "probe_media", probe)
    user_id, edit_id = await _uploaded_edit(world, script=None)
    async with maker() as session:
        edit = await session.get(EditProject, edit_id)
        assert edit.status == EditStatus.FAILED and "not a video" in edit.error
        # Free allows one new footage reel a day; the retry must not be refused for it.
        broken["on"] = False
        await EditService(session, FakeS3()).analyze(user_id, edit_id)
    await _run(world)
    async with maker() as session:
        assert (await session.get(EditProject, edit_id)).status == EditStatus.PLANNED


async def test_reference_reel_guides_the_director_and_is_not_footage(world, monkeypatch):
    async def ask_sheet(sheet, prompt, max_tokens=700):
        return '{"style": "Big yellow captions, fast punch-ins.", "energy": "high"}'

    monkeypatch.setattr(vision, "ask_sheet", ask_sheet)
    user_id, edit_id = await _uploaded_edit(world, script=None, reference=True)
    async with world["db"]() as session:
        edit = await EditService(session, FakeS3()).get(user_id, edit_id)
    assert edit.status == "planned", edit.error
    assert edit.reference and edit.reference.style == "Big yellow captions, fast punch-ins." and edit.reference.energy == "high"
    assert edit.reference_error is None
    assert [s.kind for s in edit.sources] == ["video", "image", "reference"]
    assert edit.raw_seconds < 10  # the reference is studied, not counted as footage
    assert "REFERENCE REEL: 9 s" in FakeDirector.seen and "Big yellow captions" in FakeDirector.seen


async def test_a_reference_link_that_fails_is_skipped_not_fatal(world, monkeypatch):
    async def download(url, folder):
        raise ValueError("the reference link is longer than 3 minutes")

    monkeypatch.setattr(jobs.reference, "download", download)
    user_id, edit_id = await _uploaded_edit(world, script=None, reference_url="https://youtu.be/abcdefghijk")
    async with world["db"]() as session:
        edit = await EditService(session, FakeS3()).get(user_id, edit_id)
    assert edit.status == "planned" and edit.reference is None
    assert edit.reference_url == "https://youtu.be/abcdefghijk"
    assert "longer than 3 minutes" in edit.reference_error


async def test_reference_and_model_rules(world, monkeypatch):
    maker = world["db"]
    user_id = await _user(maker)
    monkeypatch.setattr(service_module, "selectable_models", lambda: ["gpt-6-astra-1"])
    async with maker() as session:
        service = EditService(session, FakeS3())
        with pytest.raises(CustomException) as unknown:
            await service.create(user_id, EditCreateRequest(ai_model="gpt-0"))
        assert unknown.value.code == "UNKNOWN_MODEL"
        with pytest.raises(CustomException) as free:
            await service.create(user_id, EditCreateRequest(ai_model="gpt-6-astra-1", ai_effort="high"))
        assert free.value.code == "PRO_REQUIRED"
        with pytest.raises(CustomException):
            await service.create(user_id, EditCreateRequest(reference_url="https://www.instagram.com/reel/abc/"))
        edit = await service.create(user_id, EditCreateRequest())
        style = dict(content_type="video/mp4", size_bytes=10, duration_s=20, reference=True)
        with pytest.raises(CustomException):
            await service.init_sources(user_id, edit.id, EditSourcesInitRequest(files=[
                EditSourceFile(filename="a.mp4", **style), EditSourceFile(filename="b.mp4", **style)]))
        with pytest.raises(CustomException):
            await service.init_sources(user_id, edit.id, EditSourcesInitRequest(files=[
                EditSourceFile(filename="long.mp4", **{**style, "duration_s": 600})]))


def _youtube(monkeypatch, world, duration: float = 9.0) -> None:
    """YouTube faked: the link reads as a public video of ``duration`` seconds and downloads as the test clip."""
    from clip.youtube_service import PrefetchResult, YouTubeService

    video, _ = _media(world["tmp"])

    async def fetch_metadata(self, url):
        return PrefetchResult(title="How I train for a marathon", duration=duration, uploader="Runner", thumbnail=None, qualities=[])

    async def download_for_edit(self, url, folder, max_seconds):
        shutil.copy(video, folder / "source.mp4")
        return folder / "source.mp4", "How I train for a marathon"

    import clip.source_video

    monkeypatch.setattr(clip.source_video, "DOWNLOAD_DIR", world["tmp"] / "downloads")
    monkeypatch.setattr(YouTubeService, "fetch_metadata", fetch_metadata)
    monkeypatch.setattr(YouTubeService, "download_for_edit", download_for_edit)


async def test_a_youtube_link_alone_is_fetched_and_edited(world, monkeypatch):
    _youtube(monkeypatch, world)
    maker = world["db"]
    user_id = await _user(maker)
    link = "https://www.youtube.com/watch?v=abcdefghijk"
    async with maker() as session:
        service = EditService(session, FakeS3())
        created = await service.create(user_id, EditCreateRequest(source_url=link, language="auto"))
        assert created.title == "How I train for a marathon" and created.source_url == link
        started = await service.analyze(user_id, created.id)
        assert started.status == "analyzing" and len(world["background"]) == 1 and not world["queued"]
    await _run(world)
    async with maker() as session:
        edit = await EditService(session, FakeS3()).get(user_id, created.id)
    assert edit.status == "planned", edit.error
    assert [s.kind for s in edit.sources] == ["video"] and edit.sources[0].name == "How I train for a marathon"
    assert 8 < edit.raw_seconds < 10


async def test_youtube_links_are_checked_when_the_reel_is_made(world, monkeypatch):
    _youtube(monkeypatch, world, duration=3600)
    maker = world["db"]
    user_id = await _user(maker)
    async with maker() as session:
        service = EditService(session, FakeS3())
        with pytest.raises(CustomException) as long:
            await service.create(user_id, EditCreateRequest(source_url="https://youtu.be/abcdefghijk"))
        assert long.value.code == "FOOTAGE_LIMIT" and "60 minutes" in long.value.message
        with pytest.raises(CustomException):
            await service.create(user_id, EditCreateRequest(source_url="https://vimeo.com/123"))
        empty = await service.create(user_id, EditCreateRequest())
        with pytest.raises(CustomException) as nothing:
            await service.analyze(user_id, empty.id)
        assert "YouTube link" in nothing.value.message


async def test_a_youtube_fetch_that_fails_leaves_a_clear_reason(world, monkeypatch):
    _youtube(monkeypatch, world)
    from clip.youtube_service import YouTubeService

    async def broken(self, url, folder, max_seconds):
        raise RuntimeError("HTTP Error 403")

    monkeypatch.setattr(YouTubeService, "download_for_edit", broken)
    maker = world["db"]
    user_id = await _user(maker)
    async with maker() as session:
        service = EditService(session, FakeS3())
        created = await service.create(user_id, EditCreateRequest(source_url="https://youtu.be/abcdefghijk"))
        await service.analyze(user_id, created.id)
    await _run(world)
    async with maker() as session:
        edit = await EditService(session, FakeS3()).get(user_id, created.id)
    assert edit.status == "failed" and "couldn't fetch your YouTube video" in edit.error


async def test_a_youtube_bot_block_says_so(world, monkeypatch):
    _youtube(monkeypatch, world)
    from clip.youtube_service import YouTubeService

    async def blocked(self, url, folder, max_seconds):
        raise RuntimeError("ERROR: [youtube] abc: Sign in to confirm you're not a bot.")

    monkeypatch.setattr(YouTubeService, "download_for_edit", blocked)
    maker = world["db"]
    user_id = await _user(maker)
    async with maker() as session:
        service = EditService(session, FakeS3())
        created = await service.create(user_id, EditCreateRequest(source_url="https://youtu.be/abcdefghijk"))
        await service.analyze(user_id, created.id)
    await _run(world)
    async with maker() as session:
        edit = await EditService(session, FakeS3()).get(user_id, created.id)
    assert edit.status == "failed" and "blocking our server" in edit.error and "upload the video file" in edit.error
