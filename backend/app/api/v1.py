from __future__ import annotations

import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import AuthUser, get_current_user, issue_token
from app.db import get_db
from app.db.repository import (
    fetch_member_detail,
    fetch_members,
    fetch_members_by_ids,
    fetch_project,
    fetch_projects,
)
from app.domain.patterns import detect_pattern
from app.domain.scoring import score

router = APIRouter(prefix="/v1")

DEV_LOGIN_PASSWORD = os.getenv("DEV_LOGIN_PASSWORD", "saihai")


class LoginRequest(BaseModel):
    userId: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    name: str
    role: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    budget: int
    requiredSkills: list[str] = Field(default_factory=list)
    status: str | None = None
    difficulty: str | None = None
    description: str | None = None


class MemberAnalysis(BaseModel):
    patternId: str
    patternName: str | None = None
    pmRiskScore: int | None = None
    hrRiskScore: int | None = None
    riskRiskScore: int | None = None
    finalDecision: str | None = None


class MemberResponse(BaseModel):
    id: str
    name: str
    cost: int
    availability: int
    skills: list[str]
    notes: str | None = None
    role: str | None = None
    skillLevel: int | None = None
    careerAspiration: str | None = None
    analysis: MemberAnalysis | None = None


class MemberDetailResponse(MemberResponse):
    assignments: list[dict] = Field(default_factory=list)


class SimulationEvaluateRequest(BaseModel):
    projectId: str = Field(min_length=1)
    memberIds: list[str] = Field(default_factory=list)


class RequirementResult(BaseModel):
    name: str
    fulfilled: bool


class SimulationMetrics(BaseModel):
    budgetUsed: int
    budgetPct: int
    skillFitPct: int
    careerFitPct: int
    riskPct: int


class SimulationProjectSummary(BaseModel):
    id: str
    name: str
    budget: int


class SimulationMemberSummary(BaseModel):
    id: str
    name: str
    cost: int


class SimulationTimelineEntry(BaseModel):
    t: str
    level: Literal["good", "ok", "bad"]
    text: str


class SimulationMeetingEntry(BaseModel):
    agent_id: Literal["PM", "HR", "RISK", "GUNSHI"]
    decision: Literal["APPROVE", "CONDITIONAL_APPROVE", "REJECT"]
    risk_score: int
    risk_reason: str
    message: str


class SimulationAgentVote(BaseModel):
    vote: Literal["ok", "ng"]
    note: str


class SimulationAgentGunshi(BaseModel):
    recommend: Literal["A", "B", "C"]
    note: str


class SimulationAgents(BaseModel):
    pm: SimulationAgentVote
    hr: SimulationAgentVote
    risk: SimulationAgentVote
    gunshi: SimulationAgentGunshi


class SimulationEvaluationResponse(BaseModel):
    id: str
    project: SimulationProjectSummary
    team: list[SimulationMemberSummary]
    metrics: SimulationMetrics
    pattern: str
    timeline: list[SimulationTimelineEntry]
    meetingLog: list[SimulationMeetingEntry]
    agents: SimulationAgents
    requirementResult: list[RequirementResult]


class SimulationPlan(BaseModel):
    id: str
    simulationId: str
    planType: str
    summary: str
    prosCons: dict[str, list[str]]
    score: int
    recommended: bool


class DashboardKpi(BaseModel):
    label: str
    value: int
    suffix: str
    delta: str
    color: str
    deltaColor: str


class DashboardAlert(BaseModel):
    id: str
    title: str
    subtitle: str
    risk: int
    severity: str
    status: str
    projectId: str | None = None


class DashboardProposal(BaseModel):
    id: int
    projectId: str
    planType: str
    description: str
    recommendationScore: int
    isRecommended: bool


class DashboardPendingAction(BaseModel):
    id: int
    proposalId: int
    actionType: str
    title: str
    status: str


class DashboardTimelineEntry(BaseModel):
    t: str
    text: str
    dot: str


class DashboardInitialResponse(BaseModel):
    kpis: list[DashboardKpi]
    alerts: list[DashboardAlert]
    members: list[MemberResponse]
    proposals: list[DashboardProposal]
    pendingActions: list[DashboardPendingAction]
    watchdog: list[DashboardTimelineEntry]
    checkpointWaiting: bool


_simulations: dict[str, dict] = {}
_plans: dict[str, dict] = {}


