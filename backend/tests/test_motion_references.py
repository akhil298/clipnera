from __future__ import annotations

import json

import pytest

from motion_library import references, telegram_inbox
from motion_library.references import ReelError, Reference, reel_id, reel_link, save_reel

REEL = "https://www.instagram.com/reel/DAbc_12-x/?igsh=abc"


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(references, "library_root", lambda: tmp_path)
    return tmp_path


def _fake_download(calls: list[str]):
    def download(url, folder):
        calls.append(url)
        (folder / "reel.mp4").write_bytes(b"video")
        return {"channel": "somecreator", "description": "nice motion", "duration": 12.5}
    return download


class TestLinks:
    def test_link_is_found_inside_a_shared_message(self):
        assert reel_link(f"look at this {REEL} wow") == REEL
        assert reel_link("no link here") is None
        assert reel_link("https://youtube.com/watch?v=abc") is None

    def test_id_comes_from_any_reel_or_post_shape(self):
        assert reel_id(REEL) == "DAbc_12-x"
        assert reel_id("https://instagram.com/someone/reel/XyZ/") == "XyZ"
        assert reel_id("https://www.instagram.com/p/Post1/") == "Post1"
        assert reel_id("https://www.instagram.com/someone/") is None


@pytest.mark.asyncio
class TestSaveReel:
    async def test_reel_is_stored_with_its_notes(self, library, monkeypatch):
        monkeypatch.setattr(references, "_download", _fake_download([]))
        saved = await save_reel(REEL)
        assert saved.new and saved.folder == library / "references" / "DAbc_12-x"
        assert (saved.folder / "reel.mp4").read_bytes() == b"video"
        notes = json.loads((saved.folder / "reference.json").read_text())
        assert notes["source_url"] == REEL and notes["creator"] == "somecreator" and notes["duration_s"] == 12.5
        # Nothing is left behind from the download.
        assert [p.name for p in (library / "references").iterdir()] == ["DAbc_12-x"]

    async def test_same_reel_is_downloaded_once(self, library, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(references, "_download", _fake_download(calls))
        await save_reel(REEL)
        again = await save_reel("https://www.instagram.com/reels/DAbc_12-x/")
        assert not again.new and len(calls) == 1

    async def test_failed_download_leaves_no_folder(self, library, monkeypatch):
        def refuse(url, folder):
            raise ReelError("private")
        monkeypatch.setattr(references, "_download", refuse)
        with pytest.raises(ReelError):
            await save_reel(REEL)
        assert list((library / "references").iterdir()) == []

    async def test_a_profile_link_is_refused(self, library):
        with pytest.raises(ReelError):
            await save_reel("https://www.instagram.com/someone/")


@pytest.mark.asyncio
class TestInbox:
    @pytest.fixture(autouse=True)
    def chats(self, monkeypatch):
        monkeypatch.setattr(telegram_inbox, "_allowed_chats", lambda: {"42"})

    async def test_reel_from_the_owner_is_saved(self, monkeypatch, tmp_path):
        async def save(link):
            return Reference("DAbc_12-x", tmp_path, new=True)
        monkeypatch.setattr(telegram_inbox, "save_reel", save)
        assert await telegram_inbox._answer({"chat": {"id": 42}, "text": REEL}) == "Saved as DAbc_12-x."

    async def test_strangers_get_no_reply_and_no_download(self, monkeypatch):
        async def save(link):
            raise AssertionError("must not download for a stranger")
        monkeypatch.setattr(telegram_inbox, "save_reel", save)
        assert await telegram_inbox._answer({"chat": {"id": 7}, "text": REEL}) is None

    async def test_unconfigured_bot_tells_the_chat_its_id(self, monkeypatch):
        monkeypatch.setattr(telegram_inbox, "_allowed_chats", lambda: set())
        assert "TELEGRAM_ALLOWED_CHAT_IDS=42" in await telegram_inbox._answer({"chat": {"id": 42}, "text": REEL})

    async def test_download_failure_is_reported(self, monkeypatch):
        async def save(link):
            raise ReelError("Instagram would not let me download that reel.")
        monkeypatch.setattr(telegram_inbox, "save_reel", save)
        assert "would not let me" in await telegram_inbox._answer({"chat": {"id": 42}, "text": REEL})
