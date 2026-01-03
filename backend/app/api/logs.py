from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/logs", tags=["logs"])

_frontend_logger = logging.getLogger("saihai.frontend")

_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}


class FrontendLogPayload(BaseModel):
    level: Literal["debug", "info", "warn", "error"] = "info"
    message: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] | None = None
    timestamp: str | None = None
    url: str | None = None
    userAgent: str | None = None


@router.post("/frontend")
async def ingest_frontend_log(payload: FrontendLogPayload, request: Request) -> dict[str, bool]:
    context_dump = ""
    if payload.context:
        try:
            context_dump = json.dumps(payload.context, ensure_ascii=False, default=str)[:8000]
        except Exception:
            context_dump = "{unserializable_context}"

    level = _LEVEL_MAP.get(payload.level, logging.INFO)
    client = request.client.host if request.client else "unknown"
    if context_dump:
        _frontend_logger.log(
            level,
            "frontend[%s] %s | url=%s ua=%s ctx=%s",
            client,
            payload.message,
            payload.url or "-",
            payload.userAgent or "-",
            context_dump,
        )
    else:
        _frontend_logger.log(
            level,
            "frontend[%s] %s | url=%s ua=%s",
            client,
            payload.message,
            payload.url or "-",
            payload.userAgent or "-",
        )
    return {"ok": True}

