from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
    return []


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


def _normalize_date(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return date.today().isoformat()
    return date.today().isoformat()



