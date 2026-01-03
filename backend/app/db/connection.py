from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./saihai.db")


def create_db_engine() -> Engine:
    database_url = get_database_url()
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = create_db_engine()


def is_sqlite_engine(target: Engine) -> bool:
    return target.dialect.name == "sqlite"


def is_postgres_engine(target: Engine) -> bool:
    return target.dialect.name.startswith("postgres")

