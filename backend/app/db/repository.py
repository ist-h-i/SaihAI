from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.security import decrypt_value, encrypt_value


@dataclass(frozen=True)
class GoogleOAuthToken:
    user_id: str
    google_email: str
    access_token: str
    refresh_token: str
    token_type: str | None = None
    scope: str | None = None
    expires_at: datetime | None = None


def _parse_text_array(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, tuple):
        return [str(v) for v in value]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except json.JSONDecodeError:
                pass
        if raw.startswith("{") and raw.endswith("}"):
            inner = raw[1:-1]
            if not inner:
                return []
            return [v.strip() for v in inner.split(",") if v.strip()]
        return [v.strip() for v in raw.split(",") if v.strip()]
    return [str(value)]


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _to_google_oauth_token(row: dict[str, Any]) -> GoogleOAuthToken:
    access_token = decrypt_value(row.get("access_token"))
    refresh_token = decrypt_value(row.get("refresh_token"))
    if not access_token or not refresh_token:
        raise ValueError("google oauth token missing encrypted values")
    return GoogleOAuthToken(
        user_id=str(row.get("user_id")),
        google_email=str(row.get("google_email")),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=row.get("token_type"),
        scope=row.get("scope"),
        expires_at=_parse_timestamp(row.get("expires_at")),
    )


def fetch_google_oauth_token_by_user(conn: Connection, user_id: str) -> GoogleOAuthToken | None:
    row = conn.execute(
        text(
            """
            SELECT user_id, google_email, access_token, refresh_token, token_type, scope, expires_at
            FROM google_oauth_tokens
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return None
    return _to_google_oauth_token(row)


def fetch_google_oauth_token_by_email(conn: Connection, email: str) -> GoogleOAuthToken | None:
    row = conn.execute(
        text(
            """
            SELECT user_id, google_email, access_token, refresh_token, token_type, scope, expires_at
            FROM google_oauth_tokens
            WHERE google_email = :email
            """
        ),
        {"email": email},
    ).mappings().first()
    if not row:
        return None
    return _to_google_oauth_token(row)


def upsert_google_oauth_token(
    conn: Connection,
    *,
    user_id: str,
    google_email: str,
    access_token: str,
    refresh_token: str | None,
    token_type: str | None,
    scope: str | None,
    expires_at: datetime | None,
) -> None:
    if not refresh_token:
        existing = fetch_google_oauth_token_by_user(conn, user_id)
        if existing:
            refresh_token = existing.refresh_token
    if not refresh_token:
        raise ValueError("refresh token is required for google oauth")
    encrypted_access = encrypt_value(access_token)
    encrypted_refresh = encrypt_value(refresh_token)
    conn.execute(
        text(
            """
            INSERT INTO google_oauth_tokens
              (user_id, google_email, access_token, refresh_token, token_type, scope, expires_at, updated_at)
            VALUES
              (:user_id, :google_email, :access_token, :refresh_token, :token_type, :scope, :expires_at, :updated_at)
            ON CONFLICT (user_id) DO UPDATE SET
              google_email = excluded.google_email,
              access_token = excluded.access_token,
              refresh_token = excluded.refresh_token,
              token_type = excluded.token_type,
              scope = excluded.scope,
              expires_at = excluded.expires_at,
              updated_at = excluded.updated_at
            """
        ),
        {
            "user_id": user_id,
            "google_email": google_email,
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_type": token_type,
            "scope": scope,
            "expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc),
        },
    )


def fetch_projects(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT project_id, project_name, status, budget_cap, difficulty_level, required_skills, description
            FROM projects
            ORDER BY project_id
            """
        )
    ).mappings()
    projects: list[dict[str, Any]] = []
    for row in rows:
        projects.append(
            {
                "id": row["project_id"],
                "name": row["project_name"],
                "budget": int(row["budget_cap"] or 0),
                "requiredSkills": _parse_text_array(row["required_skills"]),
                "status": row["status"],
                "difficulty": row["difficulty_level"],
                "description": row["description"],
            }
        )
    return projects


