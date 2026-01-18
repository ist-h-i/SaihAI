from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

ACTION_TYPE_EMAIL = "mail_draft"
ACTION_TYPE_CALENDAR = "meeting_request"
ACTION_TYPE_HR = "hr_request"

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "mock")
CALENDAR_PROVIDER = os.getenv("CALENDAR_PROVIDER", "mock")
HR_PROVIDER = os.getenv("HR_PROVIDER", "mock")
HR_API_URL = os.getenv("HR_API_URL", "")

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
    error: str | None = None
    executed_at: str | None = None


class ExternalActionError(RuntimeError):
    pass


def execute_external_action(
    conn: Connection,
    job_id: str,
    action_id: int,
) -> ExternalActionRun | list[ExternalActionRun] | None:
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
    if action_type not in (ACTION_TYPE_EMAIL, ACTION_TYPE_CALENDAR, ACTION_TYPE_HR):
        return None

    draft_content = action.get("draft_content")
    raw_payload = _extract_payload_from_draft(draft_content)
    if isinstance(raw_payload.get("actions"), list):
        return _execute_batch_actions(conn, job_id, action_id, raw_payload.get("actions") or [])

    payload = _build_payload(action_type, draft_content)
    return _execute_single_action(conn, job_id, action_id, action_type, payload)


def _build_payload(
    action_type: str,
    draft_content: str | None,
) -> EmailPayload | CalendarPayload | dict[str, Any]:
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

    if action_type == ACTION_TYPE_HR:
        if isinstance(payload.get("hr_request"), dict):
            return payload.get("hr_request") or {}
        return payload or {"request": draft_content or ""}


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


def _send_hr_request(payload: dict[str, Any]) -> dict[str, Any]:
    if HR_PROVIDER != "mock":
        if not HR_API_URL:
            raise RuntimeError("HR_API_URL is not configured")
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            HR_API_URL,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"HR API error: {exc}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"status": "accepted", "raw": body}
    return {"request_id": f"hr-{uuid4().hex[:10]}", "status": "submitted"}


def _execute_single_action(
    conn: Connection,
    job_id: str,
    action_id: int,
    action_type: str,
    payload: EmailPayload | CalendarPayload | dict[str, Any],
    *,
    raise_on_error: bool = True,
) -> ExternalActionRun:
    payload = _coerce_payload(action_type, payload)
    if action_type == ACTION_TYPE_EMAIL:
        provider_name = EMAIL_PROVIDER
    elif action_type == ACTION_TYPE_CALENDAR:
        provider_name = CALENDAR_PROVIDER
    else:
        provider_name = HR_PROVIDER

    response: dict[str, Any] | None = None
    error: str | None = None
    status = "succeeded"
    try:
        if action_type == ACTION_TYPE_EMAIL:
            response = _send_email(payload)
        elif action_type == ACTION_TYPE_HR:
            response = _send_hr_request(payload)
        else:
            response = _create_calendar_event(payload)
    except Exception as exc:
        status = "failed"
        error = str(exc)

    run_id = f"ext-{uuid4().hex[:12]}"
    executed_at = datetime.now(timezone.utc).isoformat()
    result = ExternalActionRun(
        run_id=run_id,
        status=status,
        provider=provider_name,
        action_type=action_type,
        job_id=job_id,
        action_id=action_id,
        response=response,
        error=error,
        executed_at=executed_at,
    )
    _record_external_action_run(
        conn,
        result,
        payload=_payload_to_dict(payload),
    )
    if status != "succeeded" and raise_on_error:
        raise ExternalActionError(error or "external action failed")
    return result


def _coerce_payload(
    action_type: str,
    payload: EmailPayload | CalendarPayload | dict[str, Any],
) -> EmailPayload | CalendarPayload | dict[str, Any]:
    if isinstance(payload, (EmailPayload, CalendarPayload)):
        return payload
    if action_type == ACTION_TYPE_EMAIL:
        return EmailPayload(
            to=str(payload.get("to") or DEFAULT_EMAIL_TO),
            subject=str(payload.get("subject") or "Follow-up"),
            body=str(payload.get("body") or payload.get("content") or ""),
            sender=str(payload.get("from") or DEFAULT_EMAIL_FROM),
        )
    if action_type == ACTION_TYPE_CALENDAR:
        now = datetime.now(timezone.utc)
        default_start = now + timedelta(days=1)
        default_end = default_start + timedelta(hours=1)
        return CalendarPayload(
            attendee=str(payload.get("attendee") or DEFAULT_CALENDAR_ATTENDEE),
            title=str(payload.get("title") or "Meeting"),
            start_at=str(payload.get("start_at") or default_start.isoformat()),
            end_at=str(payload.get("end_at") or default_end.isoformat()),
            timezone=str(payload.get("timezone") or DEFAULT_CALENDAR_TIMEZONE),
            description=payload.get("description"),
        )
    return payload


def _execute_batch_actions(
    conn: Connection,
    job_id: str,
    action_id: int,
    actions: list[dict[str, Any]],
) -> list[ExternalActionRun]:
    results: list[ExternalActionRun] = []
    errors: list[str] = []
    for item in actions:
        action_type = str(item.get("type") or item.get("action_type") or "")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if action_type not in (ACTION_TYPE_EMAIL, ACTION_TYPE_CALENDAR, ACTION_TYPE_HR):
            continue
        try:
            run = _execute_single_action(
                conn,
                job_id,
                action_id,
                action_type,
                payload,
                raise_on_error=False,
            )
            results.append(run)
            if run.status != "succeeded":
                errors.append(run.error or "unknown error")
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise ExternalActionError("; ".join(errors))
    return results


def _payload_to_dict(payload: EmailPayload | CalendarPayload | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, EmailPayload):
        return {"to": payload.to, "subject": payload.subject, "body": payload.body, "from": payload.sender}
    if isinstance(payload, CalendarPayload):
        return {
            "attendee": payload.attendee,
            "title": payload.title,
            "start_at": payload.start_at,
            "end_at": payload.end_at,
            "timezone": payload.timezone,
            "description": payload.description,
        }
    return payload


def _record_external_action_run(
    conn: Connection,
    run: ExternalActionRun,
    *,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO external_action_runs
              (action_type, status, payload, job_id, action_id, provider, response, error, executed_at)
            VALUES
              (:action_type, :status, :payload, :job_id, :action_id, :provider, :response, :error, :executed_at)
            """
        ),
        {
            "action_type": run.action_type,
            "status": run.status,
            "payload": json.dumps(payload, ensure_ascii=False),
            "job_id": run.job_id,
            "action_id": run.action_id,
            "provider": run.provider,
            "response": json.dumps(run.response or {}, ensure_ascii=False),
            "error": run.error,
            "executed_at": run.executed_at,
        },
    )


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
