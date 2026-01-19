from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Iterator

from fastapi import HTTPException
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError

from app.db.connection import engine, get_database_url, is_postgres_engine, is_sqlite_engine

logger = logging.getLogger("saihai.db")


@contextmanager
def db_connection() -> Iterator[Connection]:
    with engine.begin() as conn:
        yield conn


def get_db() -> Iterator[Connection]:
    ctx = engine.begin()
    try:
        conn = ctx.__enter__()
    except OperationalError as exc:
        logger.warning("Database connection failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    exit_exc_type = None
    exit_exc = None
    exit_tb = None
    try:
        yield conn
    except Exception:
        exit_exc_type, exit_exc, exit_tb = sys.exc_info()
        raise
    finally:
        ctx.__exit__(exit_exc_type, exit_exc, exit_tb)


__all__ = [
    "db_connection",
    "engine",
    "get_database_url",
    "get_db",
    "is_postgres_engine",
    "is_sqlite_engine",
]
