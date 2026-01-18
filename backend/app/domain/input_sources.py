from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.embeddings import ensure_weekly_report_embeddings

SOURCE_WEEKLY_REPORTS = "weekly_reports"
SOURCE_SLACK_LOGS = "slack_logs"
SOURCE_ATTENDANCE = "attendance"

SLACK_API_BASE = "https://slack.com/api"
SLACK_LOG_CHANNELS = [c.strip() for c in os.getenv("SLACK_LOG_CHANNELS", "").split(",") if c.strip()]
SLACK_LOG_LOOKBACK_DAYS = int(os.getenv("SLACK_LOG_LOOKBACK_DAYS", "14"))
SLACK_LOG_LIMIT = int(os.getenv("SLACK_LOG_LIMIT", "200"))
ATTENDANCE_LOG_SOURCE = os.getenv("ATTENDANCE_LOG_SOURCE", "")

DEFAULT_WEEKLY_REPORT_SOURCE = (
    Path(__file__).resolve().parents[1] / "data" / "weekly_reports_source.json"
)


@dataclass(frozen=True)
class IngestionRunResult:
    run_id: str
    source_type: str
    status: str
    items_inserted: int
    started_at: datetime
    finished_at: datetime
    error: str | None = None
    metadata: dict[str, Any] | None = None


