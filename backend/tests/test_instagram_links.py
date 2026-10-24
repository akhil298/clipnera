"""Instagram reel links in the reel maker: recognised, checked at create, and named in messages."""

from __future__ import annotations

import asyncio

import pytest

from clip import instagram_service
from clip.instagram_service import InstagramVideo, is_instagram_link, link_name
from core.exceptions import CustomException
from edit_engine.service import EditService


@pytest.mark.parametrize("url", ["https://www.instagram.com/reel/Chunk8-jurw/", "https://instagram.com/reels/Chunk8-jurw",
                                 "https://www.instagram.com/someone.name/reel/Chunk8-jurw/?igsh=abc", "https://m.instagram.com/p/Abc_12/"])
def test_reel_and_post_links_are_instagram(url):
    assert is_instagram_link(url) and link_name(url) == "Instagram reel"


@pytest.mark.parametrize("url", ["https://www.instagram.com/someone/", "https://youtu.be/abc", "https://evil.com/instagram.com/reel/x"])
def test_other_links_are_not(url):
    assert not is_instagram_link(url)


def test_an_instagram_reel_is_checked_like_a_youtube_video(monkeypatch):
    async def found(self, url):
        return InstagramVideo(title="Five habits", duration=40.0) if "ok" in url else InstagramVideo(title="Long", duration=4000.0)

    monkeypatch.setattr(instagram_service.InstagramService, "fetch_metadata", found)
    assert asyncio.run(EditService._check_source_link("https://www.instagram.com/reel/ok123/", 600)) == "Five habits"
    with pytest.raises(CustomException) as too_long:
        asyncio.run(EditService._check_source_link("https://www.instagram.com/reel/long1/", 600))
    assert too_long.value.code == "FOOTAGE_LIMIT"

    async def closed(self, url):
        return None

    monkeypatch.setattr(instagram_service.InstagramService, "fetch_metadata", closed)
    with pytest.raises(CustomException) as private:
        asyncio.run(EditService._check_source_link("https://www.instagram.com/reel/priv/", 600))
    assert "Instagram reel" in private.value.message
    with pytest.raises(CustomException) as other:
        asyncio.run(EditService._check_source_link("https://vimeo.com/123", 600))
    assert "Instagram reel link" in other.value.message
