from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection


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


def fetch_projects(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT project_id, name, status, budget_cap, difficulty_level, required_skills, description
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
                "name": row["name"],
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
            SELECT project_id, name, status, budget_cap, difficulty_level, required_skills, description
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
        "name": row["name"],
        "budget": int(row["budget_cap"] or 0),
        "requiredSkills": _parse_text_array(row["required_skills"]),
        "status": row["status"],
        "difficulty": row["difficulty_level"],
        "description": row["description"],
    }


def _load_member_profiles(conn: Connection, user_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    ids = list(user_ids)
    if not ids:
        return {}
    stmt = text(
            """
            SELECT user_id, availability_pct, notes
            FROM user_profiles
            WHERE user_id IN :ids
            """
    ).bindparams(bindparam("ids", expanding=True))
    profile_rows = conn.execute(stmt, {"ids": ids}).mappings()
    return {row["user_id"]: dict(row) for row in profile_rows}


def _load_member_skills(conn: Connection, user_ids: Iterable[str]) -> dict[str, list[str]]:
    ids = list(user_ids)
    if not ids:
        return {}
    skills = defaultdict(list)
    stmt = text(
            """
            SELECT user_id, skill
            FROM user_skills
            WHERE user_id IN :ids
            ORDER BY skill
            """
    ).bindparams(bindparam("ids", expanding=True))
    skill_rows = conn.execute(stmt, {"ids": ids}).mappings()
    for row in skill_rows:
        skills[row["user_id"]].append(row["skill"])
    return skills


def fetch_members(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration
            FROM users
            ORDER BY user_id
            """
        )
    ).mappings().all()
    user_ids = [row["user_id"] for row in rows]
    profiles = _load_member_profiles(conn, user_ids)
    skills_map = _load_member_skills(conn, user_ids)

    members: list[dict[str, Any]] = []
    for row in rows:
        profile = profiles.get(row["user_id"], {})
        skills = skills_map.get(row["user_id"]) or ([row["role"]] if row["role"] else [])
        availability = profile.get("availability_pct")
        if availability is None:
            availability = 80 if row.get("can_overtime") else 60
        notes = profile.get("notes") or row.get("career_aspiration") or ""
        members.append(
            {
                "id": row["user_id"],
                "name": row["name"],
                "cost": int(row["unit_price"] or 0),
                "availability": int(availability or 0),
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
            SELECT user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration
            FROM users
            WHERE user_id IN :ids
            """
    ).bindparams(bindparam("ids", expanding=True))
    rows = conn.execute(stmt, {"ids": ids}).mappings().all()
    profiles = _load_member_profiles(conn, [row["user_id"] for row in rows])
    skills_map = _load_member_skills(conn, [row["user_id"] for row in rows])

    members: list[dict[str, Any]] = []
    for row in rows:
        profile = profiles.get(row["user_id"], {})
        skills = skills_map.get(row["user_id"]) or ([row["role"]] if row["role"] else [])
        availability = profile.get("availability_pct")
        if availability is None:
            availability = 80 if row.get("can_overtime") else 60
        notes = profile.get("notes") or row.get("career_aspiration") or ""
        members.append(
            {
                "id": row["user_id"],
                "name": row["name"],
                "cost": int(row["unit_price"] or 0),
                "availability": int(availability or 0),
                "skills": [s for s in skills if s],
                "notes": notes,
                "role": row.get("role"),
                "skillLevel": row.get("skill_level"),
                "careerAspiration": row.get("career_aspiration"),
            }
        )
    return members


def fetch_member_detail(conn: Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration
            FROM users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return None
    profile = _load_member_profiles(conn, [user_id]).get(user_id, {})
    skills = _load_member_skills(conn, [user_id]).get(user_id) or ([row["role"]] if row["role"] else [])
    availability = profile.get("availability_pct")
    if availability is None:
        availability = 80 if row.get("can_overtime") else 60
    notes = profile.get("notes") or row.get("career_aspiration") or ""
    return {
        "id": row["user_id"],
        "name": row["name"],
        "cost": int(row["unit_price"] or 0),
        "availability": int(availability or 0),
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
            SELECT user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration
            FROM users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    return dict(row) if row else None
