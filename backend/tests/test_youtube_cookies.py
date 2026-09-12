import os
from pathlib import Path

from clip.youtube_service import YouTubeService


def test_yt_dlp_uses_default_cookie_file_when_env_not_set(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_BROWSER", raising=False)
    monkeypatch.delenv("YOUTUBE_COOKIES_PATH", raising=False)

    cookie_path = Path(__file__).resolve().parents[1] / "youtube_cookies.txt"
    assert cookie_path.exists()

    options = YouTubeService()._yt_dlp_base_options()

    assert options.get("cookiefile") == str(cookie_path)
    assert "cookiesfrombrowser" not in options