def ingest_weekly_reports(
    conn: Connection,
    source_path: Path | None = None,
) -> IngestionRunResult:
    run_id = f"ing-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    items_inserted = 0
    error: str | None = None
    status = "succeeded"
    source = source_path or DEFAULT_WEEKLY_REPORT_SOURCE
    metadata: dict[str, Any] = {"source_path": str(source)}

    try:
        payload = _load_source(source)
        for row in payload:
            user_id = str(row.get("user_id") or "")
            project_id = str(row.get("project_id") or "")
            content = str(row.get("content_text") or "")
            reporting_date = _normalize_date(row.get("reporting_date"))
            reported_at = _normalize_timestamp(str(row.get("reported_at") or ""))
            if not user_id or not project_id or not content:
                continue
            exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM weekly_reports
                    WHERE user_id = :user_id
                      AND project_id = :project_id
                      AND reporting_date = :reporting_date
                    LIMIT 1
                    """
                ),
                {
                    "user_id": user_id,
                    "project_id": project_id,
                    "reporting_date": reporting_date,
                },
            ).scalar()
            if exists:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO weekly_reports
                      (user_id, project_id, reporting_date, content_text, reported_at)
                    VALUES
                      (:user_id, :project_id, :reporting_date, :content_text, :reported_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "project_id": project_id,
                    "reporting_date": reporting_date,
                    "content_text": content,
                    "reported_at": reported_at,
                },
            )
            items_inserted += 1

        metadata["embeddings_updated"] = ensure_weekly_report_embeddings(conn)
    except Exception as exc:
        status = "failed"
        error = str(exc)

    finished_at = datetime.now(timezone.utc)
    result = IngestionRunResult(
        run_id=run_id,
        source_type=SOURCE_WEEKLY_REPORTS,
        status=status,
        items_inserted=items_inserted,
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        metadata=metadata,
    )
    _record_ingestion_run(conn, result)
    return result


def fetch_ingestion_runs(
    conn: Connection,
    source_type: str = SOURCE_WEEKLY_REPORTS,
    limit: int = 10,
) -> list[IngestionRunResult]:
    rows = conn.execute(
        text(
            """
            SELECT run_id, source, status, payload, created_at
            FROM input_ingestion_runs
            WHERE source = :source
            ORDER BY run_id DESC
            LIMIT :limit
            """
        ),
        {"source": source_type, "limit": limit},
    ).mappings().all()

    results: list[IngestionRunResult] = []
    for row in rows:
        payload = _deserialize_payload(row.get("payload"))
        started_at = _normalize_timestamp(payload.get("started_at") or "")
        finished_at = _normalize_timestamp(payload.get("finished_at") or "")
        results.append(
            IngestionRunResult(
                run_id=str(payload.get("run_id") or row["run_id"]),
                source_type=str(row.get("source") or source_type),
                status=str(row.get("status") or payload.get("status") or "unknown"),
                items_inserted=int(payload.get("items_inserted") or 0),
                started_at=datetime.fromisoformat(started_at),
                finished_at=datetime.fromisoformat(finished_at),
                error=payload.get("error"),
                metadata=payload.get("metadata") or {},
            )
        )
    return results


def ingest_slack_logs(
    conn: Connection,
    channel_ids: list[str] | None = None,
    oldest: float | None = None,
    latest: float | None = None,
) -> IngestionRunResult:
    run_id = f"ing-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    items_inserted = 0
    error: str | None = None
    status = "succeeded"
    channels = channel_ids or SLACK_LOG_CHANNELS
    metadata: dict[str, Any] = {"channels": channels}

    if not channels:
        status = "failed"
        error = "SLACK_LOG_CHANNELS is empty"
    else:
        try:
            oldest_ts = oldest
            if oldest_ts is None:
                oldest_ts = (datetime.now(timezone.utc) - timedelta(days=SLACK_LOG_LOOKBACK_DAYS)).timestamp()
            for channel_id in channels:
                cursor: str | None = None
                while True:
                    payload = _slack_api_call(
                        "conversations.history",
                        {
                            "channel": channel_id,
                            "limit": SLACK_LOG_LIMIT,
                            "oldest": oldest_ts,
                            **({"latest": latest} if latest else {}),
                            **({"cursor": cursor} if cursor else {}),
                        },
                    )
                    messages = payload.get("messages") or []
                    items_inserted += _persist_slack_messages(conn, channel_id, messages)
                    cursor = payload.get("response_metadata", {}).get("next_cursor") or None
                    if not cursor:
                        break
        except Exception as exc:
            status = "failed"
            error = str(exc)

    finished_at = datetime.now(timezone.utc)
    result = IngestionRunResult(
        run_id=run_id,
        source_type=SOURCE_SLACK_LOGS,
        status=status,
        items_inserted=items_inserted,
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        metadata=metadata,
    )
    _record_ingestion_run(conn, result)
    return result


def ingest_attendance(
    conn: Connection,
    source_path: Path | None = None,
) -> IngestionRunResult:
    run_id = f"ing-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    items_inserted = 0
    error: str | None = None
    status = "succeeded"
    if source_path is None and not ATTENDANCE_LOG_SOURCE:
        source = None
    else:
        source = source_path or Path(ATTENDANCE_LOG_SOURCE)
    metadata: dict[str, Any] = {"source_path": str(source) if source else ""}

    if not source or not source.exists() or source.is_dir():
        status = "failed"
        error = f"attendance source not found: {source}"
    else:
        try:
            items_inserted = _load_attendance(conn, source)
        except Exception as exc:
            status = "failed"
            error = str(exc)

    finished_at = datetime.now(timezone.utc)
    result = IngestionRunResult(
        run_id=run_id,
        source_type=SOURCE_ATTENDANCE,
        status=status,
        items_inserted=items_inserted,
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        metadata=metadata,
    )
    _record_ingestion_run(conn, result)
    return result


def _load_source(source: Path) -> list[dict[str, Any]]:
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _normalize_timestamp(value: str) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _normalize_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return date.today().isoformat()
    return date.today().isoformat()


def _slack_api_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    token = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured")
    query = urllib.parse.urlencode(params)
    url = f"{SLACK_API_BASE}/{method}?{query}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Slack API error: {exc}") from exc
    payload = json.loads(body)
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API error: {payload.get('error')}")
    return payload


def _persist_slack_messages(conn: Connection, channel_id: str, messages: list[dict[str, Any]]) -> int:
    dialect = conn.engine.dialect.name
    inserted = 0
    for message in messages:
        message_ts = str(message.get("ts") or "")
        if not message_ts:
            continue
        row = {
            "channel_id": channel_id,
            "message_ts": message_ts,
            "user_id": message.get("user") or message.get("bot_id"),
            "text": message.get("text") or "",
            "thread_ts": message.get("thread_ts"),
            "client_msg_id": message.get("client_msg_id"),
            "message_type": message.get("subtype") or "message",
            "raw_payload": json.dumps(message, ensure_ascii=False),
        }
        inserted += _insert_slack_message(conn, row, dialect)
    return inserted


def _insert_slack_message(conn: Connection, row: dict[str, Any], dialect: str) -> int:
    if dialect.startswith("postgres"):
        result = conn.execute(
            text(
                """
                INSERT INTO slack_messages
                  (channel_id, message_ts, user_id, text, thread_ts, client_msg_id, message_type, raw_payload)
                VALUES
                  (:channel_id, :message_ts, :user_id, :text, :thread_ts, :client_msg_id, :message_type, :raw_payload)
                ON CONFLICT (channel_id, message_ts) DO NOTHING
                """
            ),
            row,
        )
        return result.rowcount or 0
    result = conn.execute(
        text(
            """
            INSERT OR IGNORE INTO slack_messages
              (channel_id, message_ts, user_id, text, thread_ts, client_msg_id, message_type, raw_payload)
            VALUES
              (:channel_id, :message_ts, :user_id, :text, :thread_ts, :client_msg_id, :message_type, :raw_payload)
            """
        ),
        row,
    )
    return result.rowcount or 0


def _load_attendance(conn: Connection, source: Path) -> int:
    dialect = conn.engine.dialect.name
    inserted = 0
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            employee_id = str(row.get("employee_id") or row.get("user_id") or "").strip()
            if not employee_id:
                continue
            work_date = _normalize_date(row.get("work_date") or row.get("date"))
            status = str(row.get("status") or "")
            hours_worked = float(row.get("hours_worked") or 0)
            overtime_hours = float(row.get("overtime_hours") or 0)
            inserted += _insert_attendance_row(
                conn,
                {
                    "employee_id": employee_id,
                    "work_date": work_date,
                    "status": status,
                    "hours_worked": hours_worked,
                    "overtime_hours": overtime_hours,
                    "source": str(source),
                },
                dialect,
            )
    return inserted


def _insert_attendance_row(conn: Connection, row: dict[str, Any], dialect: str) -> int:
    if dialect.startswith("postgres"):
        result = conn.execute(
            text(
                """
                INSERT INTO attendance_logs
                  (employee_id, work_date, status, hours_worked, overtime_hours, source)
                VALUES
                  (:employee_id, :work_date, :status, :hours_worked, :overtime_hours, :source)
                ON CONFLICT (employee_id, work_date) DO NOTHING
                """
            ),
            row,
        )
        return result.rowcount or 0
    result = conn.execute(
        text(
            """
            INSERT OR IGNORE INTO attendance_logs
              (employee_id, work_date, status, hours_worked, overtime_hours, source)
            VALUES
              (:employee_id, :work_date, :status, :hours_worked, :overtime_hours, :source)
            """
        ),
        row,
    )
    return result.rowcount or 0


def _record_ingestion_run(conn: Connection, result: IngestionRunResult) -> None:
    payload = {
        "run_id": result.run_id,
        "status": result.status,
        "items_inserted": result.items_inserted,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "error": result.error,
        "metadata": result.metadata or {},
    }
    conn.execute(
        text(
            """
            INSERT INTO input_ingestion_runs (source, status, payload)
            VALUES (:source, :status, :payload)
            """
        ),
        {
            "source": result.source_type,
            "status": result.status,
            "payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def _deserialize_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}



