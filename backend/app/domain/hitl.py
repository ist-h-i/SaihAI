from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.external_actions import (
    ACTION_TYPE_CALENDAR,
    CALENDAR_PROVIDER,
    DEFAULT_CALENDAR_ATTENDEE,
    DEFAULT_CALENDAR_OWNER_EMAIL,
    DEFAULT_CALENDAR_TIMEZONE,
    CalendarPayload,
    ExternalActionError,
    _create_calendar_event,
    _extract_payload_from_draft,
    execute_external_action,
)
from app.integrations.slack import SlackMeta, post_thread_message, send_approval_message


@dataclass
class ApprovalResult:
    thread_id: str
    approval_request_id: str
    status: str
    action_id: int
    slack: SlackMeta | None = None


@dataclass
class ExecutionJobResult:
    job_id: str
    status: str
    thread_id: str
    action_id: int


HITL_STATUS_DRAFTED = "drafted"
HITL_STATUS_PENDING = "approval_pending"
HITL_STATUS_APPROVED = "approved"
HITL_STATUS_REJECTED = "rejected"
HITL_STATUS_EXECUTING = "executing"
HITL_STATUS_DONE = "executed"
HITL_STATUS_FAILED = "failed"

logger = logging.getLogger("saihai.hitl")


def _idempotency_seen(metadata: dict[str, Any], key: str | None) -> bool:
    if not key:
        return False
    keys = set(metadata.get("idempotency_keys") or [])
    return key in keys


def _record_idempotency_key(metadata: dict[str, Any], key: str | None) -> None:
    if not key:
        return
    keys = list(metadata.get("idempotency_keys") or [])
    if key in keys:
        return
    keys.append(key)
    metadata["idempotency_keys"] = keys


def _approval_result_from_metadata(
    *,
    thread_id: str,
    action_id: int,
    metadata: dict[str, Any],
) -> ApprovalResult:
    return ApprovalResult(
        thread_id=thread_id,
        approval_request_id=str(metadata.get("approval_request_id") or ""),
        status=str(metadata.get("status") or HITL_STATUS_PENDING),
        action_id=action_id,
        slack=_slack_meta_from_metadata(metadata),
    )


def _execution_result_from_metadata(
    *,
    thread_id: str,
    action_id: int,
    metadata: dict[str, Any],
) -> ExecutionJobResult | None:
    job_id = metadata.get("execution_job_id")
    status = metadata.get("execution_status") or metadata.get("status")
    if status in {HITL_STATUS_EXECUTING, HITL_STATUS_DONE, HITL_STATUS_FAILED}:
        return ExecutionJobResult(
            job_id=str(job_id or f"job-{action_id}"),
            status=str(status),
            thread_id=thread_id,
            action_id=action_id,
        )
    return None


