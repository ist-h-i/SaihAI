from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

_DEFAULT_REDACTED = "***REDACTED***"


def is_frontend_request(request: Request, *, allowed_origins: Iterable[str]) -> bool:
    allowed = set(allowed_origins)
    origin = (request.headers.get("origin") or "").strip()
    if origin and origin in allowed:
        return True

    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return False

    try:
        parsed = urlparse(referer)
    except ValueError:
        return False

    if not parsed.scheme or not parsed.netloc:
        return False

    referer_origin = f"{parsed.scheme}://{parsed.netloc}"
    return referer_origin in allowed


def _looks_like_json(content_type: str) -> bool:
    base = (content_type or "").split(";", 1)[0].strip().lower()
    return base == "application/json" or base.endswith("+json")


def _looks_like_text(content_type: str) -> bool:
    base = (content_type or "").split(";", 1)[0].strip().lower()
    return base.startswith("text/") or base in {
        "application/xml",
        "application/x-www-form-urlencoded",
    }


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered == "token_type":
        return False
    if lowered in {
        "password",
        "pass",
        "pwd",
        "jwt",
        "jwt_secret",
        "secret",
        "client_secret",
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "bearer",
        "signing_secret",
        "slack_bot_token",
        "slack_signing_secret",
        "aws_bearer_token_bedrock",
    }:
        return True
    return any(fragment in lowered for fragment in ("password", "secret", "authorization", "bearer")) or (
        "token" in lowered and "token_type" not in lowered
    )


def _redact(value: Any, *, depth: int = 0, max_depth: int = 20) -> Any:
    if depth >= max_depth:
        return "{max_depth_reached}"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _is_sensitive_key(key):
                redacted[key] = _DEFAULT_REDACTED
            else:
                redacted[key] = _redact(v, depth=depth + 1, max_depth=max_depth)
        return redacted
    if isinstance(value, list):
        return [_redact(item, depth=depth + 1, max_depth=max_depth) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, depth=depth + 1, max_depth=max_depth) for item in value)
    return value


def _truncate(text: str, max_chars: int) -> str:
    max_chars = max(0, int(max_chars))
    if max_chars == 0:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...(truncated,{len(text)}chars)"


def _safe_json_dumps(payload: Any, *, max_chars: int) -> str:
    try:
        dumped = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        dumped = "{unserializable_json}"
    return _truncate(dumped, max_chars)


def format_query_params(request: Request, *, max_chars: int) -> str:
    try:
        query = dict(request.query_params)
    except Exception:
        return "-"
    if not query:
        return "-"
    return _safe_json_dumps(_redact(query), max_chars=max_chars)


async def format_request_body(request: Request, *, max_chars: int) -> str:
    content_type = request.headers.get("content-type") or ""
    if "multipart/form-data" in content_type.lower():
        content_length = (request.headers.get("content-length") or "").strip() or "unknown"
        return f"<multipart {content_length} bytes>"

    if not (_looks_like_json(content_type) or _looks_like_text(content_type)):
        base = (content_type or "binary").split(";", 1)[0]
        content_length = (request.headers.get("content-length") or "").strip() or "unknown"
        return f"<{base} {content_length} bytes>"

    try:
        body = await request.body()
    except Exception:
        return "{unreadable_body}"

    if not body:
        return "-"

    if _looks_like_json(content_type):
        try:
            parsed = json.loads(body)
        except Exception:
            decoded = body.decode("utf-8", errors="replace")
            return _truncate(decoded, max_chars)
        return _safe_json_dumps(_redact(parsed), max_chars=max_chars)

    if _looks_like_text(content_type):
        decoded = body.decode("utf-8", errors="replace")
        return _truncate(decoded, max_chars)

    return f"<{(content_type or 'binary').split(';', 1)[0]} {len(body)} bytes>"


def format_response_body(response: Response, *, max_chars: int) -> str:
    if isinstance(response, StreamingResponse):
        return f"<streaming {response.media_type or '-'}>"

    content_type = response.headers.get("content-type") or (response.media_type or "")
    body = getattr(response, "body", b"") or b""
    if not body:
        return "-"

    if _looks_like_json(content_type):
        try:
            parsed = json.loads(body)
        except Exception:
            decoded = body.decode("utf-8", errors="replace")
            return _truncate(decoded, max_chars)
        return _safe_json_dumps(_redact(parsed), max_chars=max_chars)

    if _looks_like_text(content_type):
        decoded = body.decode("utf-8", errors="replace")
        return _truncate(decoded, max_chars)

    return f"<{(content_type or 'binary').split(';', 1)[0]} {len(body)} bytes>"
