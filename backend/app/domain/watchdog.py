from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.agents.drafting import DraftingResult, generate_drafts
from app.agents.gunshi import GunshiPlan, generate_plans
from app.agents.monitor import MonitorResult, analyze_risk
from app.domain.embeddings import ensure_weekly_report_embeddings
from app.domain.hitl import request_approval

POSITIVE_WORDS = ("挑戦", "伸びしろ", "育成", "学び", "成長")
NEGATIVE_WORDS = ("疲労", "飽き", "燃え尽き", "限界")
RISK_WORDS = ("炎上", "対人トラブル", "噂", "不満")

logger = logging.getLogger("saihai.watchdog")


def enqueue_watchdog_job(conn: Connection, payload: dict | None = None) -> dict[str, str]:
    conn.execute(
        text(
            """
            INSERT INTO watchdog_jobs (status, payload)
            VALUES ('queued', :payload)
            """
        ),
        {"payload": json.dumps(payload or {}, ensure_ascii=False)},
    )
    job_id = conn.execute(
        text(
            """
            SELECT job_id
            FROM watchdog_jobs
            ORDER BY job_id DESC
            LIMIT 1
            """
        )
    ).scalar()
    return {"job_id": str(job_id), "status": "queued"}


def run_watchdog_job(conn: Connection, job_id: str | None = None) -> dict[str, str]:
    if isinstance(job_id, str) and job_id.isdigit():
        job_id = int(job_id)
    job_id = job_id or _next_watchdog_job_id(conn)
    if not job_id:
        raise ValueError("no queued job")

    _update_watchdog_job(conn, job_id, "running", None)
    try:
        summary = _perform_watchdog_cycle(conn, job_id=str(job_id))
        _update_watchdog_job(conn, job_id, "succeeded", summary)
        _record_watchdog_alerts(conn, job_id=job_id, alerts=summary.get("alerts") or [])
        return {
            "job_id": str(job_id),
            "status": "succeeded",
            "summary": summary.get("summary", "watchdog completed"),
        }
    except Exception as exc:
        _update_watchdog_job(conn, job_id, "failed", {"error": str(exc)})
        raise