def fetch_project(conn: Connection, project_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT project_id, project_name, status, budget_cap, difficulty_level, required_skills, description
            FROM projects
            WHERE project_id = :project_id
            """
        ),
        {"project_id": project_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["project_id"],
        "name": row["project_name"],
        "budget": int(row["budget_cap"] or 0),
        "requiredSkills": _parse_text_array(row["required_skills"]),
        "status": row["status"],
        "difficulty": row["difficulty_level"],
        "description": row["description"],
    }


def _load_member_assignments(
    conn: Connection, user_ids: Iterable[str]
) -> dict[str, list[dict[str, Any]]]:
    ids = list(user_ids)
    if not ids:
        return {}
    stmt = text(
            """
            SELECT assignment_id, user_id, project_id, role_in_pj, allocation_rate, start_date, end_date
            FROM assignments
            WHERE user_id IN :ids
            ORDER BY assignment_id
            """
    ).bindparams(bindparam("ids", expanding=True))
    assignment_rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assignment_rows:
        grouped[row["user_id"]].append(dict(row))
    return grouped


def _load_project_skills(conn: Connection, project_ids: Iterable[str]) -> dict[str, list[str]]:
    ids = list({pid for pid in project_ids if pid})
    if not ids:
        return {}
    stmt = text(
            """
            SELECT project_id, required_skills
            FROM projects
            WHERE project_id IN :ids
            """
    ).bindparams(bindparam("ids", expanding=True))
    rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    return {row["project_id"]: _parse_text_array(row["required_skills"]) for row in rows}


def _load_latest_reports(conn: Connection, user_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    ids = list(user_ids)
    if not ids:
        return {}
    stmt = text(
            """
            SELECT user_id, reporting_date, reported_at, content_text
            FROM weekly_reports
            WHERE user_id IN :ids
            ORDER BY user_id, reporting_date DESC, reported_at DESC
            """
    ).bindparams(bindparam("ids", expanding=True))
    rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["user_id"] not in latest:
            latest[row["user_id"]] = dict(row)
    return latest


def _availability_from_assignments(assignments: list[dict[str, Any]]) -> int:
    if not assignments:
        return 100
    today = date.today()
    active = 0.0
    for assignment in assignments:
        start = assignment.get("start_date")
        end = assignment.get("end_date")
        if start and isinstance(start, date) and start > today:
            continue
        if end and isinstance(end, date) and end < today:
            continue
        active += float(assignment.get("allocation_rate") or 0)
    return max(0, min(100, round(100 - active * 100)))


def _collect_member_skills(
    member_role: str | None,
    assignments: list[dict[str, Any]],
    project_skills: dict[str, list[str]],
) -> list[str]:
    collected: list[str] = []
    if member_role:
        collected.append(member_role)
    for assignment in assignments:
        role = assignment.get("role_in_pj")
        if role:
            collected.append(str(role))
        for skill in project_skills.get(assignment.get("project_id"), []):
            collected.append(skill)
    seen: set[str] = set()
    unique: list[str] = []
    for skill in collected:
        if skill and skill not in seen:
            seen.add(skill)
            unique.append(skill)
    return unique


def fetch_members(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT user_id, name, role, skill_level, cost_per_month, can_overtime, career_aspiration
            FROM users
            ORDER BY user_id
            """
        )
    ).mappings().all()
    user_ids = [row["user_id"] for row in rows]
    assignments_map = _load_member_assignments(conn, user_ids)
    project_skills = _load_project_skills(
        conn,
        [assignment.get("project_id") for assignments in assignments_map.values() for assignment in assignments],
    )
    latest_reports = _load_latest_reports(conn, user_ids)

    members: list[dict[str, Any]] = []
    for row in rows:
        assignments = assignments_map.get(row["user_id"], [])
        skills = _collect_member_skills(row.get("role"), assignments, project_skills)
        availability = _availability_from_assignments(assignments)
        if availability == 100 and row.get("can_overtime") is False:
            availability = 80
        report = latest_reports.get(row["user_id"], {})
        notes = report.get("content_text") or row.get("career_aspiration") or ""
        members.append(
            {
                "id": row["user_id"],
                "name": row["name"],
                "cost": int(row["cost_per_month"] or 0),
                "availability": int(availability),
                "skills": [s for s in skills if s],
                "notes": notes,
                "role": row.get("role"),
                "skillLevel": row.get("skill_level"),
                "careerAspiration": row.get("career_aspiration"),
            }
        )
    return members


