"""The "download all clips" ZIP: one file holding every render."""
import zipfile
from types import SimpleNamespace

import pytest

from clip_generation.schema import SocialExportRequest, SocialExportResponse
from clip_generation.service import ClipService


class _FakeS3:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes, str]] = []

    def upload_file(self, bucket: str, key: str, path: str, content_type: str | None = None) -> dict:
        with open(path, "rb") as f:
            self.uploads.append((bucket, key, f.read(), content_type))
        return {}

    def generate_presigned_url(self, bucket, key, expires_in, download_name=None) -> str:
        return f"https://s3/{key}?name={download_name}"


def test_bundle_is_off_by_default():
    assert SocialExportRequest().bundle is False
    response = SocialExportResponse(
        project_id="p", exported_clips=[], platforms=[], total_exported=0, watermark_enabled=True,
    )
    assert response.bundle_presigned_url is None


@pytest.mark.asyncio
async def test_store_bundle_uploads_zip_and_signs_download(tmp_path):
    service = object.__new__(ClipService)
    service._s3 = _FakeS3()
    service._bucket = "bucket"

    render = tmp_path / "render.mp4"
    render.write_bytes(b"video")
    archive = zipfile.ZipFile(tmp_path / "clips.zip", "w", zipfile.ZIP_STORED)
    archive.write(render, "01-clip-tiktok-9x16.mp4")

    url = await service._store_bundle(archive, SimpleNamespace(id="p1", title="My Talk!"), "u1")

    assert url == "https://s3/social/u1/p1/my-talk-clips.zip?name=my-talk-clips.zip"
    (bucket, key, body, content_type), = service._s3.uploads
    assert (bucket, key, content_type) == ("bucket", "social/u1/p1/my-talk-clips.zip", "application/zip")
    with zipfile.ZipFile(tmp_path / "clips.zip") as uploaded:
        assert uploaded.namelist() == ["01-clip-tiktok-9x16.mp4"]
        assert uploaded.read("01-clip-tiktok-9x16.mp4") == b"video"
