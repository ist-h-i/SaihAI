from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.repository import (
    GoogleOAuthToken,
    fetch_google_oauth_token_by_email,
    fetch_google_oauth_token_by_user,
    upsert_google_oauth_token,
)
from app.integrations.google_calendar import create_google_calendar_event, refresh_google_access_token

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
DEFAULT_CALENDAR_OWNER_EMAIL = os.getenv("CALENDAR_DEFAULT_OWNER_EMAIL", "")

logger = logging.getLogger("saihai.external_actions")


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
    meeting_url: str | None = None
    owner_email: str | None = None
    owner_user_id: str | None = None


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
    payload_override: dict[str, Any] | None = None,
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

    if payload_override:
        payload = _coerce_payload(action_type, payload_override)
    else:
        payload = _build_payload(action_type, draft_content)

    if action_type == ACTION_TYPE_CALENDAR:
        run = _execute_single_action(
            conn, job_id, action_id, action_type, payload, raise_on_error=False
        )
        if run.status != "succeeded":
            _log_calendar_failure(action_id, job_id, payload, run.error)
        return run

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
    if action_type == ACTION_TYPE_CALENDAR:
        now = datetime.now(timezone.utc)
        default_start = now + timedelta(days=1)
        default_end = default_start + timedelta(hours=1)
        attendee = str(payload.get("attendee") or DEFAULT_CALENDAR_ATTENDEE)
        title = str(payload.get("title") or f"Approval action {action_type}")
        start_at = str(payload.get("start_at") or payload.get("startAt") or default_start.isoformat())
        end_at = str(payload.get("end_at") or payload.get("endAt") or default_end.isoformat())
        timezone_value = str(payload.get("timezone") or DEFAULT_CALENDAR_TIMEZONE)
        description = payload.get("description") or draft_content
        meeting_url = _normalize_meeting_url(payload)
        owner_email, owner_user_id = _resolve_calendar_owner(payload)
        return CalendarPayload(
            attendee=attendee,
            title=title,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone_value,
            description=description,
            meeting_url=meeting_url,
            owner_email=owner_email,
            owner_user_id=owner_user_id,
        )
    if action_type == ACTION_TYPE_HR:
        if isinstance(payload.get("hr_request"), dict):
            return payload.get("hr_request") or {}
        return payload or {"request": draft_content or ""}
    return payload


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


def _create_calendar_event(conn: Connection, payload: CalendarPayload) -> dict[str, Any]:
    if CALENDAR_PROVIDER == "mock":
        return {
            "event_id": f"cal-{uuid4().hex[:10]}",
            "attendee": payload.attendee,
            "title": payload.title,
            "start_at": payload.start_at,
            "end_at": payload.end_at,
            "timezone": payload.timezone,
            "meeting_url": payload.meeting_url,
            "status": "confirmed",
        }
    if CALENDAR_PROVIDER == "google":
        return _create_google_calendar_event(conn, payload)
    raise RuntimeError(f"unsupported CALENDAR_PROVIDER={CALENDAR_PROVIDER}")


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


def _normalize_meeting_url(payload: dict[str, Any]) -> str | None:
    raw = payload.get("meeting_url") or payload.get("meetingUrl")
    if not raw:
        return None
    value = str(raw).strip()
    return value or None


def _resolve_calendar_owner(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    owner_email = payload.get("owner_email") or payload.get("ownerEmail") or payload.get("owner")
    owner_user_id = payload.get("owner_user_id") or payload.get("ownerUserId")
    resolved_email = str(owner_email).strip() if owner_email else ""
    resolved_user = str(owner_user_id).strip() if owner_user_id else ""
    if not resolved_email and DEFAULT_CALENDAR_OWNER_EMAIL:
        resolved_email = DEFAULT_CALENDAR_OWNER_EMAIL.strip()
    return (resolved_email or None, resolved_user or None)


def _create_google_calendar_event(conn: Connection, payload: CalendarPayload) -> dict[str, Any]:
    token = _resolve_google_oauth_token(conn, payload)
    access_token = token.access_token
    expires_at = token.expires_at
    if expires_at and expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
        access_token, expires_at = _refresh_google_token(conn, token)

    event_payload = _payload_to_dict(payload)
    event_payload.pop("owner_email", None)
    event_payload.pop("owner_user_id", None)
    return create_google_calendar_event(access_token, event_payload)


def _resolve_google_oauth_token(conn: Connection, payload: CalendarPayload) -> GoogleOAuthToken:
    token: GoogleOAuthToken | None = None
    if payload.owner_user_id:
        token = fetch_google_oauth_token_by_user(conn, payload.owner_user_id)
    if not token and payload.owner_email:
        token = fetch_google_oauth_token_by_email(conn, payload.owner_email)
    if not token and DEFAULT_CALENDAR_OWNER_EMAIL:
        token = fetch_google_oauth_token_by_email(conn, DEFAULT_CALENDAR_OWNER_EMAIL)
    if not token:
        raise RuntimeError("google oauth token not found for calendar owner")
    return token


def _refresh_google_token(
    conn: Connection,
    token: GoogleOAuthToken,
) -> tuple[str, datetime | None]:
    refreshed = refresh_google_access_token(token.refresh_token)
    access_token = refreshed.get("access_token")
    if not access_token:
        raise RuntimeError("google oauth refresh failed")
    expires_in = refreshed.get("expires_in")
    expires_at = None
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None
    upsert_google_oauth_token(
        conn,
        user_id=token.user_id,
        google_email=token.google_email,
        access_token=str(access_token),
        refresh_token=None,
        token_type=refreshed.get("token_type") or token.token_type,
        scope=refreshed.get("scope") or token.scope,
        expires_at=expires_at,
    )
    return str(access_token), expires_at


def _log_calendar_failure(
    action_id: int,
    job_id: str,
    payload: EmailPayload | CalendarPayload | dict[str, Any],
    error: str | None,
) -> None:
    owner_email = None
    attendee = None
    if isinstance(payload, CalendarPayload):
        owner_email = payload.owner_email
        attendee = payload.attendee
    elif isinstance(payload, dict):
        owner_email = payload.get("owner_email") or payload.get("ownerEmail")
        attendee = payload.get("attendee")
    logger.error(
        "calendar event failed action_id=%s job_id=%s owner=%s attendee=%s error=%s",
        action_id,
        job_id,
        owner_email,
        attendee,
        error or "unknown error",
    )


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
            response = _create_calendar_event(conn, payload)
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
        owner_email, owner_user_id = _resolve_calendar_owner(payload)
        return CalendarPayload(
            attendee=str(payload.get("attendee") or DEFAULT_CALENDAR_ATTENDEE),
            title=str(payload.get("title") or "Meeting"),
            start_at=str(payload.get("start_at") or payload.get("startAt") or default_start.isoformat()),
            end_at=str(payload.get("end_at") or payload.get("endAt") or default_end.isoformat()),
            timezone=str(payload.get("timezone") or DEFAULT_CALENDAR_TIMEZONE),
            description=payload.get("description"),
            meeting_url=_normalize_meeting_url(payload),
            owner_email=owner_email,
            owner_user_id=owner_user_id,
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
                if run.action_type == ACTION_TYPE_CALENDAR:
                    _log_calendar_failure(action_id, job_id, payload, run.error)
                else:
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
            "meeting_url": payload.meeting_url,
            "owner_email": payload.owner_email,
            "owner_user_id": payload.owner_user_id,
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
