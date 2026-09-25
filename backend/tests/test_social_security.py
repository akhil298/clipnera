"""Security building blocks of connected publishing, without a database."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import typing
from datetime import datetime, timedelta

import httpx
import pytest
from pydantic import BaseModel

import social.schema as social_schema
from core.crypto import CipherError, TokenCipher, parse_key_ring
from core.log_redaction import MASK, redact
from core.logging_config import ContextFormatter
from feature_flags.service import resolve
from social.providers.base import ErrorKind, PkcePair, TokenSet
from social.providers.instagram import InstagramProvider
from social.providers.tiktok import TikTokProvider, chunk_plan, chunk_ranges
from social.providers.x import XProvider
from social.providers.youtube import YouTubeProvider, until_pacific_midnight
from social.publisher import backoff_for
from social.tokens import open_text, seal_text
from social.webhooks import parse_meta_signed_request, verify_tiktok_signature
from subscription.entitlements import entitlements_for

KEY_1 = base64.b64encode(b"1" * 32).decode()
KEY_2 = base64.b64encode(b"2" * 32).decode()


def _cipher(active: int = 1) -> TokenCipher:
    return TokenCipher(parse_key_ring(f"1:{KEY_1},2:{KEY_2}"), active)


# -- encryption ------------------------------------------------------------------


def test_token_round_trips_and_ciphertext_hides_plaintext():
    cipher = _cipher()
    sealed = cipher.encrypt("ya29.secret-token", "oauth_tokens:acc-1:access")
    assert b"secret-token" not in sealed.ciphertext
    assert cipher.decrypt(sealed.ciphertext, sealed.key_version, "oauth_tokens:acc-1:access") == "ya29.secret-token"


def test_same_plaintext_encrypts_differently_each_time():
    cipher = _cipher()
    assert cipher.encrypt("t", "a").ciphertext != cipher.encrypt("t", "a").ciphertext


def test_ciphertext_moved_to_another_row_fails():
    cipher = _cipher()
    sealed = cipher.encrypt("token", "oauth_tokens:acc-1:access")
    with pytest.raises(CipherError):
        cipher.decrypt(sealed.ciphertext, sealed.key_version, "oauth_tokens:acc-2:access")
    with pytest.raises(CipherError):
        cipher.decrypt(sealed.ciphertext, sealed.key_version, "oauth_tokens:acc-1:refresh")


def test_tampered_ciphertext_fails():
    cipher = _cipher()
    sealed = cipher.encrypt("token", "aad")
    tampered = sealed.ciphertext[:-1] + bytes([sealed.ciphertext[-1] ^ 1])
    with pytest.raises(CipherError):
        cipher.decrypt(tampered, sealed.key_version, "aad")


def test_key_rotation_keeps_old_values_readable():
    old = _cipher(active=1).encrypt("token", "aad")
    rotated = _cipher(active=2)
    assert rotated.decrypt(old.ciphertext, old.key_version, "aad") == "token"
    assert rotated.needs_rotation(old.key_version)
    assert rotated.encrypt("token", "aad").key_version == 2


def test_removed_key_version_cannot_decrypt():
    old = _cipher().encrypt("token", "aad")
    only_new = TokenCipher(parse_key_ring(f"2:{KEY_2}"), 2)
    with pytest.raises(CipherError):
        only_new.decrypt(old.ciphertext, old.key_version, "aad")


@pytest.mark.parametrize("raw", ["1:not-base64!", "x:" + KEY_1, "1:" + base64.b64encode(b"short").decode(), "nocolon"])
def test_bad_key_ring_is_rejected(raw):
    with pytest.raises(CipherError):
        parse_key_ring(raw)


def test_active_version_must_be_in_ring():
    with pytest.raises(CipherError):
        TokenCipher(parse_key_ring(f"1:{KEY_1}"), 2)


def test_sealed_text_checkpoint_round_trip():
    cipher = _cipher()
    sealed = seal_text("https://upload.example/session", "scheduled_posts:p1:checkpoint", cipher)
    assert "upload.example" not in sealed
    assert open_text(sealed, "scheduled_posts:p1:checkpoint", cipher) == "https://upload.example/session"


# -- log redaction -----------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Authorization: Bearer abcdefghijklmnop123",
        "GET https://graph.instagram.com/me?access_token=IGAAxyzxyzxyzxyzxyzxyzxyz&fields=id",
        '{"access_token": "act.example12345", "refresh_token": "rft.example12345"}',
        "callback?code=4/0AbCdEf&state=xyz123",
        "client_secret=super-secret-value",
        "token ya29.a0AfH6SMBxyz issued",
        "refresh 1//0gAbCdEfGhIj",
    ],
)
def test_redaction_masks_credentials(line):
    out = redact(line)
    assert MASK in out
    for secret in ("abcdefghijklmnop123", "IGAAxyz", "act.example", "rft.example", "4/0AbCdEf", "super-secret", "ya29.", "1//0g"):
        assert secret not in out


@pytest.mark.parametrize("line", ["status_code=200", "pipeline state: processing", "error code PRO_REQUIRED"])
def test_redaction_leaves_ordinary_text(line):
    assert redact(line) == line


def test_formatter_redacts_exceptions_and_extra_fields():
    formatter = ContextFormatter("%(message)s")
    try:
        raise ValueError("failed with access_token=IGAAleakedleakedleakedleaked")
    except ValueError:
        import sys

        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", (), sys.exc_info())
    record.headers = "Bearer abcdefghijklmnopqrst"
    out = formatter.format(record)
    assert "IGAAleaked" not in out
    assert "abcdefghijklmnopqrst" not in out


def test_token_set_repr_hides_secrets():
    tokens = TokenSet(access_token="secret-access", refresh_token="secret-refresh")
    assert "secret" not in repr(tokens)


# -- no tokens in any API model ------------------------------------------------------

_FORBIDDEN_FIELDS = {"access_token", "refresh_token", "token", "access_token_ct", "refresh_token_ct", "code_verifier"}


def _fields(model: type[BaseModel], seen: set) -> set[str]:
    if model in seen:
        return set()
    seen.add(model)
    names = set(model.model_fields)
    for field in model.model_fields.values():
        for arg in typing.get_args(field.annotation) or (field.annotation,):
            for inner in typing.get_args(arg) or (arg,):
                if isinstance(inner, type) and issubclass(inner, BaseModel):
                    names |= _fields(inner, seen)
    return names


def test_no_social_response_model_has_a_token_field():
    models = [
        obj for obj in vars(social_schema).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == social_schema.__name__
    ]
    assert models
    for model in models:
        assert not (_fields(model, set()) & _FORBIDDEN_FIELDS), model.__name__


# -- PKCE and webhooks ----------------------------------------------------------------


def test_pkce_challenge_is_s256_of_verifier():
    pair = PkcePair.generate()
    digest = base64.urlsafe_b64encode(hashlib.sha256(pair.verifier.encode()).digest()).rstrip(b"=").decode()
    assert pair.challenge == digest
    assert 43 <= len(pair.verifier) <= 128


def _signed_request(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{sig}.{body}"


def test_meta_signed_request_verifies():
    signed = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "123"}, "app-secret")
    assert parse_meta_signed_request(signed, "app-secret")["user_id"] == "123"


def test_meta_signed_request_rejects_wrong_secret_and_tampering():
    signed = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "123"}, "app-secret")
    assert parse_meta_signed_request(signed, "other-secret") is None
    sig, body = signed.split(".")
    forged = base64.urlsafe_b64encode(json.dumps({"algorithm": "HMAC-SHA256", "user_id": "999"}).encode()).decode()
    assert parse_meta_signed_request(f"{sig}.{forged}", "app-secret") is None
    assert parse_meta_signed_request("garbage", "app-secret") is None
    assert parse_meta_signed_request(signed, "") is None


def _tiktok_header(body: bytes, secret: str, ts: int) -> str:
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},s={sig}"


def test_tiktok_signature_verifies_and_rejects_forgery():
    body = b'{"event":"authorization.removed"}'
    now = time.time()
    header = _tiktok_header(body, "secret", int(now))
    assert verify_tiktok_signature(header, body, "secret", now)
    assert not verify_tiktok_signature(header, body + b" ", "secret", now)
    assert not verify_tiktok_signature(header, body, "wrong", now)
    assert not verify_tiktok_signature(None, body, "secret", now)


def test_tiktok_signature_rejects_replayed_old_events():
    body = b"{}"
    old = int(time.time()) - 3600
    assert not verify_tiktok_signature(_tiktok_header(body, "secret", old), body, "secret")


# -- platform rules -----------------------------------------------------------------


@pytest.mark.parametrize("size", [1, 4 * 1024**2, 5 * 1024**2, 50_000_123, 300 * 1024**2 + 7])
def test_tiktok_chunks_cover_the_file_exactly(size):
    chunk_size, count = chunk_plan(size)
    ranges = chunk_ranges(size)
    assert len(ranges) == count
    assert ranges[0][0] == 0 and ranges[-1][1] == size - 1
    assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))
    # Every chunk but the last is exactly chunk_size; the last may be larger, never over 128 MB.
    assert all(last - first + 1 == chunk_size for first, last in ranges[:-1])
    assert ranges[-1][1] - ranges[-1][0] + 1 <= 128 * 1024**2


def test_youtube_quota_reset_is_after_pacific_midnight():
    wait = until_pacific_midnight(datetime(2026, 9, 25, 6, 0))  # 23:00 PDT
    assert timedelta(minutes=0) < wait <= timedelta(hours=1, minutes=5)


def test_backoff_grows_and_is_capped():
    assert [backoff_for(n) for n in range(1, 7)] == [
        timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=25),
        timedelta(hours=2), timedelta(hours=2), timedelta(hours=2),
    ]


def _response(status: int, body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers, request=httpx.Request("GET", "https://x"))


@pytest.mark.parametrize(
    ("provider", "status", "body", "kind"),
    [
        (YouTubeProvider(), 400, {"error": "invalid_grant"}, ErrorKind.AUTH),
        (YouTubeProvider(), 403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}, ErrorKind.QUOTA),
        (YouTubeProvider(), 403, {"error": {"errors": [{"reason": "uploadLimitExceeded"}]}}, ErrorKind.QUOTA),
        (YouTubeProvider(), 400, {"error": {"errors": [{"reason": "invalidTitle"}], "message": "bad"}}, ErrorKind.PERMANENT),
        (YouTubeProvider(), 503, {}, ErrorKind.TRANSIENT),
        (TikTokProvider(), 401, {"error": {"code": "access_token_invalid"}}, ErrorKind.AUTH),
        (TikTokProvider(), 403, {"error": {"code": "spam_risk_too_many_posts"}}, ErrorKind.PERMANENT),
        (TikTokProvider(), 429, {"error": {"code": "rate_limit_exceeded"}}, ErrorKind.TRANSIENT),
        (InstagramProvider(), 400, {"error": {"code": 190}}, ErrorKind.AUTH),
        (InstagramProvider(), 400, {"error": {"code": 9, "error_subcode": 2207042}}, ErrorKind.QUOTA),
        (InstagramProvider(), 400, {"error": {"code": 4}}, ErrorKind.TRANSIENT),
        (InstagramProvider(), 400, {"error": {"code": 100, "message": "bad video"}}, ErrorKind.PERMANENT),
        (XProvider(), 401, {"title": "Unauthorized"}, ErrorKind.AUTH),
        (XProvider(), 429, {"title": "Too Many Requests"}, ErrorKind.QUOTA),
        (XProvider(), 403, {"detail": "You are not allowed to create a Tweet with duplicate content."}, ErrorKind.PERMANENT),
    ],
)
def test_platform_errors_are_classified(provider, status, body, kind):
    assert provider.map_error(_response(status, body)).kind == kind


def test_error_messages_never_carry_tokens():
    body = {"error": {"code": 100, "message": "Invalid access_token=IGAAsecretsecretsecretsecret"}}
    error = InstagramProvider().map_error(_response(400, body))
    assert "IGAAsecret" not in error.message


# -- flags and plans ------------------------------------------------------------------


def test_platform_flag_needs_its_parent():
    assert resolve({"social_publishing.youtube": True})["social_publishing.youtube"] is False
    both = resolve({"social_publishing": True, "social_publishing.youtube": True})
    assert both["social_publishing.youtube"] is True
    assert both["social_publishing.tiktok"] is False


def test_unknown_stored_flags_are_ignored():
    assert "not_a_flag" not in resolve({"not_a_flag": True})


def test_free_plan_social_limits():
    free = entitlements_for("free")
    assert free.social_max_accounts == 1
    assert not free.social_scheduling
    assert "x" not in free.social_platforms
    pro = entitlements_for("pro")
    assert pro.social_scheduling and pro.social_max_schedule_days == 30
    assert "x" in pro.social_platforms