def fetch_members_by_ids(conn: Connection, user_ids: Iterable[str]) -> list[dict[str, Any]]:
    ids = list(user_ids)
    if not ids:
        return []
    stmt = text(
            """
            SELECT user_id, name, role, skill_level, cost_per_month, can_overtime, career_aspiration
            FROM users
            WHERE user_id IN :ids
            """
    ).bindparams(bindparam("ids", expanding=True))
    rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    assignments_map = _load_member_assignments(conn, [row["user_id"] for row in rows])
    project_skills = _load_project_skills(
        conn,
        [assignment.get("project_id") for assignments in assignments_map.values() for assignment in assignments],
    )
    latest_reports = _load_latest_reports(conn, [row["user_id"] for row in rows])

    members: list[dict[str, Any]] = []
    for row in rows:
        assignments = assignments_map.get(row["user_id"], [])
        skills = _collect_member_skills(row.get("role"), assignments, project_skills)
        availability = _availability_from_assignments(assignments)
        if availability == 100 and row.get("can_overtime") is False:
            availability = 80
        report = latest_reports.get(row["user_id"], {})
        notes = report.get("content_text") or row.get("career_aspiration") or ""
        members.append(
            {
                "id": row["user_id"],
                "name": row["name"],
                "cost": int(row["cost_per_month"] or 0),
                "availability": int(availability),
                "skills": [s for s in skills if s],
                "notes": notes,
                "role": row.get("role"),
                "skillLevel": row.get("skill_level"),
                "careerAspiration": row.get("career_aspiration"),
            }
        )
    return members


def fetch_project_team(conn: Connection, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT user_id, role_in_pj, allocation_rate
            FROM assignments
            WHERE project_id = :project_id
            ORDER BY assignment_id
            """
        ),
        {"project_id": project_id},
    ).mappings().all()
    if not rows:
        return []
    assignment_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        user_id = row["user_id"]
        if user_id not in assignment_map:
            assignment_map[user_id] = dict(row)
            continue
        existing = assignment_map[user_id]
        if (row.get("allocation_rate") or 0) > (existing.get("allocation_rate") or 0):
            assignment_map[user_id] = dict(row)

    members = fetch_members_by_ids(conn, assignment_map.keys())
    for member in members:
        assignment = assignment_map.get(member["id"])
        if assignment:
            member["assignment"] = {
                "role": assignment.get("role_in_pj"),
                "allocationRate": float(assignment.get("allocation_rate") or 0),
            }
    return members


def fetch_member_detail(conn: Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT user_id, name, role, skill_level, cost_per_month, can_overtime, career_aspiration
            FROM users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return None
    assignments = _load_member_assignments(conn, [user_id]).get(user_id, [])
    project_skills = _load_project_skills(
        conn, [assignment.get("project_id") for assignment in assignments]
    )
    skills = _collect_member_skills(row.get("role"), assignments, project_skills)
    availability = _availability_from_assignments(assignments)
    if availability == 100 and row.get("can_overtime") is False:
        availability = 80
    report = _load_latest_reports(conn, [user_id]).get(user_id, {})
    notes = report.get("content_text") or row.get("career_aspiration") or ""
    return {
        "id": row["user_id"],
        "name": row["name"],
        "cost": int(row["cost_per_month"] or 0),
        "availability": int(availability),
        "skills": [s for s in skills if s],
        "notes": notes,
        "role": row.get("role"),
        "skillLevel": row.get("skill_level"),
        "careerAspiration": row.get("career_aspiration"),
    }


def fetch_user(conn: Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT user_id, name, role, skill_level, cost_per_month, can_overtime, career_aspiration
            FROM users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    return dict(row) if row else None
