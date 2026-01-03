import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.slack import router as slack_router
from app.logging_config import configure_logging, request_id_var
from app.settings import settings

configure_logging(level=settings.log_level, log_file=settings.log_file)
http_logger = logging.getLogger("saihai.http")

app = FastAPI(title="SaihAI API", version="0.1.0")

@app.middleware("http")
async def http_request_logger(request, call_next):
    if not settings.log_http_requests:
        return await call_next(request)

    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_var.set(request_id)
    started = time.perf_counter()
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