def request_approval(
    conn: Connection,
    action_id: int,
    requested_by: str | None,
    idempotency_key: str | None = None,
    summary: str | None = None,
) -> ApprovalResult:
    action = _load_action(conn, action_id)
    if not action:
        raise ValueError("action not found")

    thread_id = f"action-{action_id}"
    checkpoint, metadata = _load_checkpoint(conn, thread_id)
    metadata = metadata or {}

    if metadata.get("status") == HITL_STATUS_PENDING and metadata.get("approval_request_id"):
        return _approval_result_from_metadata(
            thread_id=thread_id,
            action_id=action_id,
            metadata=metadata,
        )

    if idempotency_key and _idempotency_seen(metadata, idempotency_key):
        approval_request_id = str(metadata.get("approval_request_id") or "")
        if approval_request_id:
            return _approval_result_from_metadata(
                thread_id=thread_id,
                action_id=action_id,
                metadata=metadata,
            )

    approval_request_id = f"apr-{uuid4().hex[:12]}"
    metadata.update(
        {
            "approval_request_id": approval_request_id,
            "status": HITL_STATUS_PENDING,
            "requested_by": requested_by,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _record_idempotency_key(metadata, idempotency_key)

    state = checkpoint or {}
    state.update(
        {
            "thread_id": thread_id,
            "action_id": action_id,
            "proposal_id": action.get("proposal_id"),
            "draft": action.get("draft_content"),
        }
    )

    metadata = _append_audit(
        metadata,
        event_type="approval_requested",
        actor=requested_by,
        correlation_id=approval_request_id,
        detail={"action_id": action_id, "summary": summary},
    )

    slack_existing = _slack_meta_from_metadata(metadata)
    slack_meta = send_approval_message(
        action_id=action_id,
        approval_request_id=approval_request_id,
        thread_id=thread_id,
        summary=summary,
        draft=action.get("draft_content"),
        channel=slack_existing.channel if slack_existing else None,
        thread_ts=slack_existing.thread_ts if slack_existing else None,
    )
    if slack_meta:
        metadata["slack"] = {
            "channel": slack_meta.channel,
            "message_ts": slack_meta.message_ts,
            "thread_ts": slack_meta.thread_ts,
        }

    metadata = _apply_tentative_calendar_hold(conn, action_id, action, metadata)

    _upsert_checkpoint(conn, thread_id, state, metadata)

    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = :status,
                is_approved = FALSE
            WHERE action_id = :action_id
            """
        ),
        {"status": HITL_STATUS_PENDING, "action_id": action_id},
    )

    logger.info(
        "approval requested thread_id=%s action_id=%s approval_request_id=%s",
        thread_id,
        action_id,
        approval_request_id,
    )

    return ApprovalResult(
        thread_id=thread_id,
        approval_request_id=approval_request_id,
        status=HITL_STATUS_PENDING,
        action_id=action_id,
        slack=slack_meta,
    )


def approve_request(
    conn: Connection,
    approval_request_id: str,
    actor: str | None,
    idempotency_key: str | None = None,
) -> ExecutionJobResult:
    thread_id, checkpoint, metadata = _find_by_approval_id(conn, approval_request_id)
    if not thread_id or not metadata:
        raise ValueError("approval request not found")

    action_id = int((checkpoint or {}).get("action_id") or 0)
    if not action_id:
        raise ValueError("action not found")

    existing = _execution_result_from_metadata(
        thread_id=thread_id,
        action_id=action_id,
        metadata=metadata,
    )
    if existing:
        return existing

    action = _load_action(conn, action_id)
    if action and action.get("status") in {HITL_STATUS_EXECUTING, HITL_STATUS_DONE, HITL_STATUS_FAILED}:
        return ExecutionJobResult(
            job_id=str(metadata.get("execution_job_id") or f"job-{action_id}"),
            status=str(action.get("status")),
            thread_id=thread_id,
            action_id=action_id,
        )

    if idempotency_key and _idempotency_seen(metadata, idempotency_key):
        return ExecutionJobResult(
            job_id=str(metadata.get("execution_job_id") or f"job-{action_id}"),
            status=str(metadata.get("execution_status") or metadata.get("status") or HITL_STATUS_APPROVED),
            thread_id=thread_id,
            action_id=action_id,
        )

    _record_idempotency_key(metadata, idempotency_key)

    metadata["status"] = HITL_STATUS_APPROVED
    metadata = _append_audit(
        metadata,
        event_type="approval_approved",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = :status,
                is_approved = TRUE
            WHERE action_id = :action_id
            """
        ),
        {"status": HITL_STATUS_APPROVED, "action_id": action_id},
    )

    logger.info(
        "approval approved thread_id=%s action_id=%s approval_request_id=%s",
        thread_id,
        action_id,
        approval_request_id,
    )

    return process_execution_job(conn, action_id=action_id)