def _perform_watchdog_cycle(conn: Connection, job_id: str | None = None) -> dict[str, Any]:
    ensure_weekly_report_embeddings(conn)

    users = conn.execute(
        text(
            """
            SELECT user_id, name, role, cost_per_month, career_aspiration
            FROM users
            ORDER BY user_id
            """
        )
    ).mappings().all()
    projects = conn.execute(
        text(
            """
            SELECT project_id, project_name, manager_id, budget_cap
            FROM projects
            ORDER BY project_id
            """
        )
    ).mappings().all()
    assignments = conn.execute(
        text(
            """
            SELECT assignment_id, user_id, project_id, allocation_rate
            FROM assignments
            ORDER BY assignment_id
            """
        )
    ).mappings().all()
    reports = conn.execute(
        text(
            """
            SELECT user_id, project_id, reporting_date, content_text
            FROM weekly_reports
            ORDER BY reporting_date DESC
            """
        )
    ).mappings().all()

    report_by_user = _latest_report_by_user(reports)
    report_by_project = _reports_by_project(reports)

    motivation_map: dict[str, float] = {}
    today = date.today().isoformat()
    for user in users:
        notes = report_by_user.get(user["user_id"], user.get("career_aspiration") or "")
        motivation_score, sentiment_score = _score_motivation(notes)
        motivation_map[user["user_id"]] = motivation_score
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM user_motivation_history
                WHERE user_id = :user_id AND recorded_at = :recorded_at
                """
            ),
            {"user_id": user["user_id"], "recorded_at": today},
        ).scalar()
        if exists:
            continue
        conn.execute(
            text(
                """
                INSERT INTO user_motivation_history
                  (user_id, motivation_score, sentiment_score, ai_summary, recorded_at)
                VALUES
                  (:user_id, :motivation_score, :sentiment_score, :ai_summary, :recorded_at)
                """
            ),
            {
                "user_id": user["user_id"],
                "motivation_score": motivation_score,
                "sentiment_score": sentiment_score,
                "ai_summary": _summarize_motivation(notes),
                "recorded_at": today,
            },
        )

    project_health: dict[str, dict] = {}
    alerts: list[dict[str, Any]] = []
    for project in projects:
        project_id = project["project_id"]
        project_notes = " ".join(report_by_project.get(project_id, []))
        health_score, risk_level = _score_project_health(project_notes)
        variance_score = _score_variance(project_id, assignments, motivation_map)
        manager_gap_score = _score_manager_gap(project.get("manager_id"), project_id, assignments, motivation_map)
        project_health[project_id] = {
            "health_score": health_score,
            "risk_level": risk_level,
            "variance_score": variance_score,
            "manager_gap_score": manager_gap_score,
        }
        if risk_level != "Safe":
            alerts.append(
                {
                    "project_id": project_id,
                    "risk_level": risk_level,
                    "health_score": health_score,
                }
            )

        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM project_health_snapshots
                WHERE project_id = :project_id AND DATE(calculated_at) = :calculated_at
                """
            ),
            {"project_id": project_id, "calculated_at": today},
        ).scalar()
        if exists:
            continue

        conn.execute(
            text(
                """
                INSERT INTO project_health_snapshots
                  (project_id, health_score, risk_level, variance_score, manager_gap_score, aggregate_vector, calculated_at)
                VALUES
                  (:project_id, :health_score, :risk_level, :variance_score, :manager_gap_score, :aggregate_vector, :calculated_at)
                """
            ),
            {
                "project_id": project_id,
                "health_score": health_score,
                "risk_level": risk_level,
                "variance_score": variance_score,
                "manager_gap_score": manager_gap_score,
                "aggregate_vector": None,
                "calculated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    _ensure_patterns(conn)
    _refresh_analysis(conn, assignments, report_by_user)
    _ensure_proposals(conn, projects, project_health)
    actions_created = _ensure_actions(conn, projects, project_health, report_by_project)

    summary = f"watchdog updated: {len(projects)} projects / {len(users)} users"
    if actions_created:
        summary = f"watchdog created {actions_created} actions"
    return {"summary": summary, "job_id": job_id or f"wdjob-{uuid4().hex[:12]}", "alerts": alerts}


def _next_watchdog_job_id(conn: Connection) -> str | None:
    return conn.execute(
        text(
            """
            SELECT job_id
            FROM watchdog_jobs
            WHERE status = 'queued'
            ORDER BY job_id
            LIMIT 1
            """
        )
    ).scalar()


def _update_watchdog_job(conn: Connection, job_id: str, status: str, payload: dict | None) -> None:
    conn.execute(
        text(
            """
            UPDATE watchdog_jobs
            SET status = :status,
                payload = :payload
            WHERE job_id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "status": status,
            "payload": json.dumps(payload or {}, ensure_ascii=False),
        },
    )


def _record_watchdog_alerts(conn: Connection, job_id: int | str, alerts: list[dict[str, Any]]) -> None:
    for alert in alerts:
        message = f"{alert.get('project_id')} risk {alert.get('risk_level')} score {alert.get('health_score')}"
        conn.execute(
            text(
                """
                INSERT INTO watchdog_alerts (job_id, alert_level, message)
                VALUES (:job_id, :alert_level, :message)
                """
            ),
            {
                "job_id": job_id,
                "alert_level": alert.get("risk_level"),
                "message": message,
            },
        )


def _ensure_patterns(conn: Connection) -> None:
    patterns = [
        {"pattern_id": "the_savior", "name_ja": "全会一致", "description": "All signals align"},
        {"pattern_id": "burnout", "name_ja": "燃え尽き", "description": "High burnout risk"},
        {"pattern_id": "rising_star", "name_ja": "ダイヤの原石", "description": "High growth potential"},
        {"pattern_id": "luxury", "name_ja": "高嶺の花", "description": "Over budget but strong"},
        {"pattern_id": "toxic", "name_ja": "隠れ爆弾", "description": "Team risk"},
        {"pattern_id": "constraint", "name_ja": "制約あり", "description": "Availability constraints"},
    ]
    for pattern in patterns:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM assignment_patterns
                WHERE pattern_id = :pattern_id
                """
            ),
            {"pattern_id": pattern["pattern_id"]},
        ).scalar()
        if exists:
            continue
        conn.execute(
            text(
                """
                INSERT INTO assignment_patterns (pattern_id, name_ja, description)
                VALUES (:pattern_id, :name_ja, :description)
                """
            ),
            pattern,
        )


def _latest_report_by_user(reports: list[dict]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for row in reports:
        if row["user_id"] not in latest:
            latest[row["user_id"]] = row.get("content_text") or ""
    return latest


def _reports_by_project(reports: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in reports:
        grouped.setdefault(row["project_id"], []).append(row.get("content_text") or "")
    return grouped


def _score_motivation(text_value: str) -> tuple[float, float]:
    positive = _count_hits(text_value, POSITIVE_WORDS)
    negative = _count_hits(text_value, NEGATIVE_WORDS)
    score = _clamp(60 + positive * 12 - negative * 20, 0, 100)
    sentiment = _clamp((positive - negative) / 4, -1.0, 1.0)
    return score, sentiment


def _summarize_motivation(text_value: str) -> str:
    positive = _count_hits(text_value, POSITIVE_WORDS)
    negative = _count_hits(text_value, NEGATIVE_WORDS)
    if negative > positive:
        return "負荷が高く、ケアが必要です。"
    if positive > 0:
        return "前向きな兆候があり、育成機会を活かせます。"
    return "安定傾向。"


def _score_project_health(text_value: str) -> tuple[float, str]:
    positive = _count_hits(text_value, POSITIVE_WORDS)
    negative = _count_hits(text_value, NEGATIVE_WORDS)
    risk = _count_hits(text_value, RISK_WORDS)
    score = _clamp(80 + positive * 8 - negative * 15 - risk * 10, 0, 100)
    if score <= 50:
        return score, "Critical"
    if score <= 70:
        return score, "Warning"
    return score, "Safe"


def _score_variance(
    project_id: str,
    assignments: list[dict],
    motivation_map: dict[str, float],
) -> float:
    members = [a["user_id"] for a in assignments if a["project_id"] == project_id]
    values = [motivation_map.get(user_id, 0) for user_id in members]
    if len(values) <= 1:
        return 0.0
    return round((max(values) - min(values)) / 100, 2)


def _score_manager_gap(
    manager_id: str | None,
    project_id: str,
    assignments: list[dict],
    motivation_map: dict[str, float],
) -> float:
    if not manager_id:
        return 0.0
    members = [a["user_id"] for a in assignments if a["project_id"] == project_id]
    if not members:
        return 0.0
    team_avg = sum(motivation_map.get(uid, 0) for uid in members) / len(members)
    return round(abs(motivation_map.get(manager_id, team_avg) - team_avg) / 100, 2)


def _refresh_analysis(conn: Connection, assignments: list[dict], report_by_user: dict[str, str]) -> None:
    for assignment in assignments:
        user_id = assignment["user_id"]
        project_id = assignment["project_id"]
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM ai_analysis_results
                WHERE user_id = :user_id AND project_id = :project_id
                LIMIT 1
                """
            ),
            {"user_id": user_id, "project_id": project_id},
        ).scalar()
        if exists:
            continue

        notes = report_by_user.get(user_id, "")
        pattern_id = _determine_pattern(notes)
        debate_log = json.dumps(
            {
                "PM": f"allocation_rate={assignment.get('allocation_rate')}",
                "HR": _summarize_motivation(notes),
                "Risk": f"flags={_count_hits(notes, RISK_WORDS)}",
            },
            ensure_ascii=False,
        )
        conn.execute(
            text(
                """
                INSERT INTO ai_analysis_results
                  (user_id, project_id, pattern_id, debate_log, final_decision)
                VALUES
                  (:user_id, :project_id, :pattern_id, :debate_log, :final_decision)
                """
            ),
            {
                "user_id": user_id,
                "project_id": project_id,
                "pattern_id": pattern_id,
                "debate_log": debate_log,
                "final_decision": _decision_from_pattern(pattern_id),
            },
        )


def _ensure_proposals(
    conn: Connection,
    projects: list[dict],
    project_health: dict[str, dict],
) -> None:
    for project in projects:
        project_id = project["project_id"]
        existing = conn.execute(
            text(
                """
                SELECT proposal_id, plan_type
                FROM ai_strategy_proposals
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id},
        ).mappings().all()
        existing_types = {row["plan_type"] for row in existing}
        for plan_type, description, impact in _default_plans(project_id).values():
            if plan_type in existing_types:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO ai_strategy_proposals
                      (project_id, plan_type, is_recommended, description, predicted_future_impact)
                    VALUES
                      (:project_id, :plan_type, :is_recommended, :description, :predicted_future_impact)
                    """
                ),
                {
                    "project_id": project_id,
                    "plan_type": plan_type,
                    "is_recommended": False,
                    "description": description,
                    "predicted_future_impact": impact,
                },
            )

        recommended = _recommended_plan(project_health.get(project_id, {}))
        conn.execute(
            text(
                """
                UPDATE ai_strategy_proposals
                SET is_recommended = CASE WHEN plan_type = :recommended THEN TRUE ELSE FALSE END
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id, "recommended": recommended},
        )


