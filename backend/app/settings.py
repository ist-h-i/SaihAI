import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    log_level: str
    log_file: str | None
    log_http_requests: bool


settings = Settings(
    cors_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    log_file=(os.getenv("LOG_FILE") or "").strip() or None,
    log_http_requests=os.getenv("LOG_HTTP_REQUESTS", "1").lower() not in {"0", "false", "no"},
)
