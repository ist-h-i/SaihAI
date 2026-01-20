from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from app.auth import AuthUser, get_current_user
from app.db import get_db
from app.domain.hitl import (
    ApprovalResult,
    ExecutionJobResult,
    apply_steer,
    approve_request,
    fetch_audit_logs,
    process_execution_job,
    reject_request,
    request_approval,
)

router = APIRouter(prefix="/v1", tags=["hitl"])


class SlackMetaResponse(BaseModel):
    channel: str
    message_ts: str
    thread_ts: str | None = None


class ApprovalRequestResponse(BaseModel):
    thread_id: str
    approval_request_id: str
    status: str
    action_id: int
    slack: SlackMetaResponse | None = None


class ApprovalDecisionResponse(BaseModel):
    job_id: str
    status: str
    thread_id: str
    action_id: int


class SteerRequest(BaseModel):
    feedback: str = Field(min_length=1)
    selectedPlan: str | None = None
    idempotencyKey: str | None = None


class CalendarExecuteRequest(BaseModel):
    ownerEmail: str | None = None
    attendee: str = Field(min_length=1)
    title: str = Field(min_length=1)
    startAt: str = Field(min_length=1)
    endAt: str = Field(min_length=1)
    timezone: str | None = None
    description: str | None = None
    meetingUrl: str | None = None


class ExecuteRequest(BaseModel):
    simulateFailure: bool = False
    calendar: CalendarExecuteRequest | None = None


@router.post(
    "/nemawashi/{draft_id}/request-approval",
    response_model=ApprovalRequestResponse,
)
def request_approval_api(
    draft_id: int,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> ApprovalRequestResponse:
    try:
        result = request_approval(conn, action_id=draft_id, requested_by=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_approval_response(result)


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalDecisionResponse,
)
def approve_api(
    approval_id: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> ApprovalDecisionResponse:
    try:
        job = approve_request(conn, approval_id, user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _to_job_response(job)


@router.post("/approvals/{approval_id}/reject")
def reject_api(
    approval_id: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> dict:
    try:
        reject_request(conn, approval_id, user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "rejected"}


@router.post(
    "/approvals/{approval_id}/steer",
    response_model=ApprovalRequestResponse,
)
def steer_api(
    approval_id: str,
    req: SteerRequest,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> ApprovalRequestResponse:
    try:
        result = apply_steer(
            conn,
            approval_request_id=approval_id,
            actor=user.user_id,
            feedback=req.feedback,
            selected_plan=req.selectedPlan,
            idempotency_key=req.idempotencyKey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _to_approval_response(result)


@router.post(
    "/nemawashi/{draft_id}/execute",
    response_model=ApprovalDecisionResponse,
)
def execute_api(
    draft_id: int,
    req: ExecuteRequest,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> ApprovalDecisionResponse:
    payload_override = None
    if req.calendar:
        payload_override = {
            "owner_email": req.calendar.ownerEmail,
            "owner_user_id": user.user_id,
            "attendee": req.calendar.attendee,
            "title": req.calendar.title,
            "start_at": req.calendar.startAt,
            "end_at": req.calendar.endAt,
            "timezone": req.calendar.timezone,
            "description": req.calendar.description,
            "meeting_url": req.calendar.meetingUrl,
        }
    try:
        job = process_execution_job(
            conn,
            action_id=draft_id,
            simulate_failure=req.simulateFailure,
            payload_override=payload_override,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_job_response(job)


@router.get("/audit/{thread_id}")
def audit_api(
    thread_id: str,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> dict:
    return {"thread_id": thread_id, "events": fetch_audit_logs(conn, thread_id)}


def _to_approval_response(result: ApprovalResult) -> ApprovalRequestResponse:
    slack = None
    if result.slack:
        slack = SlackMetaResponse(
            channel=result.slack.channel,
            message_ts=result.slack.message_ts,
            thread_ts=result.slack.thread_ts,
        )
    return ApprovalRequestResponse(
        thread_id=result.thread_id,
        approval_request_id=result.approval_request_id,
        status=result.status,
        action_id=result.action_id,
        slack=slack,
    )


def _to_job_response(job: ExecutionJobResult) -> ApprovalDecisionResponse:
    return ApprovalDecisionResponse(
        job_id=job.job_id,
        status=job.status,
        thread_id=job.thread_id,
        action_id=job.action_id,
    )