def _ensure_actions(
    conn: Connection,
    projects: list[dict],
    project_health: dict[str, dict],
    report_by_project: dict[str, list[str]],
) -> int:
    created = 0
    for project in projects:
        project_id = project["project_id"]
        health = project_health.get(project_id, {})
        risk_level = health.get("risk_level") or "Safe"
        if risk_level == "Safe":
            continue

        existing = conn.execute(
            text(
                """
                SELECT aa.action_id
                FROM autonomous_actions aa
                JOIN ai_strategy_proposals ap ON ap.proposal_id = aa.proposal_id
                WHERE ap.project_id = :project_id
                  AND aa.status IN ('pending', 'approval_pending')
                LIMIT 1
                """
            ),
            {"project_id": project_id},
        ).scalar()
        if existing:
            continue

        project_notes = " ".join(report_by_project.get(project_id, []))
        monitor_result, plans, draft_result = _generate_ai_assets(
            conn=conn,
            project=project,
            risk_level=risk_level,
            project_notes=project_notes,
        )
        if plans:
            _upsert_llm_plans(conn, project_id, plans)

        proposal = _select_recommended_proposal(conn, project_id, plans)
        if not proposal:
            continue

        action_type = "meeting_request" if risk_level == "Critical" else "mail_draft"
        draft_content = _build_action_draft(
            project_id=project_id,
            proposal=proposal,
            monitor_result=monitor_result,
            draft_result=draft_result,
        )

        conn.execute(
            text(
                """
                INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
                VALUES (:proposal_id, :action_type, :draft_content, 'pending')
                """
            ),
            {
                "proposal_id": proposal["proposal_id"],
                "action_type": action_type,
                "draft_content": draft_content,
            },
        )
        action_id = conn.execute(
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
        ).scalar()
        if not action_id:
            continue
        approval = request_approval(
            conn,
            action_id=int(action_id),
            requested_by="watchdog",
            summary=f"{project_id} risk {risk_level}",
        )
        _merge_checkpoint_metadata(
            conn,
            approval.thread_id,
            {"mode": "watchdog", "project_id": project_id, "severity": risk_level},
        )
        created += 1
    return created


