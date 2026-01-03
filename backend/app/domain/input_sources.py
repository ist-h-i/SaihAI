from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.embeddings import ensure_weekly_report_embeddings

SOURCE_WEEKLY_REPORTS = "weekly_reports"

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
            content = str(row.get("content") or "")
            posted_at = str(row.get("posted_at") or "")
            if not user_id or not content:
                continue
            posted_at = _normalize_timestamp(posted_at)
            exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM weekly_reports
                    WHERE user_id = :user_id AND posted_at = :posted_at
                    LIMIT 1
                    """
                ),
                {"user_id": user_id, "posted_at": posted_at},
            ).scalar()
            if exists:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO weekly_reports (user_id, posted_at, content)
                    VALUES (:user_id, :posted_at, :content)
                    """
                ),
                {"user_id": user_id, "posted_at": posted_at, "content": content},
            )
            items_inserted += 1

        metadata["embeddings_updated"] = ensure_weekly_report_embeddings(conn)
    except Exception as exc:
        status = "failed"
        error = str(exc)

    finished_at = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            INSERT INTO input_ingestion_runs
              (run_id, source_type, status, items_inserted, started_at, finished_at, metadata, error)
            VALUES
              (:run_id, :source_type, :status, :items_inserted, :started_at, :finished_at, :metadata, :error)
            """
        ),
        {
            "run_id": run_id,
            "source_type": SOURCE_WEEKLY_REPORTS,
            "status": status,
            "items_inserted": items_inserted,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "metadata": _serialize_json(metadata),
            "error": error,
        },
    )
    return IngestionRunResult(
        run_id=run_id,
        source_type=SOURCE_WEEKLY_REPORTS,
        status=status,
        items_inserted=items_inserted,
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        metadata=metadata,
    )


def fetch_ingestion_runs(
    conn: Connection,
    source_type: str = SOURCE_WEEKLY_REPORTS,
    limit: int = 10,
) -> list[IngestionRunResult]:
    rows = conn.execute(
        text(
            """
            SELECT run_id, source_type, status, items_inserted, started_at, finished_at, metadata, error
            FROM input_ingestion_runs
            WHERE source_type = :source_type
            ORDER BY started_at DESC
            LIMIT :limit
            """
        ),
        {"source_type": source_type, "limit": limit},
    ).mappings().all()

    results: list[IngestionRunResult] = []
    for row in rows:
        started_at = _parse_timestamp(row.get("started_at"))
        finished_at = _parse_timestamp(row.get("finished_at"))
        results.append(
            IngestionRunResult(
                run_id=row["run_id"],
                source_type=row["source_type"],
                status=row["status"],
                items_inserted=int(row.get("items_inserted") or 0),
                started_at=started_at,
                finished_at=finished_at,
                error=row.get("error"),
                metadata=_deserialize_json(row.get("metadata")),
            )
        )
    return results


def _load_source(source: Path) -> list[dict[str, Any]]:
    if not source.exists():
        return []
    with source.open(encoding="utf-8") as handle:
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


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


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
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
    return value