@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, conn: Connection = Depends(get_db)) -> LoginResponse:
    if req.password != DEV_LOGIN_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid credentials")
    user = conn.execute(
        text("SELECT user_id, name, role FROM users WHERE user_id = :user_id"),
        {"user_id": req.userId},
    ).mappings().first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_token(user)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def get_me(user: AuthUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.user_id, name=user.name, role=user.role)


@router.get("/projects", response_model=list[ProjectResponse], dependencies=[Depends(get_current_user)])
def list_projects(conn: Connection = Depends(get_db)) -> list[dict]:
    return fetch_projects(conn)


@router.get("/members", response_model=list[MemberResponse], dependencies=[Depends(get_current_user)])
def list_members(conn: Connection = Depends(get_db)) -> list[dict]:
    members = fetch_members(conn)
    analysis = _load_latest_analysis(conn)
    for member in members:
        detail = analysis.get(member["id"])
        if detail:
            member["analysis"] = detail
    return members


@router.get(
    "/members/{member_id}",
    response_model=MemberDetailResponse,
    dependencies=[Depends(get_current_user)],
)
def get_member(member_id: str, conn: Connection = Depends(get_db)) -> dict:
    member = fetch_member_detail(conn, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="member not found")
    detail = _load_latest_analysis(conn).get(member_id)
    if detail:
        member["analysis"] = detail
    member["assignments"] = _load_assignments(conn, member_id)
    return member


@router.get(
    "/dashboard/initial",
    response_model=DashboardInitialResponse,
    dependencies=[Depends(get_current_user)],
)
def dashboard_initial(conn: Connection = Depends(get_db)) -> dict:
    members = fetch_members(conn)
    analysis_by_user = _load_latest_analysis(conn)
    for member in members:
        if member["id"] in analysis_by_user:
            member["analysis"] = analysis_by_user[member["id"]]

    projects = {p["id"]: p for p in fetch_projects(conn)}
    snapshots = conn.execute(
        text(
            """
            SELECT snapshot_id, project_id, budget_usage_rate, delay_risk_rate, overall_health
            FROM project_health_snapshots
            ORDER BY snapshot_id
            """
        )
    ).mappings().all()

    alerts = []
    for row in snapshots:
        risk = max(int(row["budget_usage_rate"] or 0), int(row["delay_risk_rate"] or 0))
        if risk < 70 and row.get("overall_health") == "safe":
            continue
        project = projects.get(row["project_id"], {})
        alerts.append(
            {
                "id": f"alert-{row['project_id']}-{row['snapshot_id']}",
                "title": f"{project.get('name', 'Project')} のリスクが上昇",
                "subtitle": f"Budget {row['budget_usage_rate']}% / Delay {row['delay_risk_rate']}%",
                "risk": risk,
                "severity": "high" if risk >= 85 else "medium",
                "status": "open",
                "projectId": row["project_id"],
            }
        )

    proposals = conn.execute(
        text(
            """
            SELECT proposal_id, project_id, plan_type, description, recommendation_score, is_recommended
            FROM ai_strategy_proposals
            ORDER BY proposal_id
            """
        )
    ).mappings().all()
    proposal_payload = [
        {
            "id": row["proposal_id"],
            "projectId": row["project_id"],
            "planType": row["plan_type"],
            "description": row["description"],
            "recommendationScore": row["recommendation_score"],
            "isRecommended": bool(row["is_recommended"]),
        }
        for row in proposals
    ]

    actions = conn.execute(
        text(
            """
            SELECT action_id, proposal_id, action_type, draft_content, status
            FROM autonomous_actions
            WHERE status IN ('pending', 'approval_pending')
            ORDER BY action_id
            """
        )
    ).mappings().all()
    pending_actions = [
        {
            "id": row["action_id"],
            "proposalId": row["proposal_id"],
            "actionType": row["action_type"],
            "title": row["draft_content"],
            "status": row["status"],
        }
        for row in actions
    ]

    kpis = _build_kpis(members, analysis_by_user)

    checkpoint_waiting = bool(
        conn.execute(text("SELECT 1 FROM langgraph_checkpoints LIMIT 1")).scalar()
    )

    watchdog_alerts = conn.execute(
        text(
            """
            SELECT summary, severity, created_at
            FROM watchdog_alerts
            ORDER BY created_at DESC
            LIMIT 3
            """
        )
    ).mappings().all()

    watchdog = _build_watchdog_timeline(len(members), len(pending_actions), watchdog_alerts)

    return {
        "kpis": kpis,
        "alerts": alerts,
        "members": members,
        "proposals": proposal_payload,
        "pendingActions": pending_actions,
        "watchdog": watchdog,
        "checkpointWaiting": checkpoint_waiting,
    }


