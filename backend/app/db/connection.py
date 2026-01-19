from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    return url or "sqlite:///./saihai.db"


def _normalize_database_url(database_url: str) -> str:
    database_url = (database_url or "").strip()

    if database_url.startswith(("http://", "https://")):
        raise RuntimeError(
            "DATABASE_URL looks like an HTTP URL. "
            "Set DATABASE_URL to a PostgreSQL URL like "
            "`postgresql+psycopg://<user>:<password>@<host>:5432/<db>`."
        )

    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]

    return database_url


def create_db_engine() -> Engine:
    database_url = _normalize_database_url(get_database_url())
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5") or "5")
        if connect_timeout > 0:
            connect_args["connect_timeout"] = connect_timeout

        application_name = (os.getenv("DB_APPLICATION_NAME") or "saihai-backend").strip()
        if application_name:
            connect_args["application_name"] = application_name

        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800") or "1800")
        if pool_recycle > 0:
            engine_kwargs["pool_recycle"] = pool_recycle

    return create_engine(database_url, **engine_kwargs)


engine = create_db_engine()


def is_sqlite_engine(target: Engine) -> bool:
    return target.dialect.name == "sqlite"


def is_postgres_engine(target: Engine) -> bool:
    return target.dialect.name.startswith("postgres")
