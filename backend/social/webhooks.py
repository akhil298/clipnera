"""Signature checks for platform callbacks. Verification always happens before
the payload is trusted or parsed for anything else."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from core.config import get_settings

# Reject TikTok events whose signed timestamp is older than this (replays).
TIKTOK_MAX_AGE_SECONDS = 300


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def parse_meta_signed_request(signed_request: str, app_secret: str | None = None) -> dict[str, Any] | None:
    """Meta's ``signed_request``: "<b64url HMAC-SHA256 sig>.<b64url JSON payload>".
    Returns the payload, or None when the signature does not match."""
    secret = app_secret if app_secret is not None else get_settings().INSTAGRAM_APP_SECRET
    if not secret or "." not in signed_request:
        return None
    encoded_sig, payload = signed_request.split(".", 1)
    try:
        signature = _b64url_decode(encoded_sig)
        data = json.loads(_b64url_decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        return None
    if str(data.get("algorithm", "")).upper() != "HMAC-SHA256":
        return None
    return data if isinstance(data, dict) else None


def verify_tiktok_signature(
    header: str | None, body: bytes, client_secret: str | None = None, now: float | None = None
) -> bool:
    """TikTok-Signature: "t=<unix ts>,s=<hex HMAC-SHA256 of '<t>.<body>'>"."""
    secret = client_secret if client_secret is not None else get_settings().TIKTOK_CLIENT_SECRET
    if not secret or not header:
        return False
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    timestamp, signature = parts.get("t"), parts.get("s")
    if not timestamp or not signature or not timestamp.isdigit():
        return False
    if abs((now or time.time()) - int(timestamp)) > TIKTOK_MAX_AGE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
