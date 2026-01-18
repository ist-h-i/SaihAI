from fastapi import APIRouter
from sqlalchemy import text

from app.db import db_connection

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    database = "ok"
    error = None
    try:
        with db_connection() as conn:
            conn.execute(text("SELECT 1")).scalar()
    except Exception as exc:
        database = "error"
        error = str(exc)
    status = "ok" if database == "ok" else "degraded"
    payload = {"status": status, "database": database}
    if error:
        payload["error"] = error
    return payload