@router.post(
    "/simulations/evaluate",
    response_model=SimulationEvaluationResponse,
    dependencies=[Depends(get_current_user)],
)
def evaluate(req: SimulationEvaluateRequest, conn: Connection = Depends(get_db)) -> dict:
    project = fetch_project(conn, req.projectId)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    team = fetch_members_by_ids(conn, req.memberIds)
    if len(team) != len(set(req.memberIds)):
        raise HTTPException(status_code=404, detail="member not found")

    metrics = score(project, team)
    notes = " ".join(str(m.get("notes") or "") for m in team)

    votes = {
        "pm": _vote_pm(metrics),
        "hr": _vote_hr(notes, metrics),
        "risk": _vote_risk(metrics),
    }

    pattern = detect_pattern(project, team, metrics, votes)

    pm_decision, pm_risk, pm_reason, pm_msg = _decision_pm(metrics)
    hr_decision, hr_risk, hr_reason, hr_msg = _decision_hr(notes, metrics)
    risk_decision, risk_risk, risk_reason, risk_msg = _decision_risk(metrics, pattern)

    if votes["risk"] == "ng":
        recommend = "B"
        gunshi_note = "リスクを分散しつつ火消し要員を薄く入れる"
    elif votes["pm"] == "ng" and votes["hr"] == "ok":
        recommend = "B"
        gunshi_note = "若手抜擢+レビュー体制で未来投資"
    elif metrics["budgetPct"] > 100:
        recommend = "C"
        gunshi_note = "予算を守る前提でスコープ/稼働を調整"
    else:
        recommend = "A"
        gunshi_note = "現状維持で短期の確実性を優先"

    risk_level = "bad" if metrics["riskPct"] >= 75 else ("ok" if metrics["riskPct"] >= 50 else "good")
    timeline = [
        {"t": "1ヶ月後", "level": risk_level, "text": f"パターン: {pattern} の兆候が顕在化"},
        {"t": "3ヶ月後", "level": risk_level, "text": "手当がない場合、遅延/疲労が増加"},
        {"t": "6ヶ月後", "level": "ok" if recommend == "B" else risk_level, "text": "体制次第で安定化"},
    ]

    meeting_log = [
        {
            "agent_id": "PM",
            "decision": pm_decision,
            "risk_score": pm_risk,
            "risk_reason": pm_reason,
            "message": pm_msg,
        },
        {
            "agent_id": "HR",
            "decision": hr_decision,
            "risk_score": hr_risk,
            "risk_reason": hr_reason,
            "message": hr_msg,
        },
        {
            "agent_id": "RISK",
            "decision": risk_decision,
            "risk_score": risk_risk,
            "risk_reason": risk_reason,
            "message": risk_msg,
        },
        {
            "agent_id": "GUNSHI",
            "decision": "APPROVE" if recommend in ("A", "B") else "CONDITIONAL_APPROVE",
            "risk_score": max(pm_risk, hr_risk, risk_risk),
            "risk_reason": gunshi_note,
            "message": f"結論: Plan {recommend}（{gunshi_note}）",
        },
    ]

    requirement_result = [
        {
            "name": skill,
            "fulfilled": skill in {s for m in team for s in (m.get("skills") or [])},
        }
        for skill in project.get("requiredSkills", [])
    ]

    sim_id = f"sim-{uuid4().hex[:8]}"
    evaluation = {
        "id": sim_id,
        "project": {"id": project["id"], "name": project["name"], "budget": project["budget"]},
        "team": [{"id": m["id"], "name": m["name"], "cost": m["cost"]} for m in team],
        "metrics": metrics,
        "pattern": pattern,
        "timeline": timeline,
        "meetingLog": meeting_log,
        "agents": {
            "pm": {"vote": votes["pm"], "note": "スキル/予算の観点"},
            "hr": {"vote": votes["hr"], "note": "疲労/成長/配置の観点"},
            "risk": {"vote": votes["risk"], "note": "炎上/離職/潜在リスクの観点"},
            "gunshi": {"recommend": recommend, "note": gunshi_note},
        },
        "requirementResult": requirement_result,
    }

    _simulations[sim_id] = {"evaluation": evaluation, "riskScore": metrics["riskPct"]}
    return evaluation


