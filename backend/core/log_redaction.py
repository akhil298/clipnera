"""Masks credentials in log output.

Applied to the fully formatted line (message, ``extra`` context and traceback),
so a token that reaches a log by accident -- in an exception message, a URL
query string or a dumped response body -- is still masked. This is a safety
net; code must still never log secrets on purpose.
"""

from __future__ import annotations

import re

MASK = "[REDACTED]"

# key=value, key: value, "key": "value" for credential-bearing names.
_SENSITIVE_KEYS = (
    r"access_token|refresh_token|id_token|client_secret|code_verifier|code_challenge|"
    r"authorization_code|signed_request|password|secret|api_key|apikey|token"
)
_KEY_VALUE = re.compile(
    rf"""(?P<key>["']?\b(?:{_SENSITIVE_KEYS})\b["']?\s*[=:]\s*["']?)(?P<value>[^\s"'&,}}\]]+)""",
    re.IGNORECASE,
)
# OAuth callback parameters: only as query parameters, so error codes and
# pipeline states elsewhere in logs stay readable.
_QUERY_PARAM = re.compile(r"(?P<key>[?&](?:code|state)=)(?P<value>[^&\s\"']+)", re.IGNORECASE)
_BEARER = re.compile(r"\b(Bearer|Basic|OAuth)\s+[A-Za-z0-9\-._~+/=]{8,}", re.IGNORECASE)
# Recognisable platform token shapes, masked wherever they appear.
_TOKEN_SHAPES = re.compile(
    r"\b(?:ya29\.[\w\-.]+|1//[\w\-.]+|act\.[\w\-.]+|rft\.[\w\-.]+|IG[A-Z]{2}[\w\-]{20,}|EAA[\w]{20,})"
)


def redact(text: str) -> str:
    if not text:
        return text
    text = _BEARER.sub(lambda m: f"{m.group(1)} {MASK}", text)
    text = _TOKEN_SHAPES.sub(MASK, text)
    text = _QUERY_PARAM.sub(lambda m: f"{m.group('key')}{MASK}", text)
    return _KEY_VALUE.sub(lambda m: f"{m.group('key')}{MASK}", text)
