from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.repository import (
    fetch_google_oauth_token_by_email,
    fetch_google_oauth_token_by_user,
    upsert_google_oauth_token,
)
from app.domain.external_actions import (
    CALENDAR_PROVIDER,
    DEFAULT_CALENDAR_ATTENDEE,
    DEFAULT_CALENDAR_OWNER_EMAIL,
    DEFAULT_CALENDAR_TIMEZONE,
)
from app.integrations.google_calendar import create_google_calendar_event, refresh_google_access_token
from app.integrations.slack import (
    post_demo_alert,
    post_demo_approval_prompt,
    post_demo_retry_prompt,
    post_thread_message,
)

logger = logging.getLogger("saihai.demo")

DEMO_CALENDAR_ID = (os.getenv("DEMO_CALENDAR_ID") or os.getenv("CALENDAR_ID") or "primary").strip()
DEMO_TIMEZONE = os.getenv("DEMO_TIMEZONE", DEFAULT_CALENDAR_TIMEZONE)
DEFAULT_INVITEE_EMAILS = ["demo-invitee@example.com"]
INVITEE_EMAILS_ENV = os.getenv("INVITEE_EMAILS", "").strip()
APPROVER_USER_IDS_ENV = os.getenv("APPROVER_USER_IDS", "").strip()

DEMO_STATUS_ALERTED = "alerted"
DEMO_STATUS_PLAN_SELECTED = "plan_selected"
DEMO_STATUS_INTERVENED = "intervened"
DEMO_STATUS_APPROVAL_PENDING = "approval_pending"
DEMO_STATUS_APPROVED = "approved"
DEMO_STATUS_REJECTED = "rejected"
DEMO_STATUS_CANCELLED = "cancelled"
DEMO_STATUS_CALENDAR_CREATING = "calendar_creating"
DEMO_STATUS_CALENDAR_CREATED = "calendar_created"
DEMO_STATUS_CALENDAR_FAILED = "calendar_failed"


@dataclass(frozen=True)
class DemoStartResult:
    alert_id: str
    status: str
    slack: dict | None = None


def start_demo(conn: Connection, *, requested_by: str, requested_by_name: str | None = None) -> DemoStartResult:
    alert_id = f"alert-{uuid4().hex[:12]}"
    slack_meta = post_demo_alert(alert_id)
    if not slack_meta:
        raise RuntimeError("slack demo alert failed")

    metadata = {
        "alert_id": alert_id,
        "status": DEMO_STATUS_ALERTED,
        "requested_by": requested_by,
        "requested_by_name": requested_by_name,
        "owner_user_id": requested_by,
        "owner_email": DEFAULT_CALENDAR_OWNER_EMAIL or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "slack": {
            "channel": slack_meta.channel,
            "message_ts": slack_meta.message_ts,
            "thread_ts": slack_meta.thread_ts,
        },
    }
    _upsert_demo_metadata(conn, alert_id, metadata)
    return DemoStartResult(
        alert_id=alert_id,
        status=DEMO_STATUS_ALERTED,
        slack=metadata.get("slack"),
    )


