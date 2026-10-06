"""Settings read from an env file in S3 (servers keep no .env on disk)."""

from __future__ import annotations

import io
import os

import boto3
import pytest

from core.config import CONFIG_S3_URI_VAR, load_remote_env


class FakeS3:
    def __init__(self, body: str) -> None:
        self.body = body
        self.asked: dict = {}

    def get_object(self, Bucket: str, Key: str) -> dict:
        self.asked = {"Bucket": Bucket, "Key": Key}
        return {"Body": io.BytesIO(self.body.encode())}


@pytest.fixture
def fake_s3(monkeypatch):
    s3 = FakeS3('# settings\nREMOTE_ENV_A=from-s3\nREMOTE_ENV_B="quoted value"\nREMOTE_ENV_C=from-s3\n')
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    for key in ("REMOTE_ENV_A", "REMOTE_ENV_B", "REMOTE_ENV_C"):
        monkeypatch.delenv(key, raising=False)
    yield s3
    for key in ("REMOTE_ENV_A", "REMOTE_ENV_B", "REMOTE_ENV_C"):
        os.environ.pop(key, None)


def test_values_come_from_the_s3_object(fake_s3, monkeypatch):
    monkeypatch.setenv(CONFIG_S3_URI_VAR, "s3://config-bucket/app/clipnera.env")
    monkeypatch.setenv("REMOTE_ENV_C", "already-set")
    load_remote_env()
    assert fake_s3.asked == {"Bucket": "config-bucket", "Key": "app/clipnera.env"}
    assert os.environ["REMOTE_ENV_A"] == "from-s3"
    assert os.environ["REMOTE_ENV_B"] == "quoted value"
    # The machine's own environment wins over the file.
    assert os.environ["REMOTE_ENV_C"] == "already-set"


def test_nothing_is_read_without_the_variable(fake_s3, monkeypatch):
    monkeypatch.delenv(CONFIG_S3_URI_VAR, raising=False)
    load_remote_env()
    assert fake_s3.asked == {}
    assert "REMOTE_ENV_A" not in os.environ
