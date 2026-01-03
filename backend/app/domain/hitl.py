from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

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
HITL_STATUS_DONE = "done"
HITL_STATUS_FAILED = "failed"


def _serialize_json(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _deserialize_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _load_state(conn: Connection, thread_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT thread_id, status, approval_request_id, action_id, state_payload,
                   slack_channel, slack_message_ts, slack_thread_ts, version, updated_at
            FROM hitl_states
            WHERE thread_id = :thread_id
            """
        ),
        {"thread_id": thread_id},
    ).mappings().first()
    if not row:
        return None
    payload = dict(row)
    payload["state_payload"] = _deserialize_json(payload.get("state_payload"))
    return payload


def _load_state_by_action(conn: Connection, action_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT thread_id, status, approval_request_id, action_id, state_payload,
                   slack_channel, slack_message_ts, slack_thread_ts, version, updated_at
            FROM hitl_states
            WHERE action_id = :action_id
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    if not row:
        return None
    payload = dict(row)
    payload["state_payload"] = _deserialize_json(payload.get("state_payload"))
    return payload


def _insert_state(
    conn: Connection,
    thread_id: str,
    status: str,
    action_id: int,
    state_payload: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hitl_states
              (thread_id, status, approval_request_id, action_id, state_payload, version)
            VALUES
              (:thread_id, :status, NULL, :action_id, :state_payload, 0)
            """
        ),
        {
            "thread_id": thread_id,
            "status": status,
            "action_id": action_id,
            "state_payload": _serialize_json(state_payload),
        },
    )


def _update_state(
    conn: Connection,
    thread_id: str,
    status: str | None = None,
    approval_request_id: str | None = None,
    state_payload: dict[str, Any] | None = None,
    slack_meta: SlackMeta | None = None,
    expected_status: str | None = None,
    expected_approval_request_id: str | None = None,
) -> bool:
    sets: list[str] = []
    params: dict[str, Any] = {"thread_id": thread_id}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if approval_request_id is not None:
        sets.append("approval_request_id = :approval_request_id")
        params["approval_request_id"] = approval_request_id
    if state_payload is not None:
        sets.append("state_payload = :state_payload")
        params["state_payload"] = _serialize_json(state_payload)
    if slack_meta is not None:
        sets.append("slack_channel = :slack_channel")
        sets.append("slack_message_ts = :slack_message_ts")
        sets.append("slack_thread_ts = :slack_thread_ts")
        params["slack_channel"] = slack_meta.channel
        params["slack_message_ts"] = slack_meta.message_ts
        params["slack_thread_ts"] = slack_meta.thread_ts

    sets.append("updated_at = CURRENT_TIMESTAMP")
    sets.append("version = version + 1")

    where = ["thread_id = :thread_id"]
    if expected_status is not None:
        where.append("status = :expected_status")
        params["expected_status"] = expected_status
    if expected_approval_request_id is not None:
        where.append("approval_request_id = :expected_approval_request_id")
        params["expected_approval_request_id"] = expected_approval_request_id

    stmt = f"UPDATE hitl_states SET {', '.join(sets)} WHERE {' AND '.join(where)}"
    result = conn.execute(text(stmt), params)
    return bool(result.rowcount)


def _load_approval_request(conn: Connection, approval_request_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT approval_request_id, thread_id, action_id, status, idempotency_key,
                   requested_by, requested_at, expires_at, slack_channel, slack_message_ts, slack_thread_ts
            FROM hitl_approval_requests
            WHERE approval_request_id = :approval_request_id
            """
        ),
        {"approval_request_id": approval_request_id},
    ).mappings().first()
    return dict(row) if row else None


def _load_approval_by_idempotency(conn: Connection, idempotency_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT approval_request_id, thread_id, action_id, status, idempotency_key,
                   requested_by, requested_at, expires_at, slack_channel, slack_message_ts, slack_thread_ts
            FROM hitl_approval_requests
            WHERE idempotency_key = :idempotency_key
            """
        ),
        {"idempotency_key": idempotency_key},
    ).mappings().first()
    return dict(row) if row else None


