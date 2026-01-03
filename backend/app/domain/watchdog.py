from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.embeddings import ensure_weekly_report_embeddings
from app.domain.hitl import request_approval


def enqueue_watchdog_job(conn: Connection, payload: dict | None = None) -> dict[str, str]:
    job_id = f"wdjob-{uuid4().hex[:12]}"
    conn.execute(
        text(
            """
            INSERT INTO watchdog_jobs (job_id, status, payload)
            VALUES (:job_id, 'queued', :payload)
            """
        ),
        {"job_id": job_id, "payload": json.dumps(payload or {})},
    )
    return {"job_id": job_id, "status": "queued"}


def run_watchdog_job(conn: Connection, job_id: str | None = None) -> dict[str, str]:
    job = _load_job(conn, job_id)
    if not job:
        raise ValueError("no queued job")

    conn.execute(
        text(
            """
            UPDATE watchdog_jobs
            SET status = 'running',
                started_at = CURRENT_TIMESTAMP,
                attempts = attempts + 1
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job["job_id"]},
    )

    try:
        summary, severity, action_id, thread_id = _perform_watchdog_cycle(conn)
        _insert_watchdog_alert(conn, summary, severity, thread_id, action_id)
        conn.execute(
            text(
                """
                UPDATE watchdog_jobs
                SET status = 'succeeded',
                    finished_at = CURRENT_TIMESTAMP
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job["job_id"]},
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        conn.execute(
            text(
                """
                UPDATE watchdog_jobs
                SET status = 'failed',
                    finished_at = CURRENT_TIMESTAMP,
                    last_error = :error
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job["job_id"], "error": str(exc)},
        )
        raise

    return {"job_id": job["job_id"], "status": "succeeded"}


def _load_job(conn: Connection, job_id: str | None) -> dict | None:
    if job_id:
        return conn.execute(
            text(
                """
                SELECT job_id, status, payload
                FROM watchdog_jobs
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id},
        ).mappings().first()

    return conn.execute(
        text(
            """
            SELECT job_id, status, payload
            FROM watchdog_jobs
            WHERE status = 'queued'
            ORDER BY enqueued_at
            LIMIT 1
            """
        )
    ).mappings().first()


def _perform_watchdog_cycle(conn: Connection) -> tuple[str, str, int, str]:
    ensure_weekly_report_embeddings(conn)

    project = conn.execute(
        text(
            """
            SELECT project_id, budget_usage_rate, delay_risk_rate
            FROM project_health_snapshots
            ORDER BY (budget_usage_rate + delay_risk_rate) DESC
            LIMIT 1
            """
        )
    ).mappings().first()

    if not project:
        project = conn.execute(
            text("SELECT project_id FROM projects ORDER BY project_id LIMIT 1")
        ).mappings().first()
        if not project:
            raise ValueError("no project data")
        project = {"project_id": project["project_id"], "budget_usage_rate": 0, "delay_risk_rate": 0}

    risk = max(int(project.get("budget_usage_rate") or 0), int(project.get("delay_risk_rate") or 0))
    severity = "high" if risk >= 80 else ("medium" if risk >= 60 else "low")
    summary = f"Watchdog alert for {project['project_id']} (risk {risk}%)"

    action_id = _ensure_action(conn, project["project_id"], severity)
    approval = request_approval(
        conn,
        action_id=action_id,
        requested_by="watchdog",
        summary=summary,
    )

    _upsert_checkpoint(
        conn,
        approval.thread_id,
        {
            "thread_id": approval.thread_id,
            "approval_request_id": approval.approval_request_id,
            "action_id": action_id,
            "summary": summary,
        },
        {"mode": "watchdog", "severity": severity},
    )

    return summary, severity, action_id, approval.thread_id


def _ensure_action(conn: Connection, project_id: str, severity: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT aa.action_id
            FROM autonomous_actions aa
            JOIN ai_strategy_proposals ap ON ap.proposal_id = aa.proposal_id
            WHERE ap.project_id = :project_id
              AND aa.status IN ('pending', 'approval_pending')
            ORDER BY aa.action_id DESC
            LIMIT 1
            """
        ),
        {"project_id": project_id},
    ).mappings().first()
    if row:
        return int(row["action_id"])

    proposal = conn.execute(
        text(
            """
            SELECT proposal_id
            FROM ai_strategy_proposals
            WHERE project_id = :project_id
            ORDER BY recommendation_score DESC
            LIMIT 1
            """
        ),
        {"project_id": project_id},
    ).mappings().first()

    if not proposal:
        conn.execute(
            text(
                """
                INSERT INTO ai_strategy_proposals
                  (project_id, plan_type, is_recommended, recommendation_score, description)
                VALUES
                  (:project_id, 'Plan_B', TRUE, 80, :description)
                """
            ),
            {"project_id": project_id, "description": f"Auto-generated watchdog proposal ({severity})"},
        )
        proposal = conn.execute(
            text(
                """
                SELECT proposal_id
                FROM ai_strategy_proposals
                WHERE project_id = :project_id
                ORDER BY proposal_id DESC
                LIMIT 1
                """
            ),
            {"project_id": project_id},
        ).mappings().first()

    conn.execute(
        text(
            """
            INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
            VALUES (:proposal_id, 'watchdog_alert', :draft_content, 'pending')
            """
        ),
        {
            "proposal_id": proposal["proposal_id"],
            "draft_content": f"Watchdog detected {severity} risk for {project_id}",
        },
    )
    action = conn.execute(
        text(
            """
            SELECT action_id
            FROM autonomous_actions
            WHERE proposal_id = :proposal_id
            ORDER BY action_id DESC
            LIMIT 1
            """
        ),
        {"proposal_id": proposal["proposal_id"]},
    ).mappings().first()
    return int(action["action_id"])


def _insert_watchdog_alert(
    conn: Connection,
    summary: str,
    severity: str,
    thread_id: str,
    action_id: int,
) -> None:
    alert_id = f"wdalert-{uuid4().hex[:12]}"
    project = conn.execute(
        text(
            """
            SELECT ap.project_id
            FROM autonomous_actions aa
            JOIN ai_strategy_proposals ap ON ap.proposal_id = aa.proposal_id
            WHERE aa.action_id = :action_id
            """
        ),
        {"action_id": action_id},
    ).mappings().first()
    conn.execute(
        text(
            """
            INSERT INTO watchdog_alerts
              (alert_id, thread_id, project_id, summary, severity, status, metadata)
            VALUES
              (:alert_id, :thread_id, :project_id, :summary, :severity, 'pending', :metadata)
            """
        ),
        {
            "alert_id": alert_id,
            "thread_id": thread_id,
            "project_id": project.get("project_id") if project else None,
            "summary": summary,
            "severity": severity,
            "metadata": json.dumps({"action_id": action_id}),
        },
    )


def _upsert_checkpoint(
    conn: Connection,
    thread_id: str,
    state: dict,
    metadata: dict,
) -> None:
    existing = conn.execute(
        text("SELECT 1 FROM langgraph_checkpoints WHERE thread_id = :thread_id"),
        {"thread_id": thread_id},
    ).scalar()

    if existing:
        conn.execute(
            text(
                """
                UPDATE langgraph_checkpoints
                SET checkpoint = :checkpoint,
                    metadata = :metadata,
                    updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = :thread_id
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint": json.dumps(state).encode("utf-8"),
                "metadata": json.dumps(metadata),
            },
        )
        return

    conn.execute(
        text(
            """
            INSERT INTO langgraph_checkpoints (thread_id, checkpoint, metadata)
            VALUES (:thread_id, :checkpoint, :metadata)
            """
        ),
        {
            "thread_id": thread_id,
            "checkpoint": json.dumps(state).encode("utf-8"),
            "metadata": json.dumps(metadata),
        },
    )
