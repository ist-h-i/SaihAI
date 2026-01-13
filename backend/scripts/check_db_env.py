from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.env import load_env  # noqa: E402

load_env()

from app.db import engine  # noqa: E402


def _find_env_path() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".env",
        here.parents[2] / ".env",
        here.parents[1] / ".env",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def main() -> int:
    env_path = _find_env_path()
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        print("DATABASE_URL is not set.")
        if env_path:
            print(f"Detected env file: {env_path}")
        return 1

    url = make_url(database_url)
    print(f"env_file={env_path or '-'}")
    print(f"database_url={url.render_as_string(hide_password=True)}")
    print(f"dialect={url.get_backend_name()} driver={url.get_driver_name()}")
    print(f"host={url.host or '-'} port={url.port or '-'} db={url.database or '-'} user={url.username or '-'}")
    print(f"sslmode={url.query.get('sslmode') if url.query else None}")
    print(f"engine_dialect={engine.dialect.name}")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("connection=ok")
    except Exception as exc:
        print(f"connection=failed ({exc})")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
