from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.engine import Connection

from app.db import get_db
from app.db.repository import fetch_user


JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "480"))


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    name: str
    role: str | None = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(message: bytes) -> str:
    digest = hmac.new(JWT_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def encode_jwt(payload: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{header_b64}.{payload_b64}.{signature}"


def decode_jwt(token: str) -> dict[str, object]:
    try:
        header_b64, payload_b64, signature = token.split(".")
    except ValueError as exc:  # pragma: no cover - malformed token
        raise ValueError("invalid token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    if not hmac.compare_digest(signature, _sign(signing_input)):
        raise ValueError("invalid signature")

    payload_raw = _b64url_decode(payload_b64)
    payload = json.loads(payload_raw.decode("utf-8"))
    if isinstance(payload, dict):
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            now = datetime.now(timezone.utc).timestamp()
            if now > exp:
                raise ValueError("token expired")
        return payload
    raise ValueError("invalid payload")


def issue_token(user: dict[str, object]) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_TTL_MINUTES)
    payload = {
        "sub": str(user["user_id"]),
        "role": user.get("role"),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return encode_jwt(payload)


def get_current_user(
    authorization: str | None = Header(default=None),
    conn: Connection = Depends(get_db),
) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        payload = decode_jwt(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token")
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="invalid token")
    user = fetch_user(conn, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return AuthUser(user_id=user["user_id"], name=user["name"], role=user.get("role"))
