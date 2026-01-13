from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.external_actions import ExternalActionError, execute_external_action
from app.integrations.slack import SlackMeta, send_approval_message


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
        return ApprovalResult(
            thread_id=thread_id,
            approval_request_id=metadata["approval_request_id"],
            status=metadata.get("status", HITL_STATUS_PENDING),
            action_id=action_id,
            slack=_slack_meta_from_metadata(metadata),
        )

    if idempotency_key and idempotency_key in set(metadata.get("idempotency_keys") or []):
        approval_request_id = str(metadata.get("approval_request_id") or "")
        if approval_request_id:
            return ApprovalResult(
                thread_id=thread_id,
                approval_request_id=approval_request_id,
                status=metadata.get("status", HITL_STATUS_PENDING),
                action_id=action_id,
                slack=_slack_meta_from_metadata(metadata),
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
    if idempotency_key:
        keys = list(metadata.get("idempotency_keys") or [])
        keys.append(idempotency_key)
        metadata["idempotency_keys"] = keys

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

    slack_meta = send_approval_message(
        action_id=action_id,
        approval_request_id=approval_request_id,
        thread_id=thread_id,
        summary=summary,
        draft=action.get("draft_content"),
    )
    if slack_meta:
        metadata["slack"] = {
            "channel": slack_meta.channel,
            "message_ts": slack_meta.message_ts,
            "thread_ts": slack_meta.thread_ts,
        }

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
) -> ExecutionJobResult:
    thread_id, checkpoint, metadata = _find_by_approval_id(conn, approval_request_id)
    if not thread_id or not metadata:
        raise ValueError("approval request not found")

    action_id = int((checkpoint or {}).get("action_id") or 0)
    if not action_id:
        raise ValueError("action not found")

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

    return process_execution_job(conn, action_id=action_id)


def reject_request(conn: Connection, approval_request_id: str, actor: str | None) -> None:
    thread_id, checkpoint, metadata = _find_by_approval_id(conn, approval_request_id)
    if not thread_id or not metadata:
        raise ValueError("approval request not found")

    action_id = int((checkpoint or {}).get("action_id") or 0)
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

    return request_approval(
        conn,
        action_id=action_id,
        requested_by=actor,
        idempotency_key=idempotency_key or f"{thread_id}:{approval_request_id}:steer",
        summary="steer update",
    )


def process_execution_job(
    conn: Connection,
    action_id: int,
    simulate_failure: bool = False,
) -> ExecutionJobResult:
    thread_id = f"action-{action_id}"
    checkpoint, metadata = _load_checkpoint(conn, thread_id)
    metadata = metadata or {}

    job_id = f"job-{uuid4().hex[:12]}"
    metadata["status"] = HITL_STATUS_EXECUTING
    metadata = _append_audit(
        metadata,
        event_type="execution_started",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    if simulate_failure:
        return _mark_failed(conn, thread_id, checkpoint, metadata, job_id, action_id, "simulated failure")

    try:
        execute_external_action(conn, job_id=job_id, action_id=action_id)
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
    metadata = _append_audit(
        metadata,
        event_type="execution_succeeded",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)

    return ExecutionJobResult(job_id=job_id, status=HITL_STATUS_DONE, thread_id=thread_id, action_id=action_id)


def fetch_audit_logs(conn: Connection, thread_id: str) -> list[dict[str, Any]]:
    _, _, metadata = _load_checkpoint(conn, thread_id)
    return list(metadata.get("audit_events") or []) if metadata else []


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
    metadata = _append_audit(
        metadata,
        event_type="execution_failed",
        actor="worker",
        correlation_id=job_id,
        detail={"action_id": action_id, "error": error_message},
    )
    _upsert_checkpoint(conn, thread_id, checkpoint, metadata)
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
