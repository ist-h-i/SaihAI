import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    log_level: str
    log_file: str | None
    log_http_requests: bool
    log_http_bodies: bool
    log_http_body_max_chars: int


settings = Settings(
    cors_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    log_file=(os.getenv("LOG_FILE") or "").strip() or None,
    log_http_requests=os.getenv("LOG_HTTP_REQUESTS", "1").lower() not in {"0", "false", "no"},
    log_http_bodies=(
        os.getenv("LOG_HTTP_BODIES", "").lower() not in {"0", "false", "no"}
        if "LOG_HTTP_BODIES" in os.environ
        else os.getenv("LOG_HTTP_REQUESTS", "1").lower() not in {"0", "false", "no"}
    ),
    log_http_body_max_chars=max(0, min(200_000, int(os.getenv("LOG_HTTP_BODY_MAX_CHARS", "8000") or "8000"))),
)
