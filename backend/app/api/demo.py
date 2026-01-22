from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from app.auth import AuthUser, get_current_user
from app.db import get_db
from app.domain.demo import start_demo

router = APIRouter(prefix="/v1/demo", tags=["demo"])


class DemoSlackMetaResponse(BaseModel):
    channel: str
    message_ts: str
    thread_ts: str | None = None


class DemoStartResponse(BaseModel):
    alertId: str
    status: str
    slack: DemoSlackMetaResponse | None = None


@router.post("/start", response_model=DemoStartResponse)
def demo_start(
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> DemoStartResponse:
    try:
        result = start_demo(conn, requested_by=user.user_id, requested_by_name=user.name)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    slack = None
    if result.slack:
        slack = DemoSlackMetaResponse(
            channel=str(result.slack.get("channel") or ""),
            message_ts=str(result.slack.get("message_ts") or ""),
            thread_ts=result.slack.get("thread_ts"),
        )

    return DemoStartResponse(alertId=result.alert_id, status=result.status, slack=slack)
