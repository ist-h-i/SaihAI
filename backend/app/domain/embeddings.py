from __future__ import annotations

import hashlib
import json
import random
from typing import Iterable

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
            SELECT report_id, content
            FROM weekly_reports
            WHERE content_embedding IS NULL
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
        content = row.get("content") or ""
        embedding = generate_embedding(content)
        payload = embedding_to_db_value(embedding, dialect)
        conn.execute(
            text(
                """
                UPDATE weekly_reports
                SET content_embedding = :embedding
                WHERE report_id = :report_id
                """
            ),
            {"embedding": payload, "report_id": row["report_id"]},
        )
        updated += 1
    return updated
