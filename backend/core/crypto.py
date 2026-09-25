"""Authenticated encryption for secrets stored in the database.

AES-256-GCM with a random 96-bit nonce per value. Every ciphertext is bound to
an ``aad`` string (for tokens: the owning row id and field name), so a value
copied into another row or column fails to decrypt instead of being accepted.

Keys come only from ``SOCIAL_TOKEN_ENCRYPTION_KEYS`` as a versioned ring. Each
stored value records its key version, so the active key can be rotated without
a flag day: new writes use the active version and old values stay readable
until they are re-encrypted.
"""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import get_settings

_NONCE_BYTES = 12
_KEY_BYTES = 32


class CipherError(Exception):
    """A value could not be encrypted or decrypted. Never carries key or plaintext."""


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    key_version: int


def parse_key_ring(raw: str) -> dict[int, bytes]:
    """Parse "1:<b64>,2:<b64>" into {version: key}. Raises CipherError on any malformed entry."""
    ring: dict[int, bytes] = {}
    for entry in (part.strip() for part in raw.split(",")):
        if not entry:
            continue
        version, sep, encoded = entry.partition(":")
        if not sep or not version.strip().isdigit():
            raise CipherError("Key ring entries must look like '<version>:<base64 key>'")
        try:
            key = base64.b64decode(encoded.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CipherError(f"Key version {version.strip()} is not valid base64") from exc
        if len(key) != _KEY_BYTES:
            raise CipherError(f"Key version {version.strip()} must decode to {_KEY_BYTES} bytes")
        ring[int(version)] = key
    return ring


class TokenCipher:
    def __init__(self, keys: dict[int, bytes], active_version: int) -> None:
        if active_version not in keys:
            raise CipherError(f"Active key version {active_version} is not in the key ring")
        self._keys = {version: AESGCM(key) for version, key in keys.items()}
        self.active_version = active_version

    def encrypt(self, plaintext: str, aad: str) -> Sealed:
        nonce = os.urandom(_NONCE_BYTES)
        sealed = self._keys[self.active_version].encrypt(nonce, plaintext.encode(), aad.encode())
        return Sealed(ciphertext=nonce + sealed, key_version=self.active_version)

    def decrypt(self, ciphertext: bytes, key_version: int, aad: str) -> str:
        aead = self._keys.get(key_version)
        if aead is None:
            raise CipherError(f"Key version {key_version} is no longer in the key ring")
        nonce, body = ciphertext[:_NONCE_BYTES], ciphertext[_NONCE_BYTES:]
        try:
            return aead.decrypt(nonce, body, aad.encode()).decode()
        except InvalidTag as exc:
            raise CipherError("Stored secret failed authentication") from exc

    def needs_rotation(self, key_version: int) -> bool:
        return key_version != self.active_version


@lru_cache
def get_token_cipher() -> TokenCipher:
    """The process-wide cipher. Raises CipherError when the key ring is missing or invalid."""
    settings = get_settings()
    keys = parse_key_ring(settings.SOCIAL_TOKEN_ENCRYPTION_KEYS)
    if not keys:
        raise CipherError("SOCIAL_TOKEN_ENCRYPTION_KEYS is not configured")
    return TokenCipher(keys, settings.SOCIAL_TOKEN_ACTIVE_KEY_VERSION)


def generate_key() -> str:
    """A new random key, base64-encoded, for adding to the ring."""
    return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()