def reject_request(
    conn: Connection,
    approval_request_id: str,
    actor: str | None,
    idempotency_key: str | None = None,
) -> None:
    thread_id, checkpoint, metadata = _find_by_approval_id(conn, approval_request_id)
    if not thread_id or not metadata:
        raise ValueError("approval request not found")

    action_id = int((checkpoint or {}).get("action_id") or 0)
    if idempotency_key and _idempotency_seen(metadata, idempotency_key):
        return
    _record_idempotency_key(metadata, idempotency_key)
    metadata["status"] = HITL_STATUS_REJECTED
    metadata = _append_audit(
        metadata,
        event_type="approval_rejected",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    if action_id:
        conn.execute(
            text(
                """
                UPDATE autonomous_actions
                SET status = :status,
                    is_approved = FALSE
                WHERE action_id = :action_id
                """
            ),
            {"status": HITL_STATUS_REJECTED, "action_id": action_id},
        )

    logger.info(
        "approval rejected thread_id=%s action_id=%s approval_request_id=%s",
        thread_id,
        action_id,
        approval_request_id,
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    if action_id:
        conn.execute(
            text(
                """
                UPDATE autonomous_actions
                SET status = :status,
                    is_approved = FALSE
                WHERE action_id = :action_id
                """
            ),
            {"status": HITL_STATUS_REJECTED, "action_id": action_id},
        )


def apply_steer(
    conn: Connection,
    approval_request_id: str,
    actor: str | None,
    feedback: str,
    selected_plan: str | None = None,
    idempotency_key: str | None = None,
) -> ApprovalResult:
    thread_id, checkpoint, metadata = _find_by_approval_id(conn, approval_request_id)
    if not thread_id or not metadata:
        raise ValueError("approval request not found")

    action_id = int((checkpoint or {}).get("action_id") or 0)
    if not action_id:
        raise ValueError("action not found")

    if idempotency_key and _idempotency_seen(metadata, idempotency_key):
        return _approval_result_from_metadata(
            thread_id=thread_id,
            action_id=action_id,
            metadata=metadata,
        )
    _record_idempotency_key(metadata, idempotency_key)

    action = _load_action(conn, action_id)
    draft = action.get("draft_content") if action else ""
    plan_line = f"\n[Plan] {selected_plan}" if selected_plan else ""
    updated_draft = f"{draft}\n\n[Steer] {feedback}{plan_line}".strip()
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET draft_content = :draft_content,
                status = :status
            WHERE action_id = :action_id
            """
        ),
        {"draft_content": updated_draft, "status": HITL_STATUS_DRAFTED, "action_id": action_id},
    )

    checkpoint = checkpoint or {}
    checkpoint.update({"draft": updated_draft, "feedback": feedback, "selected_plan": selected_plan})
    metadata["status"] = HITL_STATUS_DRAFTED
    metadata = _append_audit(
        metadata,
        event_type="human_feedback_received",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"feedback": feedback, "selected_plan": selected_plan},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    logger.info(
        "steer applied thread_id=%s action_id=%s approval_request_id=%s",
        thread_id,
        action_id,
        approval_request_id,
    )

    return request_approval(
        conn,
        action_id=action_id,
        requested_by=actor,
        idempotency_key=f"{thread_id}:{approval_request_id}:steer",
        summary="steer update",
    )


def process_execution_job(
    conn: Connection,
    action_id: int,
    simulate_failure: bool = False,
    payload_override: dict[str, Any] | None = None,
) -> ExecutionJobResult:
    thread_id = f"action-{action_id}"
    checkpoint, metadata = _load_checkpoint(conn, thread_id)
    metadata = metadata or {}

    existing = _execution_result_from_metadata(
        thread_id=thread_id,
        action_id=action_id,
        metadata=metadata,
    )
    if existing:
        return existing

    action = _load_action(conn, action_id)
    if action and action.get("status") in {HITL_STATUS_EXECUTING, HITL_STATUS_DONE, HITL_STATUS_FAILED}:
        status = str(action.get("status") or HITL_STATUS_EXECUTING)
        return ExecutionJobResult(
            job_id=str(metadata.get("execution_job_id") or f"job-{action_id}"),
            status=status,
            thread_id=thread_id,
            action_id=action_id,
        )

    job_id = f"job-{uuid4().hex[:12]}"
    metadata["status"] = HITL_STATUS_EXECUTING
    metadata["execution_job_id"] = job_id
    metadata["execution_status"] = HITL_STATUS_EXECUTING
    metadata = _append_audit(
        metadata,
        event_type="execution_started",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = :status
            WHERE action_id = :action_id
            """
        ),
        {"status": HITL_STATUS_EXECUTING, "action_id": action_id},
    )

    if simulate_failure:
        return _mark_failed(conn, thread_id, checkpoint, metadata, job_id, action_id, "simulated failure")

    try:
        execute_external_action(conn, job_id=job_id, action_id=action_id, payload_override=payload_override)
    except (ExternalActionError, ValueError) as exc:
        return _mark_failed(conn, thread_id, checkpoint, metadata, job_id, action_id, str(exc))

    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = :status
            WHERE action_id = :action_id
            """
        ),
        {"status": HITL_STATUS_DONE, "action_id": action_id},
    )

    metadata["status"] = HITL_STATUS_DONE
    metadata["execution_status"] = HITL_STATUS_DONE
    metadata = _append_audit(
        metadata,
        event_type="execution_succeeded",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    _notify_execution_result(metadata, thread_id, action_id, job_id, HITL_STATUS_DONE, None)

    logger.info("execution succeeded thread_id=%s action_id=%s job_id=%s", thread_id, action_id, job_id)

    return ExecutionJobResult(job_id=job_id, status=HITL_STATUS_DONE, thread_id=thread_id, action_id=action_id)


def fetch_audit_logs(conn: Connection, thread_id: str) -> list[dict[str, Any]]:
    _, _, metadata = _load_checkpoint(conn, thread_id)
    return list(metadata.get("audit_events") or []) if metadata else []


def fetch_history(
    conn: Connection,
    *,
    status: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        text("SELECT thread_id, checkpoint, metadata FROM langgraph_checkpoints")
    ).mappings().all()
    results: list[dict[str, Any]] = []
    for row in rows:
        metadata = _deserialize_json(row.get("metadata"))
        if not isinstance(metadata, dict):
            continue
        if project_id and str(metadata.get("project_id") or "") != project_id:
            continue
        current_status = str(metadata.get("status") or "")
        if status and current_status != status:
            continue

        checkpoint = _deserialize_blob(row.get("checkpoint")) or {}
        action_id = int(checkpoint.get("action_id") or 0)
        action = _load_action(conn, action_id) if action_id else None
        draft_summary = (action or {}).get("draft_content") or ""
        if len(draft_summary) > 160:
            draft_summary = draft_summary[:160] + "..."

        events = list(metadata.get("audit_events") or [])
        updated_at = ""
        if events:
            updated_at = str(events[-1].get("created_at") or "")
        else:
            updated_at = str(metadata.get("requested_at") or "")

        results.append(
            {
                "thread_id": row.get("thread_id"),
                "action_id": action_id,
                "status": current_status or (action or {}).get("status"),
                "summary": draft_summary,
                "project_id": metadata.get("project_id"),
                "severity": metadata.get("severity"),
                "updated_at": updated_at,
                "events": events,
            }
        )

    results.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return results[:limit]


def _load_action(conn: Connection, action_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT action_id, proposal_id, action_type, draft_content, status
            FROM autonomous_actions
            WHERE action_id = :action_id
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    return dict(row) if row else None


def _load_checkpoint(conn: Connection, thread_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    row = conn.execute(
        text(
            """
            SELECT checkpoint, metadata
            FROM langgraph_checkpoints
            WHERE thread_id = :thread_id
            """
        ),
        {"thread_id": thread_id},
    ).mappings().first()
    if not row:
        return None, None
    checkpoint = _deserialize_blob(row.get("checkpoint"))
    metadata = _deserialize_json(row.get("metadata"))
    return checkpoint, metadata


def _find_by_approval_id(
    conn: Connection, approval_request_id: str
) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    rows = conn.execute(
        text("SELECT thread_id, checkpoint, metadata FROM langgraph_checkpoints")
    ).mappings().all()
    for row in rows:
        metadata = _deserialize_json(row.get("metadata"))
        if not isinstance(metadata, dict):
            continue
        if metadata.get("approval_request_id") == approval_request_id:
            return row["thread_id"], _deserialize_blob(row.get("checkpoint")), metadata
    return None, None, None


def _upsert_checkpoint(
    conn: Connection,
    thread_id: str,
    checkpoint: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> None:
    checkpoint_bytes = json.dumps(checkpoint or {}).encode("utf-8")
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


def _append_audit(
    metadata: dict[str, Any],
    event_type: str,
    actor: str | None,
    correlation_id: str | None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = list(metadata.get("audit_events") or [])
    events.append(
        {
            "event_type": event_type,
            "actor": actor,
            "correlation_id": correlation_id,
            "detail": detail or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    metadata["audit_events"] = events
    return metadata


def _deserialize_json(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
    return {}


def _deserialize_blob(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return json.loads(bytes(value).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(value, dict):
        return value
    return None


def _mark_failed(
    conn: Connection,
    thread_id: str,
    checkpoint: dict[str, Any] | None,
    metadata: dict[str, Any],
    job_id: str,
    action_id: int,
    error_message: str,
) -> ExecutionJobResult:
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = :status
            WHERE action_id = :action_id
            """
        ),
        {"status": HITL_STATUS_FAILED, "action_id": action_id},
    )

    metadata["status"] = HITL_STATUS_FAILED
    metadata["execution_status"] = HITL_STATUS_FAILED
    metadata = _append_audit(
        metadata,
        event_type="execution_failed",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id, "error": error_message},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)
    _notify_execution_result(metadata, thread_id, action_id, job_id, HITL_STATUS_FAILED, error_message)
    logger.warning(
        "execution failed thread_id=%s action_id=%s job_id=%s error=%s",
        thread_id,
        action_id,
        job_id,
        error_message,
    )
    return ExecutionJobResult(job_id=job_id, status=HITL_STATUS_FAILED, thread_id=thread_id, action_id=action_id)


