from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.engine import Connection

from app.db.connection import engine, get_database_url, is_postgres_engine, is_sqlite_engine


@contextmanager
def db_connection() -> Iterator[Connection]:
    with engine.begin() as conn:
        yield conn


def get_db() -> Iterator[Connection]:
    with engine.begin() as conn:
        yield conn


__all__ = [
    "db_connection",
    "engine",
    "get_database_url",
    "get_db",
    "is_postgres_engine",
    "is_sqlite_engine",
]