def record_demo_plan_selection(
    *,
    alert_id: str,
    actor: str | None,
    plan: str,
    idempotency_key: str | None,
) -> None:
    with _demo_db() as conn:
        metadata = _load_demo_metadata(conn, alert_id)
        if not metadata:
            logger.warning("demo plan selection ignored (missing alert_id=%s)", alert_id)
            return
        if _idempotency_seen(metadata, idempotency_key):
            return
        _record_idempotency_key(metadata, idempotency_key)

        normalized = _normalize_plan(plan)
        if not normalized:
            logger.warning("demo plan selection invalid plan=%s alert_id=%s", plan, alert_id)
            return
        if metadata.get("status") in {DEMO_STATUS_REJECTED, DEMO_STATUS_CANCELLED}:
            _notify_thread(metadata, "すでに終了しています。新しいデモを開始してください。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return
        if metadata.get("status") in {DEMO_STATUS_APPROVED, DEMO_STATUS_CALENDAR_CREATING, DEMO_STATUS_CALENDAR_CREATED}:
            _notify_thread(metadata, "すでにApprove済みです。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        metadata["plan"] = normalized
        metadata["plan_selected_by"] = actor
        metadata["plan_selected_at"] = datetime.now(timezone.utc).isoformat()
        metadata["status"] = DEMO_STATUS_APPROVAL_PENDING
        metadata["approval_status"] = DEMO_STATUS_APPROVAL_PENDING
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, metadata)

        summary = _build_demo_summary(metadata)
        _post_demo_prompt(metadata, summary)


def record_demo_intervention(
    *,
    alert_id: str,
    actor: str | None,
    intervention: str,
    idempotency_key: str | None,
) -> None:
    with _demo_db() as conn:
        metadata = _load_demo_metadata(conn, alert_id)
        if not metadata:
            logger.warning("demo intervention ignored (missing alert_id=%s)", alert_id)
            return
        if _idempotency_seen(metadata, idempotency_key):
            return
        _record_idempotency_key(metadata, idempotency_key)

        if metadata.get("status") in {DEMO_STATUS_APPROVED, DEMO_STATUS_CALENDAR_CREATING, DEMO_STATUS_CALENDAR_CREATED}:
            _notify_thread(metadata, "すでにApprove済みです。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return
        if metadata.get("status") in {DEMO_STATUS_REJECTED, DEMO_STATUS_CANCELLED}:
            _notify_thread(metadata, "すでに終了しています。新しいデモを開始してください。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        trimmed = intervention.strip()
        if not trimmed:
            return
        metadata["intervention"] = trimmed
        metadata["intervention_by"] = actor
        metadata["intervention_at"] = datetime.now(timezone.utc).isoformat()
        metadata["status"] = DEMO_STATUS_APPROVAL_PENDING
        metadata["approval_status"] = DEMO_STATUS_APPROVAL_PENDING
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, metadata)

        summary = _build_demo_summary(metadata)
        _post_demo_prompt(metadata, summary)


def approve_demo(
    *,
    alert_id: str,
    actor: str | None,
    idempotency_key: str | None,
) -> None:
    phase1_metadata = None
    with _demo_db() as conn:
        metadata = _load_demo_metadata(conn, alert_id, for_update=True)
        if not metadata:
            logger.warning("demo approve ignored (missing alert_id=%s)", alert_id)
            return
        if _idempotency_seen(metadata, idempotency_key):
            return
        _record_idempotency_key(metadata, idempotency_key)

        if metadata.get("status") in {DEMO_STATUS_REJECTED, DEMO_STATUS_CANCELLED}:
            _notify_thread(metadata, "すでにReject/Cancelされています。新しいデモを開始してください。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        if not _is_actor_allowed(actor):
            _notify_thread(metadata, "Approve権限がありません。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        calendar = metadata.get("calendar") or {}
        if calendar.get("event_id") or calendar.get("event_link"):
            _notify_thread(metadata, "すでにカレンダー登録済みです。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        if metadata.get("status") == DEMO_STATUS_CALENDAR_CREATING or calendar.get("status") == DEMO_STATUS_CALENDAR_CREATING:
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        metadata["approval_status"] = DEMO_STATUS_APPROVED
        metadata["approved_by"] = actor
        metadata["approved_at"] = datetime.now(timezone.utc).isoformat()
        calendar = dict(calendar)
        calendar.update(
            {
                "status": DEMO_STATUS_CALENDAR_CREATING,
                "started_by": actor,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        metadata["status"] = DEMO_STATUS_CALENDAR_CREATING
        metadata["calendar"] = calendar
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, metadata)
        phase1_metadata = metadata

    if not phase1_metadata:
        return

    try:
        with _demo_db() as conn:
            latest = _load_demo_metadata(conn, alert_id)
            if not latest:
                return
            calendar = latest.get("calendar") or {}
            if calendar.get("event_id") or calendar.get("event_link"):
                return
            if latest.get("status") != DEMO_STATUS_CALENDAR_CREATING and calendar.get("status") != DEMO_STATUS_CALENDAR_CREATING:
                return
            event = _create_demo_calendar_event(conn, latest)
    except Exception as exc:
        reason = str(exc)
        with _demo_db() as conn:
            latest = _load_demo_metadata(conn, alert_id)
            if not latest:
                return
            calendar = dict(latest.get("calendar") or {})
            if calendar.get("event_id") or calendar.get("event_link"):
                return
            latest["status"] = DEMO_STATUS_CALENDAR_FAILED
            calendar.update({"status": DEMO_STATUS_CALENDAR_FAILED, "error": reason})
            latest["calendar"] = calendar
            latest["updated_at"] = datetime.now(timezone.utc).isoformat()
            _upsert_demo_metadata(conn, alert_id, latest)
        _notify_retry(phase1_metadata, reason)
        logger.warning("demo calendar failed alert_id=%s error=%s", alert_id, reason)
        return

    event_link = str(event.get("htmlLink") or "").strip() or None
    event_id = str(event.get("id") or event.get("event_id") or "").strip() or None
    with _demo_db() as conn:
        latest = _load_demo_metadata(conn, alert_id)
        if not latest:
            return
        calendar = dict(latest.get("calendar") or {})
        if calendar.get("event_id") or calendar.get("event_link"):
            return
        latest["status"] = DEMO_STATUS_CALENDAR_CREATED
        calendar.update(
            {
                "status": DEMO_STATUS_CALENDAR_CREATED,
                "event_id": event_id,
                "event_link": event_link,
            }
        )
        latest["calendar"] = calendar
        latest["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, latest)

    message = _build_success_message(phase1_metadata, event_link, event_id)
    _notify_thread(phase1_metadata, message)


def reject_demo(
    *,
    alert_id: str,
    actor: str | None,
    idempotency_key: str | None,
) -> None:
    with _demo_db() as conn:
        metadata = _load_demo_metadata(conn, alert_id)
        if not metadata:
            logger.warning("demo reject ignored (missing alert_id=%s)", alert_id)
            return
        if _idempotency_seen(metadata, idempotency_key):
            return
        _record_idempotency_key(metadata, idempotency_key)

        if metadata.get("status") in {DEMO_STATUS_APPROVED, DEMO_STATUS_CALENDAR_CREATING, DEMO_STATUS_CALENDAR_CREATED}:
            _notify_thread(metadata, "すでにApprove済みです。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        metadata["status"] = DEMO_STATUS_REJECTED
        metadata["approval_status"] = DEMO_STATUS_REJECTED
        metadata["rejected_by"] = actor
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, metadata)
        _notify_thread(metadata, "Rejectされました。")


def cancel_demo(
    *,
    alert_id: str,
    actor: str | None,
    idempotency_key: str | None,
) -> None:
    with _demo_db() as conn:
        metadata = _load_demo_metadata(conn, alert_id)
        if not metadata:
            logger.warning("demo cancel ignored (missing alert_id=%s)", alert_id)
            return
        if _idempotency_seen(metadata, idempotency_key):
            return
        _record_idempotency_key(metadata, idempotency_key)

        if metadata.get("status") in {DEMO_STATUS_APPROVED, DEMO_STATUS_CALENDAR_CREATING, DEMO_STATUS_CALENDAR_CREATED}:
            _notify_thread(metadata, "すでにApprove済みです。")
            _upsert_demo_metadata(conn, alert_id, metadata)
            return

        metadata["status"] = DEMO_STATUS_CANCELLED
        metadata["approval_status"] = DEMO_STATUS_CANCELLED
        metadata["cancelled_by"] = actor
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        _upsert_demo_metadata(conn, alert_id, metadata)
        _notify_thread(metadata, "キャンセルされました。")


def _demo_db():
    from app.db import db_connection

    return db_connection()


def _create_demo_calendar_event(conn: Connection, metadata: dict) -> dict:
    start_at, end_at = _demo_schedule()
    invitees = _resolve_invitee_emails()
    plan = metadata.get("plan")
    intervention = metadata.get("intervention")

    title = "SaihAI デモ（介入アラート）"
    if plan:
        title = f"{title} - Plan {plan}"

    description_parts = [f"Alert ID: {metadata.get('alert_id')}"]
    if plan:
        description_parts.append(f"Plan: {plan}")
    if intervention:
        description_parts.append(f"Intervention: {intervention}")
    description = "\n".join(description_parts)

    payload = {
        "title": title,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "timezone": DEMO_TIMEZONE,
        "attendees": invitees,
        "description": description,
        "calendar_id": DEMO_CALENDAR_ID,
    }

    if CALENDAR_PROVIDER == "mock":
        return {
            "event_id": f"demo-{uuid4().hex[:10]}",
            "status": "confirmed",
            "htmlLink": None,
        }

    token = _resolve_google_oauth_token(
        conn,
        owner_user_id=metadata.get("owner_user_id"),
        owner_email=metadata.get("owner_email"),
    )
    access_token = token.access_token
    expires_at = token.expires_at
    if expires_at and expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
        access_token = _refresh_google_token(conn, token)
    return create_google_calendar_event(access_token, payload)


def _resolve_google_oauth_token(
    conn: Connection,
    *,
    owner_user_id: str | None,
    owner_email: str | None,
):
    token = None
    if owner_user_id:
        token = fetch_google_oauth_token_by_user(conn, owner_user_id)
    if not token and owner_email:
        token = fetch_google_oauth_token_by_email(conn, owner_email)
    if not token and DEFAULT_CALENDAR_OWNER_EMAIL:
        token = fetch_google_oauth_token_by_email(conn, DEFAULT_CALENDAR_OWNER_EMAIL)
    if not token:
        raise RuntimeError("google oauth token not found for demo calendar owner")
    return token


def _refresh_google_token(conn: Connection, token) -> str:
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
    return str(access_token)


def _demo_schedule(now: datetime | None = None) -> tuple[datetime, datetime]:
    tz_name = _resolve_timezone_name(DEMO_TIMEZONE)
    tz = ZoneInfo(tz_name)
    base = now.astimezone(tz) if now else datetime.now(tz)
    target_day = base.date() + timedelta(days=1)
    start_at = datetime(target_day.year, target_day.month, target_day.day, 18, 0, tzinfo=tz)
    end_at = start_at + timedelta(minutes=30)
    return start_at, end_at


def _resolve_timezone_name(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return DEFAULT_CALENDAR_TIMEZONE
    try:
        ZoneInfo(value)
    except Exception:
        return DEFAULT_CALENDAR_TIMEZONE
    return value


def _resolve_invitee_emails() -> list[str]:
    raw = INVITEE_EMAILS_ENV
    if raw:
        tokens = [chunk.strip() for chunk in raw.replace(";", ",").split(",")]
        emails = [token for token in tokens if token]
        if emails:
            return emails
    if DEFAULT_INVITEE_EMAILS:
        return DEFAULT_INVITEE_EMAILS
    if DEFAULT_CALENDAR_ATTENDEE:
        return [DEFAULT_CALENDAR_ATTENDEE]
    return []


def _is_actor_allowed(actor: str | None) -> bool:
    if not APPROVER_USER_IDS_ENV:
        return True
    allowed = {token.strip() for token in APPROVER_USER_IDS_ENV.split(",") if token.strip()}
    if not allowed:
        return True
    return actor in allowed


def _build_demo_summary(metadata: dict) -> str:
    schedule = f"翌日 18:00 - 18:30 ({DEMO_TIMEZONE})"
    invitees = ", ".join(_resolve_invitee_emails())
    plan = metadata.get("plan") or "未選択"
    intervention = metadata.get("intervention") or "なし"
    return (
        "*実行ドラフト*\n"
        f"- Plan: {plan}\n"
        f"- 介入: {intervention}\n"
        f"- 予定: {schedule}\n"
        f"- 招待: {invitees}"
    )


def _build_success_message(metadata: dict, event_link: str | None, event_id: str | None) -> str:
    start_at, end_at = _demo_schedule()
    schedule = f"{start_at.strftime('%Y-%m-%d %H:%M')} - {end_at.strftime('%H:%M')} ({DEMO_TIMEZONE})"
    invitees = ", ".join(_resolve_invitee_emails())
    link_line = f"\nEvent: {event_link}" if event_link else ""
    if not event_link and event_id:
        link_line = f"\nEvent ID: {event_id}"
    return (
        "✅ Approve完了\n"
        f"{schedule}\n"
        f"招待: {invitees}"
        f"{link_line}"
    )


def _post_demo_prompt(metadata: dict, summary: str) -> None:
    slack = metadata.get("slack") or {}
    channel = slack.get("channel")
    thread_ts = slack.get("thread_ts") or slack.get("message_ts")
    if not channel or not thread_ts:
        return
    post_demo_approval_prompt(str(channel), str(thread_ts), summary, metadata.get("alert_id") or "")


def _notify_retry(metadata: dict, reason: str) -> None:
    slack = metadata.get("slack") or {}
    channel = slack.get("channel")
    thread_ts = slack.get("thread_ts") or slack.get("message_ts")
    if not channel or not thread_ts:
        return
    post_demo_retry_prompt(str(channel), str(thread_ts), metadata.get("alert_id") or "", reason)


def _notify_thread(metadata: dict, text: str) -> None:
    slack = metadata.get("slack") or {}
    channel = slack.get("channel")
    thread_ts = slack.get("thread_ts") or slack.get("message_ts")
    if not channel or not thread_ts:
        return
    post_thread_message(str(channel), str(thread_ts), text)


def _demo_thread_id(alert_id: str) -> str:
    return f"demo:{alert_id}"


def _load_demo_metadata(conn: Connection, alert_id: str, *, for_update: bool = False) -> dict:
    suffix = ""
    if for_update:
        try:
            dialect = conn.dialect.name  # type: ignore[attr-defined]
        except Exception:
            dialect = ""
        if str(dialect).startswith("postgres"):
            suffix = " FOR UPDATE"
    query = """
        SELECT metadata
        FROM langgraph_checkpoints
        WHERE thread_id = :thread_id
    """
    if suffix:
        query += suffix
    row = conn.execute(
        text(query),
        {"thread_id": _demo_thread_id(alert_id)},
    ).mappings().first()
    if not row:
        return {}
    metadata = row.get("metadata")
    if isinstance(metadata, (bytes, bytearray, memoryview)):
        metadata = metadata.decode("utf-8")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        return {}
    return metadata


def _upsert_demo_metadata(conn: Connection, alert_id: str, metadata: dict) -> None:
    thread_id = _demo_thread_id(alert_id)
    checkpoint_bytes = json.dumps({"alert_id": alert_id}).encode("utf-8")
    metadata_json = json.dumps(metadata or {})
    exists = conn.execute(
        text("SELECT 1 FROM langgraph_checkpoints WHERE thread_id = :thread_id"),
        {"thread_id": thread_id},
    ).scalar()
    if exists:
        conn.execute(
            text(
                """
                UPDATE langgraph_checkpoints
                SET checkpoint = :checkpoint,
                    metadata = :metadata
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": thread_id, "checkpoint": checkpoint_bytes, "metadata": metadata_json},
        )
        return
    conn.execute(
        text(
            """
            INSERT INTO langgraph_checkpoints (thread_id, checkpoint, metadata)
            VALUES (:thread_id, :checkpoint, :metadata)
            """
        ),
        {"thread_id": thread_id, "checkpoint": checkpoint_bytes, "metadata": metadata_json},
    )


def _idempotency_seen(metadata: dict, key: str | None) -> bool:
    if not key:
        return False
    keys = set(metadata.get("idempotency_keys") or [])
    return key in keys


def _record_idempotency_key(metadata: dict, key: str | None) -> None:
    if not key:
        return
    keys = list(metadata.get("idempotency_keys") or [])
    if key in keys:
        return
    keys.append(key)
    metadata["idempotency_keys"] = keys


def _normalize_plan(plan: str) -> str | None:
    normalized = str(plan or "").strip().upper()
    if normalized in {"A", "B", "C"}:
        return normalized
    return None
