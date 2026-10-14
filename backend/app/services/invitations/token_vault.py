"""Encrypt invitation tokens at rest so platform staff can retrieve links without storing plaintext."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def seal_invitation_token(raw_token: str) -> str:
    return _fernet().encrypt(raw_token.encode("utf-8")).decode("ascii")


def unseal_invitation_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("TOKEN_CIPHER_INVALID") from exc
