import logging
import time
from urllib.parse import urlparse
from uuid import uuid4

from app.env import load_env

load_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.slack import router as slack_router
from app.http_logging import (
    format_query_params,
    format_request_body,
    format_response_body,
    is_frontend_request,
)
from app.logging_config import configure_logging, request_id_var
from app.settings import settings

configure_logging(level=settings.log_level, log_file=settings.log_file)
http_logger = logging.getLogger("saihai.http")
http_logger.setLevel(logging.INFO)
startup_logger = logging.getLogger("saihai.startup")


def _describe_database_url(database_url: str) -> str:
    database_url = (database_url or "").strip()
    if not database_url:
        return "sqlite:///./saihai.db"
    if database_url.startswith("sqlite"):
        return database_url
    parsed = urlparse(database_url)
    host = parsed.hostname or "-"
    port = parsed.port or "-"
    database = parsed.path.lstrip("/") or "-"
    scheme = parsed.scheme or "db"
    return f"{scheme}://{host}:{port}/{database}"


try:
    from app.db import get_database_url

    startup_logger.info("Database target: %s", _describe_database_url(get_database_url()))
except Exception:
    startup_logger.exception("Failed to resolve database URL for startup log")

app = FastAPI(title="SaihAI API", version="0.1.0")

@app.middleware("http")
async def http_request_logger(request, call_next):
    if not settings.log_http_requests:
        return await call_next(request)

    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    log_body = settings.log_http_bodies and is_frontend_request(
        request, allowed_origins=settings.cors_origins
    )
    if log_body:
        query_dump = format_query_params(request, max_chars=settings.log_http_body_max_chars)
        body_dump = await format_request_body(request, max_chars=settings.log_http_body_max_chars)
        http_logger.info(
            "payload %s %s query=%s body=%s",
            request.method,
            request.url.path,
            query_dump,
            body_dump,
        )
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        http_logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        if log_body:
            http_logger.info(
                "response %s %s -> %s body=%s",
                request.method,
                request.url.path,
                response.status_code,
                format_response_body(response, max_chars=settings.log_http_body_max_chars),
            )
        return response
    except Exception:
        http_logger.exception("%s %s -> unhandled exception", request.method, request.url.path)
        raise
    finally:
        request_id_var.reset(token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(slack_router)
