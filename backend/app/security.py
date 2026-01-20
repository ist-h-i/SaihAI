from __future__ import annotations

import base64
import hashlib
import os
from typing import Final

from cryptography.fernet import Fernet


_TOKEN_SECRET: Final[str] = os.getenv("GOOGLE_OAUTH_TOKEN_SECRET") or os.getenv("JWT_SECRET", "dev-secret")


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET: Final[Fernet] = Fernet(_derive_key(_TOKEN_SECRET))


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    encoded = value.encode("utf-8")
    return _FERNET.encrypt(encoded).decode("ascii")


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.encode("ascii")
    return _FERNET.decrypt(raw).decode("utf-8")