def _insert_approval_request(
    conn: Connection,
    approval_request_id: str,
    thread_id: str,
    action_id: int,
    status: str,
    idempotency_key: str,
    requested_by: str | None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hitl_approval_requests
              (approval_request_id, thread_id, action_id, status, idempotency_key, requested_by)
            VALUES
              (:approval_request_id, :thread_id, :action_id, :status, :idempotency_key, :requested_by)
            """
        ),
        {
            "approval_request_id": approval_request_id,
            "thread_id": thread_id,
            "action_id": action_id,
            "status": status,
            "idempotency_key": idempotency_key,
            "requested_by": requested_by,
        },
    )


def _update_approval_request_status(conn: Connection, approval_request_id: str, status: str) -> None:
    conn.execute(
        text(
            """
            UPDATE hitl_approval_requests
            SET status = :status
            WHERE approval_request_id = :approval_request_id
            """
        ),
        {"status": status, "approval_request_id": approval_request_id},
    )


def _update_approval_request_slack(
    conn: Connection,
    approval_request_id: str,
    slack_meta: SlackMeta,
) -> None:
    conn.execute(
        text(
            """
            UPDATE hitl_approval_requests
            SET slack_channel = :slack_channel,
                slack_message_ts = :slack_message_ts,
                slack_thread_ts = :slack_thread_ts
            WHERE approval_request_id = :approval_request_id
            """
        ),
        {
            "slack_channel": slack_meta.channel,
            "slack_message_ts": slack_meta.message_ts,
            "slack_thread_ts": slack_meta.thread_ts,
            "approval_request_id": approval_request_id,
        },
    )


def _record_audit(
    conn: Connection,
    thread_id: str,
    event_type: str,
    actor: str | None,
    correlation_id: str | None,
    detail: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO hitl_audit_logs
              (audit_id, thread_id, event_type, actor, correlation_id, detail)
            VALUES
              (:audit_id, :thread_id, :event_type, :actor, :correlation_id, :detail)
            """
        ),
        {
            "audit_id": f"audit-{uuid4().hex}",
            "thread_id": thread_id,
            "event_type": event_type,
            "actor": actor,
            "correlation_id": correlation_id,
            "detail": _serialize_json(detail) if detail else None,
        },
    )