def _slack_meta_from_metadata(metadata: dict[str, Any]) -> SlackMeta | None:
    slack = metadata.get("slack") or {}
    channel = slack.get("channel")
    message_ts = slack.get("message_ts")
    if not channel or not message_ts:
        return None
    return SlackMeta(
        channel=str(channel),
        message_ts=str(message_ts),
        thread_ts=slack.get("thread_ts"),
    )


def _notify_execution_result(
    metadata: dict[str, Any],
    thread_id: str,
    action_id: int,
    job_id: str,
    status: str,
    error_message: str | None,
) -> None:
    slack = _slack_meta_from_metadata(metadata)
    if not slack:
        return
    thread_ts = slack.thread_ts or slack.message_ts
    if status == HITL_STATUS_DONE:
        text = f"Execution completed. job_id={job_id} action_id={action_id}"
    else:
        text = f"Execution failed. job_id={job_id} action_id={action_id} error={error_message}"
    post_thread_message(channel=slack.channel, thread_ts=thread_ts, text=text)


def _resolve_timezone_name(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return DEFAULT_CALENDAR_TIMEZONE
    try:
        ZoneInfo(value)
    except Exception:
        return DEFAULT_CALENDAR_TIMEZONE
    return value


def _build_tentative_calendar_payload(
    action_id: int,
    draft_content: str | None,
) -> tuple[CalendarPayload, dict[str, Any]]:
    payload = _extract_payload_from_draft(draft_content)
    timezone_name = _resolve_timezone_name(payload.get("timezone"))
    tz = ZoneInfo(timezone_name)
    next_day = (datetime.now(tz).date() + timedelta(days=1))
    start_dt = datetime(
        next_day.year,
        next_day.month,
        next_day.day,
        18,
        0,
        tzinfo=tz,
    )
    end_dt = start_dt + timedelta(hours=1)

    title = str(payload.get("title") or f"Approval hold {action_id}")
    if "tentative" not in title.lower():
        title = f"Tentative: {title}"

    description = str(payload.get("description") or "").strip()
    note = "Tentative hold created at approval request."
    if note not in description:
        description = f"{description}\n\n{note}".strip()

    meeting_url = payload.get("meeting_url") or payload.get("meetingUrl")
    owner_email = payload.get("owner_email") or payload.get("ownerEmail") or DEFAULT_CALENDAR_OWNER_EMAIL
    owner_user_id = payload.get("owner_user_id") or payload.get("ownerUserId")
    attendee = payload.get("attendee") or DEFAULT_CALENDAR_ATTENDEE

    calendar_payload = CalendarPayload(
        attendee=str(attendee),
        title=title,
        start_at=start_dt.isoformat(),
        end_at=end_dt.isoformat(),
        timezone=timezone_name,
        description=description or None,
        meeting_url=str(meeting_url).strip() if meeting_url else None,
        owner_email=str(owner_email).strip() if owner_email else None,
        owner_user_id=str(owner_user_id).strip() if owner_user_id else None,
    )
    hold_meta = {
        "start_at": calendar_payload.start_at,
        "end_at": calendar_payload.end_at,
        "timezone": calendar_payload.timezone,
        "title": calendar_payload.title,
        "attendee": calendar_payload.attendee,
    }
    return calendar_payload, hold_meta


def _apply_tentative_calendar_hold(
    conn: Connection,
    action_id: int,
    action: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if action.get("action_type") != ACTION_TYPE_CALENDAR:
        return metadata

    existing = metadata.get("tentative_calendar")
    if isinstance(existing, dict) and existing.get("status") == "created":
        return metadata

    calendar_payload, hold_meta = _build_tentative_calendar_payload(
        action_id=action_id,
        draft_content=action.get("draft_content"),
    )
    hold_meta.update(
        {
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": CALENDAR_PROVIDER,
        }
    )

    try:
        response = _create_calendar_event(conn, calendar_payload)
    except Exception as exc:
        hold_meta.update({"status": "failed", "error": str(exc)})
        metadata["tentative_calendar"] = hold_meta
        logger.warning(
            "tentative calendar hold failed thread_id=%s action_id=%s error=%s",
            f"action-{action_id}",
            action_id,
            exc,
        )
        return metadata

    if isinstance(response, dict):
        event_id = response.get("id") or response.get("event_id")
        if event_id:
            hold_meta["event_id"] = str(event_id)
        if response.get("htmlLink"):
            hold_meta["html_link"] = response.get("htmlLink")

    hold_meta["status"] = "created"
    metadata["tentative_calendar"] = hold_meta
    return metadata
