from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Iterable

from sqlalchemy.engine import Connection
from sqlalchemy import text


EMBEDDING_DIM = 1024


def generate_embedding(text_value: str, dim: int = EMBEDDING_DIM) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text_value.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    return [round(rng.uniform(-1.0, 1.0), 6) for _ in range(dim)]


def embedding_to_db_value(embedding: Iterable[float], dialect: str) -> str:
    values = list(embedding)
    if dialect.startswith("postgres"):
        return f"[{','.join(f'{v:.6f}' for v in values)}]"
    return json.dumps(values)


def ensure_weekly_report_embeddings(conn: Connection, limit: int = 50) -> int:
    rows = conn.execute(
        text(
            """
            SELECT report_id, content_text
            FROM weekly_reports
            WHERE content_vector IS NULL
            ORDER BY report_id
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    if not rows:
        return 0

    dialect = conn.engine.dialect.name
    updated = 0
    for row in rows:
        content = row.get("content_text") or ""
        embedding = generate_embedding(content)
        payload = embedding_to_db_value(embedding, dialect)
        conn.execute(
            text(
                """
                UPDATE weekly_reports
                SET content_vector = :embedding
                WHERE report_id = :report_id
                """
            ),
            {"embedding": payload, "report_id": row["report_id"]},
        )
        updated += 1
    return updated


def search_weekly_reports(
    conn: Connection,
    query_text: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    query_embedding = generate_embedding(query_text)
    rows = conn.execute(
        text(
            """
            SELECT report_id, user_id, project_id, reporting_date, content_text, content_vector
            FROM weekly_reports
            WHERE content_vector IS NOT NULL
            ORDER BY report_id
            """
        )
    ).mappings().all()
    scored: list[dict[str, Any]] = []
    for row in rows:
        embedding = _parse_embedding(row.get("content_vector"))
        if not embedding:
            continue
        score = _cosine_similarity(query_embedding, embedding)
        scored.append(
            {
                "report_id": row["report_id"],
                "user_id": row.get("user_id"),
                "project_id": row.get("project_id"),
                "reporting_date": row.get("reporting_date"),
                "content_text": row.get("content_text"),
                "score": score,
            }
        )
    scored.sort(key=lambda item: item.get("score") or 0, reverse=True)
    return scored[:limit]


def _parse_embedding(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [float(v) for v in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            stripped = stripped[1:-1].strip()
            if not stripped:
                return []
            try:
                return [float(v) for v in stripped.split(",")]
            except ValueError:
                return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [float(v) for v in parsed]
    return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(length))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(length)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(length)))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