@router.post(
    "/simulations/{simulation_id}/plans/generate",
    response_model=list[SimulationPlan],
    dependencies=[Depends(get_current_user)],
)
def generate_plans(simulation_id: str) -> list[dict]:
    simulation = _simulations.get(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="simulation not found")

    risk_score = int(simulation.get("riskScore", 0))
    recommended = "A" if risk_score <= 50 else "B"

    plans = []
    for pid, title, pros, cons in [
        ("A", "堅実維持", ["短期安定"], ["疲労蓄積"]),
        ("B", "未来投資", ["育成と安定の両立"], ["調整コスト"]),
        ("C", "コスト重視", ["利益率最大"], ["品質リスク"]),
    ]:
        plan_id = f"plan-{simulation_id}-{pid}"
        plan = {
            "id": plan_id,
            "simulationId": simulation_id,
            "planType": pid,
            "summary": title,
            "prosCons": {"pros": pros, "cons": cons},
            "score": max(0, 100 - risk_score - (10 if pid == "C" else 0)),
            "recommended": pid == recommended,
        }
        _plans[plan_id] = plan
        plans.append(plan)
    return plans


def _vote_pm(metrics: dict[str, int]) -> Literal["ok", "ng"]:
    return "ok" if metrics["budgetPct"] <= 100 and metrics["skillFitPct"] >= 70 else "ng"


def _vote_hr(team_notes: str, metrics: dict[str, int]) -> Literal["ok", "ng"]:
    if any(word in team_notes for word in ("疲労", "飽き", "燃え尽き")):
        return "ng"
    return "ok" if metrics["careerFitPct"] >= 45 else "ng"


def _vote_risk(metrics: dict[str, int]) -> Literal["ok", "ng"]:
    return "ok" if metrics["riskPct"] <= 60 else "ng"


def _decision_pm(metrics: dict[str, int]) -> tuple[str, int, str, str]:
    if metrics["budgetPct"] > 110:
        return (
            "CONDITIONAL_APPROVE",
            min(100, metrics["budgetPct"]),
            "予算上限超過の可能性（スコープ/単価調整が必要）",
            f"予算消化率 {metrics['budgetPct']}% です。コスト効率の観点で条件付き賛成です。",
        )
    if metrics["skillFitPct"] < 70:
        return (
            "CONDITIONAL_APPROVE",
            65,
            "必要スキル不足（レビュー/補強が必要）",
            f"スキル適合率 {metrics['skillFitPct']}% です。補強前提で条件付き賛成です。",
        )
    return (
        "APPROVE",
        10,
        "予算/スキルが許容範囲",
        "予算とスキル適合性の観点で問題ありません。",
    )


def _decision_hr(team_notes: str, metrics: dict[str, int]) -> tuple[str, int, str, str]:
    if any(word in team_notes for word in ("疲労", "飽きた", "燃え尽き", "限界")):
        return (
            "REJECT",
            85,
            "燃え尽き兆候（負荷軽減が必要）",
            "週報/面談ログに燃え尽き兆候があります。このままの負荷は危険です。",
        )
    if metrics["careerFitPct"] < 45:
        return (
            "CONDITIONAL_APPROVE",
            55,
            "成長機会の設計が弱い（介入で改善可能）",
            "成長機会が不足しやすい配置です。学習/レビュー機会の設計が必要です。",
        )
    return (
        "APPROVE",
        15,
        "成長/エンゲージメントが許容",
        "成長機会とエンゲージメントの観点で問題ありません。",
    )


def _decision_risk(metrics: dict[str, int], pattern: str) -> tuple[str, int, str, str]:
    if metrics["riskPct"] > 60:
        return (
            "REJECT",
            metrics["riskPct"],
            "炎上/離職リスクが高い（要介入）",
            f"RISK={metrics['riskPct']}%。パターンは {pattern}。放置すると損害が拡大します。",
        )
    return (
        "APPROVE",
        metrics["riskPct"],
        "統計上の重大警告なし",
        f"RISK={metrics['riskPct']}%。現時点で致命的な警告はありません。",
    )


