from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.env import load_env  # noqa: E402

load_env()

from sqlalchemy import text  # noqa: E402

from app.data.seed import load_seed  # noqa: E402
from app.db import db_connection, engine, is_sqlite_engine  # noqa: E402


MIGRATIONS_DIR = ROOT / "migrations"


def _ensure_schema_migrations(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    for chunk in sql.split(";"):
        stmt = chunk.strip()
        if stmt:
            statements.append(stmt)
    return statements


def _apply_sql(conn, sql: str) -> None:
    for stmt in _split_sql(sql):
        conn.execute(text(stmt))


def _load_migrations(suffix: str) -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob(f"*{suffix}"))


def migrate_up() -> None:
    with db_connection() as conn:
        _ensure_schema_migrations(conn)
        applied = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
        for path in _load_migrations(".up.sql"):
            version = path.name.split("_", 1)[0]
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            if is_sqlite_engine(engine):
                sql = "\n".join(
                    line for line in sql.splitlines() if "CREATE EXTENSION" not in line.upper()
                )
                sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
                sql = sql.replace("BYTEA", "BLOB")
                sql = sql.replace("JSONB", "TEXT")
                sql = sql.replace("vector(1024)", "BLOB")
                sql = sql.replace("TEXT[]", "TEXT")
            _apply_sql(conn, sql)
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )


def migrate_down() -> None:
    with db_connection() as conn:
        _ensure_schema_migrations(conn)
        applied = list(
            conn.execute(text("SELECT version FROM schema_migrations ORDER BY version")).scalars()
        )
        if not applied:
            print("No migrations to roll back.")
            return
        version = applied[-1]
        candidates = [p for p in _load_migrations(".down.sql") if p.name.startswith(version)]
        if not candidates:
            raise RuntimeError(f"Missing down migration for version {version}")
        sql = candidates[0].read_text(encoding="utf-8")
        _apply_sql(conn, sql)
        conn.execute(text("DELETE FROM schema_migrations WHERE version = :version"), {"version": version})


def _wipe_tables(conn) -> None:
    table_order = [
        "external_action_runs",
        "execution_jobs",
        "hitl_approval_requests",
        "hitl_audit_logs",
        "hitl_states",
        "input_ingestion_runs",
        "watchdog_alerts",
        "watchdog_jobs",
        "user_skills",
        "user_profiles",
        "langgraph_checkpoints",
        "project_health_snapshots",
        "user_motivation_history",
        "autonomous_actions",
        "ai_strategy_proposals",
        "ai_analysis_results",
        "assignment_patterns",
        "weekly_reports",
        "assignments",
        "projects",
        "users",
    ]
    for table in table_order:
        conn.execute(text(f"DELETE FROM {table}"))


def _skill_level_from_cost(cost: int) -> int:
    if cost <= 0:
        return 1
    return max(1, min(10, round(cost / 12)))


def _determine_pattern(notes: str) -> str:
    lowered = notes.lower()
    if any(word in notes for word in ("疲労", "飽き", "燃え尽き", "限界")):
        return "burnout"
    if any(word in notes for word in ("対人トラブル", "噂", "炎上")):
        return "toxic"
    if any(word in notes for word in ("伸びしろ", "挑戦", "育成")):
        return "rising_star"
    if "顧問" in notes or "週1" in notes:
        return "constraint"
    if "高単価" in notes or "高額" in lowered:
        return "luxury"
    return "the_savior"


def _decision_from_pattern(pattern_id: str) -> str:
    if pattern_id in ("burnout", "toxic"):
        return "不採用"
    if pattern_id in ("rising_star", "constraint", "luxury"):
        return "条件付採用"
    return "採用"


def _risk_scores(pattern_id: str) -> tuple[int, int, int]:
    if pattern_id == "burnout":
        return (25, 90, 80)
    if pattern_id == "toxic":
        return (20, 85, 90)
    if pattern_id == "rising_star":
        return (60, 35, 45)
    if pattern_id == "luxury":
        return (85, 30, 40)
    if pattern_id == "constraint":
        return (40, 55, 45)
    return (10, 15, 15)


