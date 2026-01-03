from __future__ import annotations

import os
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from app.db import get_db
from app.domain.watchdog import enqueue_watchdog_job, run_watchdog_job

router = APIRouter(prefix="/api/v1", tags=["watchdog"])


class WatchdogEnqueueRequest(BaseModel):
    payload: dict | None = None


class WatchdogRunRequest(BaseModel):
    job_id: str | None = None
    auto_enqueue: bool = True


@router.post("/watchdog/enqueue")
def watchdog_enqueue(
    req: WatchdogEnqueueRequest,
    conn: Connection = Depends(get_db),
    x_internal_token: str | None = Header(default=None),
) -> dict:
    _require_internal(x_internal_token)
    return enqueue_watchdog_job(conn, payload=req.payload)


@router.post("/watchdog/run")
def watchdog_run(
    req: WatchdogRunRequest,
    conn: Connection = Depends(get_db),
    x_internal_token: str | None = Header(default=None),
) -> dict:
    _require_internal(x_internal_token)
    try:
        return run_watchdog_job(conn, job_id=req.job_id)
    except ValueError:
        if not req.auto_enqueue:
            raise HTTPException(status_code=404, detail="no queued job")
        job = enqueue_watchdog_job(conn, payload=None)
        return run_watchdog_job(conn, job_id=job["job_id"])


def _require_internal(token: str | None) -> None:
    expected = os.getenv("INTERNAL_API_TOKEN")
    if expected and token != expected:
        raise HTTPException(status_code=403, detail="internal token required")
