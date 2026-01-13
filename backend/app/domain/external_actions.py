from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

ACTION_TYPE_EMAIL = "mail_draft"
ACTION_TYPE_CALENDAR = "meeting_request"

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "mock")
CALENDAR_PROVIDER = os.getenv("CALENDAR_PROVIDER", "mock")

DEFAULT_EMAIL_TO = os.getenv("EMAIL_DEFAULT_TO", "manager@example.com")
DEFAULT_EMAIL_FROM = os.getenv("EMAIL_DEFAULT_FROM", "no-reply@saihai.local")
DEFAULT_CALENDAR_ATTENDEE = os.getenv("CALENDAR_DEFAULT_ATTENDEE", DEFAULT_EMAIL_TO)
DEFAULT_CALENDAR_TIMEZONE = os.getenv("CALENDAR_DEFAULT_TIMEZONE", "Asia/Tokyo")


@dataclass(frozen=True)
class EmailPayload:
    to: str
    subject: str
    body: str
    sender: str


@dataclass(frozen=True)
class CalendarPayload:
    attendee: str
    title: str
    start_at: str
    end_at: str
    timezone: str
    description: str | None = None


@dataclass(frozen=True)
class ExternalActionRun:
    run_id: str
    status: str
    provider: str
    action_type: str
    job_id: str
    action_id: int
    response: dict[str, Any] | None = None


class ExternalActionError(RuntimeError):
    pass


def execute_external_action(
    conn: Connection,
    job_id: str,
    action_id: int,
) -> ExternalActionRun | None:
    action = conn.execute(
        text(
            """
            SELECT action_type, draft_content
            FROM autonomous_actions
            WHERE action_id = :action_id
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    if not action:
        raise ValueError("action not found")

    action_type = action.get("action_type")
    if action_type not in (ACTION_TYPE_EMAIL, ACTION_TYPE_CALENDAR):
        return None

    provider_name = EMAIL_PROVIDER if action_type == ACTION_TYPE_EMAIL else CALENDAR_PROVIDER
    payload = _build_payload(action_type, action.get("draft_content"))

    response: dict[str, Any] | None = None
    error: str | None = None
    status = "succeeded"
    try:
        if action_type == ACTION_TYPE_EMAIL:
            response = _send_email(payload)
        else:
            response = _create_calendar_event(payload)
    except Exception as exc:
        status = "failed"
        error = str(exc)

    run_id = f"ext-{uuid4().hex[:12]}"
    result = ExternalActionRun(
        run_id=run_id,
        status=status,
        provider=provider_name,
        action_type=action_type,
        job_id=job_id,
        action_id=action_id,
        response=response,
    )
    if status != "succeeded":
        raise ExternalActionError(error or "external action failed")
    return result


def _build_payload(
    action_type: str,
    draft_content: str | None,
) -> EmailPayload | CalendarPayload:
    payload = _extract_payload_from_draft(draft_content)
    if action_type == ACTION_TYPE_EMAIL:
        subject = str(payload.get("subject") or f"Approval action {action_type}")
        body = str(payload.get("body") or draft_content or "Action executed.")
        to = str(payload.get("to") or DEFAULT_EMAIL_TO)
        sender = str(payload.get("from") or DEFAULT_EMAIL_FROM)
        return EmailPayload(to=to, subject=subject, body=body, sender=sender)

    now = datetime.now(timezone.utc)
    default_start = now + timedelta(days=1)
    default_end = default_start + timedelta(hours=1)
    attendee = str(payload.get("attendee") or DEFAULT_CALENDAR_ATTENDEE)
    title = str(payload.get("title") or f"Approval action {action_type}")
    start_at = str(payload.get("start_at") or payload.get("startAt") or default_start.isoformat())
    end_at = str(payload.get("end_at") or payload.get("endAt") or default_end.isoformat())
    timezone_value = str(payload.get("timezone") or DEFAULT_CALENDAR_TIMEZONE)
    description = payload.get("description") or draft_content
    return CalendarPayload(
        attendee=attendee,
        title=title,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_value,
        description=description,
    )


def _send_email(payload: EmailPayload) -> dict[str, Any]:
    if EMAIL_PROVIDER != "mock":
        raise RuntimeError(f"unsupported EMAIL_PROVIDER={EMAIL_PROVIDER}")
    return {
        "message_id": f"mail-{uuid4().hex[:10]}",
        "to": payload.to,
        "from": payload.sender,
        "subject": payload.subject,
        "status": "sent",
    }


def _create_calendar_event(payload: CalendarPayload) -> dict[str, Any]:
    if CALENDAR_PROVIDER != "mock":
        raise RuntimeError(f"unsupported CALENDAR_PROVIDER={CALENDAR_PROVIDER}")
    return {
        "event_id": f"cal-{uuid4().hex[:10]}",
        "attendee": payload.attendee,
        "title": payload.title,
        "start_at": payload.start_at,
        "end_at": payload.end_at,
        "timezone": payload.timezone,
        "status": "confirmed",
    }


def _extract_payload_from_draft(draft_content: str | None) -> dict[str, Any]:
    if not draft_content:
        return {}
    for line in reversed(draft_content.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}
