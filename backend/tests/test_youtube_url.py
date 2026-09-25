import pytest
from pydantic import ValidationError

from clip.schema import YouTubeDownloadRequest, YouTubeURLRequest
from clip.youtube_service import YouTubeService
from clip.youtube_url import canonical_youtube_url, extract_youtube_video_id

VIDEO_ID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO_ID}",
    f"http://youtube.com/watch?feature=share&v={VIDEO_ID}&t=42",
    f"https://m.youtube.com/watch?v={VIDEO_ID}",
    f"www.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}?si=abc",
    f"https://www.youtube.com/shorts/{VIDEO_ID}",
    f"https://www.youtube.com/embed/{VIDEO_ID}",
    f"https://www.youtube.com/live/{VIDEO_ID}",
    f"  HTTPS://WWW.YOUTUBE.COM/watch?v={VIDEO_ID}  ",
])
def test_accepts_youtube_video_links(url):
    assert extract_youtube_video_id(url) == VIDEO_ID
    assert canonical_youtube_url(url) == CANONICAL


@pytest.mark.parametrize("url", [
    "",
    "https://vimeo.com/123456789",
    "https://www.tiktok.com/@user/video/1234567890123456789",
    "https://www.twitch.tv/videos/1234567890",
    "https://example.com/video.mp4",
    f"https://evil.com/?next=youtube.com/watch?v={VIDEO_ID}",
    f"https://youtube.com.evil.com/watch?v={VIDEO_ID}",
    f"https://youtube.com@evil.com/watch?v={VIDEO_ID}",
    f"ftp://youtube.com/watch?v={VIDEO_ID}",
    f"file:///etc/passwd?v={VIDEO_ID}",
    "https://www.youtube.com/playlist?list=PL1234567890",
    "https://www.youtube.com/@channel",
    "https://www.youtube.com/watch?v=tooshort",
    "https://[::1/watch?v=dQw4w9WgXcQ",
])
def test_rejects_non_youtube_video_links(url):
    assert extract_youtube_video_id(url) is None
    with pytest.raises(ValueError):
        canonical_youtube_url(url)


@pytest.mark.parametrize("model", [YouTubeURLRequest, YouTubeDownloadRequest])
def test_request_schemas_only_accept_youtube(model):
    assert model(url=f"https://youtu.be/{VIDEO_ID}").url == CANONICAL
    with pytest.raises(ValidationError):
        model(url="https://vimeo.com/123456789")


def test_yt_dlp_is_restricted_to_youtube_extractor():
    assert YouTubeService()._yt_dlp_base_options()["allowed_extractors"] == ["youtube"]