def request_approval(
    conn: Connection,
    action_id: int,
    requested_by: str | None,
    idempotency_key: str | None = None,
    summary: str | None = None,
) -> ApprovalResult:
    action = conn.execute(
        text(
            """
            SELECT action_id, proposal_id, action_type, draft_content, status
            FROM autonomous_actions
            WHERE action_id = :action_id
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    if not action:
        raise ValueError("action not found")

    state = _load_state_by_action(conn, action_id)
    if not state:
        thread_id = f"action-{action_id}"
        state_payload = {
            "draft": action.get("draft_content"),
            "action_id": action_id,
            "proposal_id": action.get("proposal_id"),
            "feedback": None,
            "selected_plan": None,
        }
        _insert_state(conn, thread_id, HITL_STATUS_DRAFTED, action_id, state_payload)
        state = _load_state(conn, thread_id)
    else:
        thread_id = state["thread_id"]
        if state.get("status") == HITL_STATUS_PENDING and state.get("approval_request_id"):
            existing = _load_approval_request(conn, state["approval_request_id"])
            if existing:
                return ApprovalResult(
                    thread_id=thread_id,
                    approval_request_id=existing["approval_request_id"],
                    status=existing["status"],
                    action_id=action_id,
                    slack=_slack_meta_from_row(existing),
                )

    key = idempotency_key or f"{thread_id}:{action_id}:request"
    existing = _load_approval_by_idempotency(conn, key)
    if existing:
        return ApprovalResult(
            thread_id=existing["thread_id"],
            approval_request_id=existing["approval_request_id"],
            status=existing["status"],
            action_id=existing["action_id"],
            slack=_slack_meta_from_row(existing),
        )

    approval_request_id = f"apr-{uuid4().hex[:12]}"
    _insert_approval_request(
        conn,
        approval_request_id=approval_request_id,
        thread_id=thread_id,
        action_id=action_id,
        status=HITL_STATUS_PENDING,
        idempotency_key=key,
        requested_by=requested_by,
    )

    payload = state.get("state_payload") if state else None
    updated = _update_state(
        conn,
        thread_id=thread_id,
        status=HITL_STATUS_PENDING,
        approval_request_id=approval_request_id,
        state_payload=payload,
    )
    if not updated:
        raise RuntimeError("state update failed")

    if action.get("status") in ("pending", "drafted", "approval_pending"):
        conn.execute(
            text(
                """
                UPDATE autonomous_actions
                SET status = 'approval_pending'
                WHERE action_id = :action_id
                """
            ),
            {"action_id": action_id},
        )

    _record_audit(
        conn,
        thread_id=thread_id,
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
        _update_state(conn, thread_id=thread_id, slack_meta=slack_meta)
        _update_approval_request_slack(conn, approval_request_id, slack_meta)

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
    request_row = _load_approval_request(conn, approval_request_id)
    if not request_row:
        raise ValueError("approval request not found")

    state = _load_state(conn, request_row["thread_id"])
    if not state:
        raise ValueError("state not found")

    if state.get("status") in (HITL_STATUS_APPROVED, HITL_STATUS_EXECUTING, HITL_STATUS_DONE):
        job = _load_execution_job_by_key(conn, f"{approval_request_id}:execute")
        if job:
            return ExecutionJobResult(
                job_id=job["job_id"],
                status=job["status"],
                thread_id=job["thread_id"],
                action_id=job["action_id"],
            )
        if state.get("status") == HITL_STATUS_APPROVED:
            return enqueue_execution_job(
                conn,
                thread_id=state["thread_id"],
                action_id=request_row["action_id"],
                approval_request_id=approval_request_id,
                actor=actor,
            )
        raise RuntimeError("approval already processed")

    updated = _update_state(
        conn,
        thread_id=state["thread_id"],
        status=HITL_STATUS_APPROVED,
        expected_status=HITL_STATUS_PENDING,
        expected_approval_request_id=approval_request_id,
    )
    if not updated:
        raise RuntimeError("state transition rejected")

    _update_approval_request_status(conn, approval_request_id, HITL_STATUS_APPROVED)
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET is_approved = TRUE,
                approved_at = CURRENT_TIMESTAMP,
                status = 'approved'
            WHERE action_id = :action_id
            """
        ),
        {"action_id": request_row["action_id"]},
    )

    _record_audit(
        conn,
        thread_id=state["thread_id"],
        event_type="approval_approved",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"action_id": request_row["action_id"]},
    )

    job = enqueue_execution_job(
        conn,
        thread_id=state["thread_id"],
        action_id=request_row["action_id"],
        approval_request_id=approval_request_id,
        actor=actor,
    )
    return job


