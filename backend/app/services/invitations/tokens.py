from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(expected_hash: str, token: str) -> bool:
    digest = hash_token(token)
    return hmac.compare_digest(expected_hash, digest)