def _generate_ai_assets(
    *,
    conn: Connection,
    project: dict,
    risk_level: str,
    project_notes: str,
) -> tuple[MonitorResult | None, list[GunshiPlan], DraftingResult | None]:
    monitor_result: MonitorResult | None = None
    plans: list[GunshiPlan] = []
    drafting: DraftingResult | None = None

    notes = _truncate_text(project_notes or project.get("description") or "")
    similar_reports = []
    if notes:
        try:
            from app.domain.embeddings import search_weekly_reports

            similar_reports = search_weekly_reports(conn, notes, limit=3)
        except Exception:
            logger.exception("embedding search failed project_id=%s", project.get("project_id"))
    if notes:
        try:
            monitor_result = analyze_risk(notes)
        except Exception:
            logger.exception("monitor failed project_id=%s", project.get("project_id"))

    context = {
        "project_id": project.get("project_id"),
        "project_name": project.get("project_name"),
        "risk_level": risk_level,
        "monitor_reason": monitor_result.reason if monitor_result else "",
        "notes": notes,
        "similar_reports": similar_reports,
    }

    try:
        plans = generate_plans(context)
    except Exception:
        logger.exception("gunshi failed project_id=%s", project.get("project_id"))

    recommended = next((plan for plan in plans if plan.is_recommended), None)
    if recommended:
        try:
            draft_context = {
                "project_id": project.get("project_id"),
                "project_name": project.get("project_name"),
                "plan_type": recommended.plan_type,
                "plan_description": recommended.description,
                "monitor_reason": monitor_result.reason if monitor_result else "",
            }
            drafting = generate_drafts(draft_context)
        except Exception:
            logger.exception("drafting failed project_id=%s", project.get("project_id"))

    return monitor_result, plans, drafting


def _upsert_llm_plans(conn: Connection, project_id: str, plans: list[GunshiPlan]) -> None:
    if not plans:
        return
    recommended = next((plan.plan_type for plan in plans if plan.is_recommended), None)
    for plan in plans:
        existing = conn.execute(
            text(
                """
                SELECT proposal_id
                FROM ai_strategy_proposals
                WHERE project_id = :project_id AND plan_type = :plan_type
                LIMIT 1
                """
            ),
            {"project_id": project_id, "plan_type": plan.plan_type},
        ).scalar()
        if existing:
            conn.execute(
                text(
                    """
                    UPDATE ai_strategy_proposals
                    SET description = :description,
                        predicted_future_impact = :impact,
                        is_recommended = :is_recommended
                    WHERE proposal_id = :proposal_id
                    """
                ),
                {
                    "proposal_id": existing,
                    "description": plan.description,
                    "impact": plan.predicted_future_impact,
                    "is_recommended": plan.plan_type == recommended,
                },
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_strategy_proposals
                      (project_id, plan_type, is_recommended, description, predicted_future_impact)
                    VALUES
                      (:project_id, :plan_type, :is_recommended, :description, :impact)
                    """
                ),
                {
                    "project_id": project_id,
                    "plan_type": plan.plan_type,
                    "is_recommended": plan.plan_type == recommended,
                    "description": plan.description,
                    "impact": plan.predicted_future_impact,
                },
            )
    if recommended:
        conn.execute(
            text(
                """
                UPDATE ai_strategy_proposals
                SET is_recommended = CASE WHEN plan_type = :recommended THEN TRUE ELSE FALSE END
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id, "recommended": recommended},
        )