def reject_request(conn: Connection, approval_request_id: str, actor: str | None) -> None:
    request_row = _load_approval_request(conn, approval_request_id)
    if not request_row:
        raise ValueError("approval request not found")

    state = _load_state(conn, request_row["thread_id"])
    if not state:
        raise ValueError("state not found")

    updated = _update_state(
        conn,
        thread_id=state["thread_id"],
        status=HITL_STATUS_REJECTED,
        expected_status=HITL_STATUS_PENDING,
        expected_approval_request_id=approval_request_id,
    )
    if not updated:
        raise RuntimeError("state transition rejected")

    _update_approval_request_status(conn, approval_request_id, HITL_STATUS_REJECTED)
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = 'rejected'
            WHERE action_id = :action_id
            """
        ),
        {"action_id": request_row["action_id"]},
    )

    _record_audit(
        conn,
        thread_id=state["thread_id"],
        event_type="approval_rejected",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"action_id": request_row["action_id"]},
    )


def apply_steer(
    conn: Connection,
    approval_request_id: str,
    actor: str | None,
    feedback: str,
    selected_plan: str | None = None,
    idempotency_key: str | None = None,
) -> ApprovalResult:
    if idempotency_key:
        existing = _load_approval_by_idempotency(conn, idempotency_key)
        if existing:
            return ApprovalResult(
                thread_id=existing["thread_id"],
                approval_request_id=existing["approval_request_id"],
                status=existing["status"],
                action_id=existing["action_id"],
                slack=_slack_meta_from_row(existing),
            )
    request_row = _load_approval_request(conn, approval_request_id)
    if not request_row:
        raise ValueError("approval request not found")

    state = _load_state(conn, request_row["thread_id"])
    if not state:
        raise ValueError("state not found")

    if state.get("status") != HITL_STATUS_PENDING:
        raise RuntimeError("state not pending")

    action_id = request_row["action_id"]
    action = conn.execute(
        text(
            """
            SELECT action_id, draft_content
            FROM autonomous_actions
            WHERE action_id = :action_id
            """
        ),
        {"action_id": action_id},
    ).mappings().first()

    draft = action.get("draft_content") if action else ""
    plan_line = f"\n[Plan] {selected_plan}" if selected_plan else ""
    updated_draft = f"{draft}\n\n[Steer] {feedback}{plan_line}".strip()
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET draft_content = :draft_content,
                status = 'pending'
            WHERE action_id = :action_id
            """
        ),
        {"draft_content": updated_draft, "action_id": action_id},
    )

    payload = state.get("state_payload") or {}
    payload.update({"feedback": feedback, "selected_plan": selected_plan, "draft": updated_draft})

    updated = _update_state(
        conn,
        thread_id=state["thread_id"],
        status=HITL_STATUS_DRAFTED,
        state_payload=payload,
        expected_status=HITL_STATUS_PENDING,
        expected_approval_request_id=approval_request_id,
    )
    if not updated:
        raise RuntimeError("state update failed")

    _record_audit(
        conn,
        thread_id=state["thread_id"],
        event_type="human_feedback_received",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"feedback": feedback, "selected_plan": selected_plan},
    )
    _record_audit(
        conn,
        thread_id=state["thread_id"],
        event_type="state_updated",
        actor=actor,
        correlation_id=approval_request_id,
        detail={"draft": updated_draft},
    )

    return request_approval(
        conn,
        action_id=action_id,
        requested_by=actor,
        idempotency_key=idempotency_key or f"{state['thread_id']}:{approval_request_id}:steer",
        summary="steer update",
    )


def enqueue_execution_job(
    conn: Connection,
    thread_id: str,
    action_id: int,
    approval_request_id: str,
    actor: str | None,
) -> ExecutionJobResult:
    key = f"{approval_request_id}:execute"
    existing = _load_execution_job_by_key(conn, key)
    if existing:
        return ExecutionJobResult(
            job_id=existing["job_id"],
            status=existing["status"],
            thread_id=existing["thread_id"],
            action_id=existing["action_id"],
        )

    job_id = f"job-{uuid4().hex[:12]}"
    conn.execute(
        text(
            """
            INSERT INTO execution_jobs
              (job_id, thread_id, action_id, status, idempotency_key)
            VALUES
              (:job_id, :thread_id, :action_id, :status, :idempotency_key)
            """
        ),
        {
            "job_id": job_id,
            "thread_id": thread_id,
            "action_id": action_id,
            "status": "queued",
            "idempotency_key": key,
        },
    )

    _record_audit(
        conn,
        thread_id=thread_id,
        event_type="execution_queued",
        actor=actor,
        correlation_id=job_id,
        detail={"action_id": action_id},
    )

    return ExecutionJobResult(job_id=job_id, status="queued", thread_id=thread_id, action_id=action_id)