def seed_data(force: bool = False) -> None:
    seed = load_seed()
    projects = seed.get("projects", [])
    members = seed.get("members", [])

    with db_connection() as conn:
        if force:
            _wipe_tables(conn)
        else:
            existing = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
            if existing:
                print("Seed skipped: users already exist. Use --force to reseed.")
                return

        project_rows = []
        for p in projects:
            project_rows.append(
                {
                    "project_id": p.get("id"),
                    "name": p.get("name"),
                    "status": "稼働中",
                    "budget_cap": int(p.get("budget") or 0),
                    "difficulty_level": "L3",
                    "required_skills": json.dumps(p.get("requiredSkills") or [])
                    if is_sqlite_engine(engine)
                    else p.get("requiredSkills"),
                    "description": p.get("name"),
                }
            )
        if project_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO projects
                      (project_id, name, status, budget_cap, difficulty_level, required_skills, description)
                    VALUES
                      (:project_id, :name, :status, :budget_cap, :difficulty_level, :required_skills, :description)
                    """
                ),
                project_rows,
            )

        user_rows = []
        profile_rows = []
        skill_rows = []
        report_rows = []
        for m in members:
            notes = m.get("notes") or ""
            role = (m.get("skills") or [None])[0] or "Engineer"
            user_rows.append(
                {
                    "user_id": m.get("id"),
                    "name": m.get("name"),
                    "role": role,
                    "skill_level": _skill_level_from_cost(int(m.get("cost") or 0)),
                    "unit_price": int(m.get("cost") or 0),
                    "can_overtime": bool((m.get("availability") or 0) >= 80),
                    "career_aspiration": notes,
                }
            )
            profile_rows.append(
                {
                    "user_id": m.get("id"),
                    "availability_pct": int(m.get("availability") or 0),
                    "notes": notes,
                }
            )
            for skill in m.get("skills", []):
                skill_rows.append({"user_id": m.get("id"), "skill": skill})
            report_rows.append(
                {
                    "user_id": m.get("id"),
                    "posted_at": "2026-01-01 09:00:00",
                    "content": notes or "週報なし",
                }
            )

        if user_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO users
                      (user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration)
                    VALUES
                      (:user_id, :name, :role, :skill_level, :unit_price, :can_overtime, :career_aspiration)
                    """
                ),
                user_rows,
            )
        if profile_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO user_profiles (user_id, availability_pct, notes)
                    VALUES (:user_id, :availability_pct, :notes)
                    """
                ),
                profile_rows,
            )
        if skill_rows:
            conn.execute(
                text("INSERT INTO user_skills (user_id, skill) VALUES (:user_id, :skill)"),
                skill_rows,
            )
        if report_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO weekly_reports (user_id, posted_at, content)
                    VALUES (:user_id, :posted_at, :content)
                    """
                ),
                report_rows,
            )

        assignment_rows = []
        if projects and members:
            primary_project = projects[0].get("id")
            for member in members[:2]:
                assignment_rows.append(
                    {
                        "project_id": primary_project,
                        "user_id": member.get("id"),
                        "role_in_pj": "Dev",
                        "start_date": "2025-12-01",
                        "end_date": None,
                        "remarks": "Seed assignment",
                    }
                )
        if assignment_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO assignments (project_id, user_id, role_in_pj, start_date, end_date, remarks)
                    VALUES (:project_id, :user_id, :role_in_pj, :start_date, :end_date, :remarks)
                    """
                ),
                assignment_rows,
            )

        pattern_rows = [
            {"pattern_id": "the_savior", "name_ja": "全会一致", "description": "All signals align"},
            {"pattern_id": "burnout", "name_ja": "燃え尽き", "description": "High burnout risk"},
            {"pattern_id": "rising_star", "name_ja": "ダイヤの原石", "description": "High growth potential"},
            {"pattern_id": "luxury", "name_ja": "高嶺の花", "description": "Over budget but strong"},
            {"pattern_id": "toxic", "name_ja": "隠れ爆弾", "description": "Team risk"},
            {"pattern_id": "constraint", "name_ja": "制約あり", "description": "Availability constraints"},
        ]
        conn.execute(
            text(
                """
                INSERT INTO assignment_patterns (pattern_id, name_ja, description)
                VALUES (:pattern_id, :name_ja, :description)
                """
            ),
            pattern_rows,
        )

        analysis_rows = []
        for project in projects:
            for member in members:
                notes = member.get("notes") or ""
                pattern_id = _determine_pattern(notes)
                pm_risk, hr_risk, risk_risk = _risk_scores(pattern_id)
                debate_log = json.dumps(
                    {
                        "PM": "予算とスキルの観点で評価",
                        "HR": "コンディションをチェック",
                        "Risk": "離職/炎上リスクを推定",
                    },
                    ensure_ascii=False,
                )
                analysis_rows.append(
                    {
                        "user_id": member.get("id"),
                        "project_id": project.get("id"),
                        "pattern_id": pattern_id,
                        "pm_risk_score": pm_risk,
                        "hr_risk_score": hr_risk,
                        "risk_risk_score": risk_risk,
                        "debate_log": debate_log,
                        "final_decision": _decision_from_pattern(pattern_id),
                    }
                )
        if analysis_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_analysis_results
                      (user_id, project_id, pattern_id, pm_risk_score, hr_risk_score, risk_risk_score, debate_log, final_decision)
                    VALUES
                      (:user_id, :project_id, :pattern_id, :pm_risk_score, :hr_risk_score, :risk_risk_score, :debate_log, :final_decision)
                    """
                ),
                analysis_rows,
            )

        proposal_rows = []
        for project in projects:
            base_cost = int(project.get("budget") or 0)
            proposal_rows.extend(
                [
                    {
                        "project_id": project.get("id"),
                        "plan_type": "Plan_A",
                        "is_recommended": False,
                        "recommendation_score": 62,
                        "description": "既存体制を維持して短期安定を狙う",
                        "total_cost": base_cost,
                        "predicted_future_impact": "短期安定",
                    },
                    {
                        "project_id": project.get("id"),
                        "plan_type": "Plan_B",
                        "is_recommended": True,
                        "recommendation_score": 82,
                        "description": "成長枠を織り込んだ未来投資プラン",
                        "total_cost": base_cost + 20,
                        "predicted_future_impact": "中期成長",
                    },
                    {
                        "project_id": project.get("id"),
                        "plan_type": "Plan_C",
                        "is_recommended": False,
                        "recommendation_score": 55,
                        "description": "コスト重視で短期収益を最大化",
                        "total_cost": max(0, base_cost - 15),
                        "predicted_future_impact": "短期利益",
                    },
                ]
            )
        if proposal_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_strategy_proposals
                      (project_id, plan_type, is_recommended, recommendation_score, description, total_cost, predicted_future_impact)
                    VALUES
                      (:project_id, :plan_type, :is_recommended, :recommendation_score, :description, :total_cost, :predicted_future_impact)
                    """
                ),
                proposal_rows,
            )

        proposals = conn.execute(
            text("SELECT proposal_id, plan_type FROM ai_strategy_proposals ORDER BY proposal_id")
        ).mappings().all()
        action_rows = []
        for proposal in proposals[: max(1, len(proposals) // 2)]:
            action_rows.append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "action_type": "mail_draft",
                    "draft_content": f"{proposal['plan_type']} の根回しメール案",
                    "status": "pending",
                }
            )
        if action_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
                    VALUES (:proposal_id, :action_type, :draft_content, :status)
                    """
                ),
                action_rows,
            )

        snapshot_rows = []
        for idx, project in enumerate(projects):
            snapshot_rows.append(
                {
                    "project_id": project.get("id"),
                    "measured_date": date.today().isoformat(),
                    "budget_usage_rate": 70 + idx * 10,
                    "delay_risk_rate": 50 + idx * 15,
                    "overall_health": "warning" if idx % 2 else "safe",
                }
            )
        if snapshot_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO project_health_snapshots
                      (project_id, measured_date, budget_usage_rate, delay_risk_rate, overall_health)
                    VALUES
                      (:project_id, :measured_date, :budget_usage_rate, :delay_risk_rate, :overall_health)
                    """
                ),
                snapshot_rows,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="DB migration and seed tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="apply migrations")
    sub.add_parser("down", help="rollback last migration")
    seed_parser = sub.add_parser("seed", help="seed database")
    seed_parser.add_argument("--force", action="store_true", help="wipe data before seeding")

    args = parser.parse_args()
    if args.command == "up":
        migrate_up()
    elif args.command == "down":
        migrate_down()
    elif args.command == "seed":
        seed_data(force=args.force)


if __name__ == "__main__":
    main()