def _select_recommended_proposal(
    conn: Connection, project_id: str, plans: list[GunshiPlan]
) -> dict[str, Any] | None:
    preferred = next((plan.plan_type for plan in plans if plan.is_recommended), None)
    if preferred:
        proposal = conn.execute(
            text(
                """
                SELECT proposal_id, plan_type, description, predicted_future_impact
                FROM ai_strategy_proposals
                WHERE project_id = :project_id AND plan_type = :plan_type
                ORDER BY proposal_id
                LIMIT 1
                """
            ),
            {"project_id": project_id, "plan_type": preferred},
        ).mappings().first()
        if proposal:
            return proposal

    proposal = conn.execute(
        text(
            """
            SELECT proposal_id, plan_type, description, predicted_future_impact
            FROM ai_strategy_proposals
            WHERE project_id = :project_id AND is_recommended = TRUE
            ORDER BY proposal_id
            LIMIT 1
            """
        ),
        {"project_id": project_id},
    ).mappings().first()
    if proposal:
        return proposal

    return conn.execute(
        text(
            """
            SELECT proposal_id, plan_type, description, predicted_future_impact
            FROM ai_strategy_proposals
            WHERE project_id = :project_id
            ORDER BY proposal_id
            LIMIT 1
            """
        ),
        {"project_id": project_id},
    ).mappings().first()


def _build_action_draft(
    *,
    project_id: str,
    proposal: dict[str, Any],
    monitor_result: MonitorResult | None,
    draft_result: DraftingResult | None,
) -> str:
    lines = [
        f"{project_id} / {proposal['plan_type']} proposal",
        str(proposal.get("description") or ""),
        f"Impact: {proposal.get('predicted_future_impact') or ''}",
    ]
    if monitor_result:
        lines.append(
            f"Risk: {monitor_result.risk_level} ({monitor_result.urgency}) - {monitor_result.reason}"
        )
    if draft_result:
        lines.append("Email Draft:")
        lines.append(draft_result.email_draft)
        lines.append("HR Draft:")
        lines.append(draft_result.approval_doc)
        payload = json.dumps(draft_result.email_payload, ensure_ascii=True)
        lines.append(payload)
    return "\n".join([line for line in lines if line]).strip()


def _merge_checkpoint_metadata(conn: Connection, thread_id: str, extra: dict[str, Any]) -> None:
    row = conn.execute(
        text("SELECT metadata FROM langgraph_checkpoints WHERE thread_id = :thread_id"),
        {"thread_id": thread_id},
    ).mappings().first()
    if not row:
        return
    metadata = row.get("metadata")
    if isinstance(metadata, (bytes, bytearray, memoryview)):
        metadata = metadata.decode("utf-8")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.update(extra)
    conn.execute(
        text(
            """
            UPDATE langgraph_checkpoints
            SET metadata = :metadata
            WHERE thread_id = :thread_id
            """
        ),
        {"thread_id": thread_id, "metadata": json.dumps(metadata)},
    )


def _default_plans(project_id: str) -> dict[str, tuple[str, str, str]]:
    return {
        "Plan_A": ("Plan_A", "現状維持で短期安定を確保する", "短期安定"),
        "Plan_B": ("Plan_B", "人員配置を調整して成長機会を作る", "中期成長"),
        "Plan_C": ("Plan_C", "コスト最適化で負荷を抑える", "短期利益"),
    }


def _recommended_plan(health: dict) -> str:
    score = float(health.get("health_score") or 0)
    if score <= 60:
        return "Plan_B"
    return "Plan_A"


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


def _count_hits(text_value: str, words: tuple[str, ...]) -> int:
    return sum(text_value.count(word) for word in words)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _truncate_text(text_value: str, limit: int = 1500) -> str:
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit] + "..."