def process_execution_job(
    conn: Connection,
    action_id: int,
    simulate_failure: bool = False,
) -> ExecutionJobResult:
    job = conn.execute(
        text(
            """
            SELECT job_id, thread_id, action_id, status, idempotency_key
            FROM execution_jobs
            WHERE action_id = :action_id AND status = 'queued'
            ORDER BY enqueued_at
            LIMIT 1
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    if not job:
        raise ValueError("no queued job")

    conn.execute(
        text(
            """
            UPDATE execution_jobs
            SET status = 'running',
                started_at = CURRENT_TIMESTAMP,
                attempts = attempts + 1
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job["job_id"]},
    )

    _update_state(
        conn,
        thread_id=job["thread_id"],
        status=HITL_STATUS_EXECUTING,
    )
    _record_audit(
        conn,
        thread_id=job["thread_id"],
        event_type="execution_started",
        actor="worker",
        correlation_id=job["job_id"],
        detail={"action_id": action_id},
    )

    if simulate_failure:
        conn.execute(
            text(
                """
                UPDATE execution_jobs
                SET status = 'failed',
                    finished_at = CURRENT_TIMESTAMP,
                    last_error = 'simulated failure'
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job["job_id"]},
        )
        conn.execute(
            text(
                """
                UPDATE autonomous_actions
                SET status = 'failed'
                WHERE action_id = :action_id
                """
            ),
            {"action_id": action_id},
        )
        _update_state(conn, thread_id=job["thread_id"], status=HITL_STATUS_FAILED)
        _record_audit(
            conn,
            thread_id=job["thread_id"],
            event_type="execution_failed",
            actor="worker",
            correlation_id=job["job_id"],
            detail={"action_id": action_id},
        )
        return ExecutionJobResult(
            job_id=job["job_id"],
            status="failed",
            thread_id=job["thread_id"],
            action_id=action_id,
        )

    conn.execute(
        text(
            """
            UPDATE execution_jobs
            SET status = 'succeeded',
                finished_at = CURRENT_TIMESTAMP
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job["job_id"]},
    )
    conn.execute(
        text(
            """
            UPDATE autonomous_actions
            SET status = 'executed'
            WHERE action_id = :action_id
            """
        ),
        {"action_id": action_id},
    )
    _update_state(conn, thread_id=job["thread_id"], status=HITL_STATUS_DONE)
    _record_audit(
        conn,
        thread_id=job["thread_id"],
        event_type="execution_succeeded",
        actor="worker",
        correlation_id=job["job_id"],
        detail={"action_id": action_id},
    )
    return ExecutionJobResult(
        job_id=job["job_id"],
        status="succeeded",
        thread_id=job["thread_id"],
        action_id=action_id,
    )


def fetch_audit_logs(conn: Connection, thread_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT audit_id, thread_id, event_type, actor, correlation_id, detail, created_at
            FROM hitl_audit_logs
            WHERE thread_id = :thread_id
            ORDER BY created_at
            """
        ),
        {"thread_id": thread_id},
    ).mappings().all()

    results: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["detail"] = _deserialize_json(payload.get("detail"))
        results.append(payload)
    return results


def _load_execution_job_by_key(conn: Connection, key: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT job_id, thread_id, action_id, status, idempotency_key
            FROM execution_jobs
            WHERE idempotency_key = :idempotency_key
            """
        ),
        {"idempotency_key": key},
    ).mappings().first()
    return dict(row) if row else None


def _slack_meta_from_row(row: dict[str, Any]) -> SlackMeta | None:
    if not row.get("slack_channel") or not row.get("slack_message_ts"):
        return None
    return SlackMeta(
        channel=row["slack_channel"],
        message_ts=row["slack_message_ts"],
        thread_ts=row.get("slack_thread_ts"),
    )