def _load_latest_analysis(conn: Connection) -> dict[str, dict]:
    patterns = {
        row["pattern_id"]: row["name_ja"]
        for row in conn.execute(text("SELECT pattern_id, name_ja FROM assignment_patterns")).mappings()
    }
    rows = conn.execute(
        text(
            """
            SELECT analysis_id, user_id, pattern_id, pm_risk_score, hr_risk_score, risk_risk_score, final_decision
            FROM ai_analysis_results
            ORDER BY analysis_id
            """
        )
    ).mappings().all()
    latest: dict[str, dict] = {}
    for row in rows:
        latest[row["user_id"]] = {
            "patternId": row["pattern_id"],
            "patternName": patterns.get(row["pattern_id"]),
            "pmRiskScore": row["pm_risk_score"],
            "hrRiskScore": row["hr_risk_score"],
            "riskRiskScore": row["risk_risk_score"],
            "finalDecision": row["final_decision"],
        }
    return latest


def _build_kpis(members: list[dict], analysis_by_user: dict[str, dict]) -> list[dict]:
    risk_scores = [
        detail.get("riskRiskScore", 0) or 0 for detail in analysis_by_user.values() if detail
    ]
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
    high_risk = sum(1 for score in risk_scores if score >= 70)
    engagement = max(0, round(100 - avg_risk * 0.6))
    career_fit = max(0, round(100 - avg_risk * 0.4))
    margin = max(0, round(90 + (len(members) * 2) - avg_risk * 0.2))
    return [
        {
            "label": "エンゲージメント",
            "value": engagement,
            "suffix": "%",
            "color": "#10b981",
            "delta": "▲ 2.4pt",
            "deltaColor": "#10b981",
        },
        {
            "label": "キャリア適合率",
            "value": career_fit,
            "suffix": "%",
            "color": "#d946ef",
            "delta": "介入で\"成長機会\"を再設計",
            "deltaColor": "#94a3b8",
        },
        {
            "label": "離職リスク (High)",
            "value": high_risk,
            "suffix": "名",
            "color": "#f43f5e",
            "delta": "※要対応" if high_risk else "平常運転",
            "deltaColor": "#f43f5e" if high_risk else "#10b981",
        },
        {
            "label": "予測粗利益率",
            "value": margin,
            "suffix": "%",
            "color": "#f59e0b",
            "delta": "自動根回しで調整コスト削減",
            "deltaColor": "#94a3b8",
        },
    ]


def _build_watchdog_timeline(
    member_count: int,
    pending_count: int,
    alerts: list[dict] | None = None,
) -> list[dict]:
    timeline = [
        {
            "t": "09:00",
            "text": f"全社解析完了（{member_count}名の週報/面談を更新）",
            "dot": "#6366f1",
        },
        {
            "t": "10:15",
            "text": f"承認待ちタスク {pending_count} 件",
            "dot": "#06b6d4",
        },
    ]

    if alerts:
        for alert in alerts:
            severity = alert.get("severity") or "low"
            dot = "#f43f5e" if severity == "high" else ("#f59e0b" if severity == "medium" else "#10b981")
            timeline.append(
                {
                    "t": (alert.get("created_at") or "auto").strftime("%H:%M")
                    if hasattr(alert.get("created_at"), "strftime")
                    else "auto",
                    "text": alert.get("summary") or "Watchdog alert",
                    "dot": dot,
                }
            )
        return timeline

    timeline.append(
        {
            "t": "11:00",
            "text": "新規案件マッチング中…",
            "dot": "#10b981",
        }
    )
    return timeline


def _load_assignments(conn: Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT assignment_id, project_id, role_in_pj, start_date, end_date, remarks
            FROM assignments
            WHERE user_id = :user_id
            ORDER BY assignment_id
            """
        ),
        {"user_id": user_id},
    ).mappings()
    assignments = []
    for row in rows:
        assignments.append(
            {
                "id": row["assignment_id"],
                "projectId": row["project_id"],
                "role": row["role_in_pj"],
                "startDate": row["start_date"].isoformat() if row["start_date"] else None,
                "endDate": row["end_date"].isoformat() if row["end_date"] else None,
                "remarks": row["remarks"],
            }
        )
    return assignments
