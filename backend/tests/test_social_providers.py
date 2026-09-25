"""Platform flows against mocked HTTP: request shapes, checkpoints, recovery."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import social.providers.instagram as instagram_module
import social.providers.tiktok as tiktok_module
import social.providers.x as x_module
from core.config import get_settings
from social.providers.base import ClipFile, ErrorKind, NotPublished, PlatformError, PublishRequest, TokenSet
from social.providers.instagram import InstagramProvider
from social.providers.tiktok import TikTokProvider
from social.providers.x import XProvider
from social.providers.youtube import SCOPE_READONLY, SCOPE_UPLOAD, YouTubeProvider


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    settings = get_settings()
    for name, value in {
        "PUBLIC_APP_URL": "https://app.clipnera.test",
        "YOUTUBE_CLIENT_ID": "yt-id", "YOUTUBE_CLIENT_SECRET": "yt-secret",
        "TIKTOK_CLIENT_KEY": "tt-key", "TIKTOK_CLIENT_SECRET": "tt-secret",
        "INSTAGRAM_APP_ID": "ig-id", "INSTAGRAM_APP_SECRET": "ig-secret",
        "X_CLIENT_ID": "x-id", "X_CLIENT_SECRET": "x-secret",
    }.items():
        monkeypatch.setattr(settings, name, value)
    for module in (tiktok_module, instagram_module, x_module):
        monkeypatch.setattr(module.asyncio, "sleep", _no_sleep)


async def _no_sleep(_seconds):
    return None


@pytest.fixture
def clip(tmp_path: Path) -> ClipFile:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"v" * 1000)
    return ClipFile(
        path=path, size_bytes=1000, duration_seconds=30, width=1080, height=1920, fps=30,
        video_codec="h264", audio_codec="aac", audio_sample_rate=48000, container="mov,mp4,m4a",
        presign=lambda ttl: f"https://bucket.s3.test/clip.mp4?X-Amz-Expires={ttl}",
    )


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class Checkpoints(list):
    async def __call__(self, value: str) -> None:
        self.append(value)


TOKENS = TokenSet(access_token="access-1", refresh_token="refresh-1")


# -- YouTube -------------------------------------------------------------------


def test_youtube_authorize_url_is_fixed_and_uses_pkce():
    url = YouTubeProvider().authorize_url("state-1", "challenge-1")
    query = parse_qs(urlparse(url).query)
    assert query["redirect_uri"] == ["https://app.clipnera.test/dashboard/connect/youtube"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["access_type"] == ["offline"]
    assert set(query["scope"][0].split()) == {SCOPE_UPLOAD, SCOPE_READONLY}


@pytest.mark.asyncio
async def test_youtube_exchange_rejects_partial_scopes():
    def handler(request):
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "scope": SCOPE_UPLOAD})

    with pytest.raises(PlatformError) as exc:
        await YouTubeProvider(_client(handler)).exchange_code("code", "verifier")
    assert exc.value.code == "scopes_missing"


@pytest.mark.asyncio
async def test_youtube_exchange_sends_verifier_and_secret_server_side():
    seen = {}

    def handler(request):
        seen.update(parse_qs(request.content.decode()))
        return httpx.Response(200, json={
            "access_token": "a", "refresh_token": "r", "expires_in": 3600,
            "scope": f"{SCOPE_UPLOAD} {SCOPE_READONLY}",
        })

    tokens = await YouTubeProvider(_client(handler)).exchange_code("code-1", "verifier-1")
    assert tokens.refresh_token == "r" and tokens.expires_at is not None
    assert seen["code_verifier"] == ["verifier-1"] and seen["client_secret"] == ["yt-secret"]


@pytest.mark.asyncio
async def test_youtube_profile_hides_hidden_subscriber_count():
    def handler(request):
        return httpx.Response(200, json={"items": [{
            "id": "UC1", "snippet": {"title": "Chan", "customUrl": "@chan", "thumbnails": {"default": {"url": "u"}}},
            "statistics": {"subscriberCount": "100", "hiddenSubscriberCount": True},
        }]})

    profile = await YouTubeProvider(_client(handler)).fetch_profile(TOKENS)
    assert (profile.platform_user_id, profile.handle, profile.follower_count) == ("UC1", "@chan", None)


@pytest.mark.asyncio
async def test_youtube_publish_checkpoints_before_uploading(clip):
    checkpoints = Checkpoints()
    calls = []

    def handler(request):
        calls.append((request.method, len(checkpoints)))
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["status"] == {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}
            return httpx.Response(200, headers={"Location": "https://upload.test/session-1"})
        return httpx.Response(201, json={"id": "vid-1"})

    request = PublishRequest(
        caption="desc", clip=clip,
        options={"title": "Title", "privacy_status": "unlisted", "made_for_kids": False},
    )
    result = await YouTubeProvider(_client(handler)).publish(TOKENS, request, checkpoints)
    assert result.post_url == "https://www.youtube.com/shorts/vid-1"
    assert checkpoints == ["1000 https://upload.test/session-1"]
    # The upload (PUT) only started after the checkpoint was saved.
    assert calls == [("POST", 0), ("PUT", 1)]


@pytest.mark.asyncio
async def test_youtube_resolve_unfinished_session_is_not_published():
    provider = YouTubeProvider(_client(lambda r: httpx.Response(308)))
    with pytest.raises(NotPublished):
        await provider.resolve_checkpoint(TOKENS, "1000 https://upload.test/s", None)


@pytest.mark.asyncio
async def test_youtube_resolve_finished_session_returns_the_video():
    def handler(request):
        assert request.headers["content-range"] == "bytes */1000"
        return httpx.Response(200, json={"id": "vid-9"})

    result = await YouTubeProvider(_client(handler)).resolve_checkpoint(TOKENS, "1000 https://upload.test/s", None)
    assert result.platform_post_id == "vid-9"


def test_youtube_requires_explicit_made_for_kids():
    problems = YouTubeProvider().validate_options({"title": "t", "privacy_status": "public"})
    assert any("made for kids" in p for p in problems)


def test_youtube_rejects_horizontal_and_long_clips(clip):
    from dataclasses import replace

    wide = replace(clip, width=1920, height=1080)
    long = replace(clip, duration_seconds=200)
    options = {"title": "t", "privacy_status": "public", "made_for_kids": False}
    assert YouTubeProvider().validate(wide, "", options)
    assert YouTubeProvider().validate(long, "", options)
    assert not YouTubeProvider().validate(clip, "", options)


# -- TikTok ----------------------------------------------------------------------

TIKTOK_OPTIONS = {
    "privacy_level": "SELF_ONLY", "disable_comment": False, "disable_duet": False, "disable_stitch": False,
    "brand_content_toggle": False, "brand_organic_toggle": False,
}


@pytest.mark.asyncio
async def test_tiktok_publish_flow(clip):
    checkpoints = Checkpoints()
    order = []

    def handler(request):
        path = request.url.path
        order.append(path)
        if path.endswith("/creator_info/query/"):
            return httpx.Response(200, json={"data": {"privacy_level_options": ["SELF_ONLY"], "max_video_post_duration_sec": 600}})
        if path.endswith("/video/init/"):
            body = json.loads(request.content)
            assert body["source_info"] == {"source": "FILE_UPLOAD", "video_size": 1000, "chunk_size": 1000, "total_chunk_count": 1}
            assert body["post_info"]["privacy_level"] == "SELF_ONLY"
            return httpx.Response(200, json={"data": {"publish_id": "pub-1", "upload_url": "https://upload.tiktok.test/u"}})
        if request.method == "PUT":
            assert checkpoints == ["pub-1"]
            assert request.headers["content-range"] == "bytes 0-999/1000"
            return httpx.Response(201)
        return httpx.Response(200, json={"data": {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [777]}})

    request = PublishRequest(caption="hi", options=TIKTOK_OPTIONS, clip=clip, account_handle="@me")
    result = await TikTokProvider(_client(handler)).publish(TOKENS, request, checkpoints)
    assert result.post_url == "https://www.tiktok.com/@me/video/777"


@pytest.mark.asyncio
async def test_tiktok_refuses_privacy_option_the_creator_no_longer_has(clip):
    def handler(request):
        return httpx.Response(200, json={"data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE"]}})

    request = PublishRequest(caption="", options=TIKTOK_OPTIONS, clip=clip)
    with pytest.raises(PlatformError) as exc:
        await TikTokProvider(_client(handler)).publish(TOKENS, request, Checkpoints())
    assert exc.value.kind == ErrorKind.PERMANENT


@pytest.mark.asyncio
async def test_tiktok_resolve_unfinished_upload_is_not_published():
    provider = TikTokProvider(_client(lambda r: httpx.Response(200, json={"data": {"status": "PROCESSING_UPLOAD"}})))
    with pytest.raises(NotPublished):
        await provider.resolve_checkpoint(TOKENS, "pub-1", "@me")


def test_tiktok_branded_content_cannot_be_private():
    problems = TikTokProvider().validate_options({**TIKTOK_OPTIONS, "brand_content_toggle": True})
    assert any("Branded" in p for p in problems)


# -- Instagram --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instagram_publish_uses_a_short_lived_url(clip):
    checkpoints = Checkpoints()

    def handler(request):
        path = request.url.path
        if path.endswith("/content_publishing_limit"):
            return httpx.Response(200, json={"data": [{"quota_usage": 3, "config": {"quota_total": 100}}]})
        if path.endswith("/me/media"):
            form = parse_qs(request.content.decode())
            assert form["media_type"] == ["REELS"]
            assert "X-Amz-Expires=900" in form["video_url"][0]
            return httpx.Response(200, json={"id": "container-1"})
        if path.endswith("/container-1"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path.endswith("/media_publish"):
            assert checkpoints == ["container-1"]
            return httpx.Response(200, json={"id": "media-1"})
        return httpx.Response(200, json={"permalink": "https://instagram.com/reel/abc"})

    request = PublishRequest(caption="hi", options={"share_to_feed": True}, clip=clip)
    result = await InstagramProvider(_client(handler)).publish(TOKENS, request, checkpoints)
    assert (result.platform_post_id, result.post_url) == ("media-1", "https://instagram.com/reel/abc")


@pytest.mark.asyncio
async def test_instagram_full_publishing_quota_defers(clip):
    def handler(request):
        return httpx.Response(200, json={"data": [{"quota_usage": 100, "config": {"quota_total": 100}}]})

    request = PublishRequest(caption="", options={}, clip=clip)
    with pytest.raises(PlatformError) as exc:
        await InstagramProvider(_client(handler)).publish(TOKENS, request, Checkpoints())
    assert exc.value.kind == ErrorKind.QUOTA


@pytest.mark.asyncio
async def test_instagram_rejects_personal_accounts():
    provider = InstagramProvider(_client(lambda r: httpx.Response(200, json={"id": "1", "account_type": "PERSONAL"})))
    with pytest.raises(PlatformError) as exc:
        await provider.fetch_profile(TOKENS)
    assert exc.value.code == "not_professional"


# -- X ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_x_uploads_then_posts(clip):
    checkpoints = Checkpoints()
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/initialize"):
            return httpx.Response(200, json={"data": {"id": "m1"}})
        if request.url.path.endswith("/append"):
            return httpx.Response(200)
        if request.url.path.endswith("/finalize"):
            return httpx.Response(200, json={"data": {"id": "m1", "processing_info": {"state": "succeeded"}}})
        assert checkpoints == ["m1"]
        assert json.loads(request.content) == {"text": "hello", "media": {"media_ids": ["m1"]}}
        return httpx.Response(201, json={"data": {"id": "t1"}})

    request = PublishRequest(caption="hello", options={}, clip=clip, account_handle="@me")
    result = await XProvider(_client(handler)).publish(TOKENS, request, checkpoints)
    assert result.post_url == "https://x.com/me/status/t1"
    assert paths[-1] == "/2/tweets"


@pytest.mark.asyncio
async def test_x_cannot_confirm_an_interrupted_post():
    # No safe way to tell whether the post went out, so recovery must not claim either way.
    assert await XProvider().resolve_checkpoint(TOKENS, "m1", "@me") is None


@pytest.mark.asyncio
async def test_x_refresh_uses_basic_auth():
    def handler(request):
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200})

    tokens = await XProvider(_client(handler)).refresh(TOKENS)
    assert tokens.refresh_token == "r2"
