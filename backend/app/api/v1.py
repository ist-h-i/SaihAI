from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import AuthUser, get_current_user, get_current_user_or_token, issue_token
from app.db import get_db
from app.db.repository import (
    fetch_member_detail,
    fetch_members,
    fetch_members_by_ids,
    fetch_project,
    fetch_project_team,
    fetch_projects,
)
from app.domain.patterns import detect_pattern
from app.domain.scoring import score
from app.domain.external_actions import ACTION_TYPE_CALENDAR, ACTION_TYPE_EMAIL, ACTION_TYPE_HR
from app.domain.input_sources import (
    SOURCE_ATTENDANCE,
    SOURCE_SLACK_LOGS,
    SOURCE_WEEKLY_REPORTS,
    fetch_ingestion_runs,
    ingest_attendance,
    ingest_slack_logs,
    ingest_weekly_reports,
)
from app.domain.hitl import fetch_history
from app.integrations.bedrock import BedrockError, is_bedrock_configured
from app.agents.plan_chat import update_plan_via_chat
from app.agents.simulator_planner import build_simulation_plan_logs, generate_simulation_plans

router = APIRouter(prefix="/v1")

DEV_LOGIN_PASSWORD = os.getenv("DEV_LOGIN_PASSWORD", "saihai")
auth_logger = logging.getLogger("saihai.auth")
logger = logging.getLogger("saihai.api.v1")


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


class ProjectAssignment(BaseModel):
    role: str | None = None
    allocationRate: float | None = None


class ProjectTeamMember(MemberResponse):
    assignment: ProjectAssignment | None = None


class ProjectTeamResponse(BaseModel):
    projectId: str
    members: list[ProjectTeamMember]


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


class PlanChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    allowMock: bool = False


class PlanChatResponse(BaseModel):
    plan: SimulationPlan
    message: str


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
    category: str | None = None
    focusMemberId: str | None = None


class DashboardProposal(BaseModel):
    id: int
    projectId: str
    projectName: str | None = None
    planType: str
    description: str
    predictedFutureImpact: str | None = None
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


class ExternalEmailActionRequest(BaseModel):
    to: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    proposalId: int | None = None


class ExternalCalendarActionRequest(BaseModel):
    ownerEmail: str | None = None
    attendee: str = Field(min_length=1)
    title: str = Field(min_length=1)
    startAt: str = Field(min_length=1)
    endAt: str = Field(min_length=1)
    timezone: str | None = None
    description: str | None = None
    meetingUrl: str | None = None
    proposalId: int | None = None


class ExternalHrActionRequest(BaseModel):
    employeeId: str = Field(min_length=1)
    requestType: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    proposalId: int | None = None


class ActionCreateResponse(BaseModel):
    actionId: int
    status: str
    actionType: str


class ExternalActionRunResponse(BaseModel):
    runId: str
    jobId: str
    actionId: int
    actionType: str
    provider: str
    status: str
    executedAt: str | None = None
    error: str | None = None


class InputIngestionRunResponse(BaseModel):
    runId: str
    sourceType: str
    status: str
    itemsInserted: int
    startedAt: str
    finishedAt: str
    error: str | None = None


class HistoryEventResponse(BaseModel):
    event_type: str
    actor: str | None = None
    correlation_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class HistoryEntryResponse(BaseModel):
    thread_id: str
    action_id: int
    status: str | None = None
    summary: str | None = None
    project_id: str | None = None
    severity: str | None = None
    updated_at: str | None = None
    events: list[HistoryEventResponse] = Field(default_factory=list)


_simulations: dict[str, dict] = {}
_plans: dict[str, dict] = {}
_plan_chats: dict[str, list[dict[str, str]]] = {}


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
    auth_logger.info("login success user_id=%s", req.userId)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def get_me(user: AuthUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.user_id, name=user.name, role=user.role)


@router.get("/projects", response_model=list[ProjectResponse], dependencies=[Depends(get_current_user)])
def list_projects(conn: Connection = Depends(get_db)) -> list[dict]:
    return fetch_projects(conn)


@router.get(
    "/projects/{project_id}/team",
    response_model=ProjectTeamResponse,
    dependencies=[Depends(get_current_user)],
)
def get_project_team(project_id: str, conn: Connection = Depends(get_db)) -> dict:
    project = fetch_project(conn, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    members = fetch_project_team(conn, project_id)
    analysis = _load_latest_analysis(conn)
    for member in members:
        detail = analysis.get(member["id"])
        if detail:
            member["analysis"] = detail
    return {"projectId": project_id, "members": members}


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
    project_members = _load_project_members(conn)
    snapshots = conn.execute(
        text(
            """
            SELECT snapshot_id, project_id, health_score, risk_level, variance_score, manager_gap_score, calculated_at
            FROM project_health_snapshots
            ORDER BY snapshot_id
            """
        )
    ).mappings().all()

    alerts = []
    for row in snapshots:
        health_score = int(row.get("health_score") or 0)
        risk_level = row.get("risk_level") or "Safe"
        project = projects.get(row["project_id"], {})
        project_id = row["project_id"]
        if risk_level != "Safe":
            severity = "high" if risk_level == "Critical" or health_score <= 50 else "medium"
            subtitle = f"Health {health_score}"
            if row.get("variance_score") is not None:
                subtitle = f"{subtitle} / variance {row['variance_score']}"
            alerts.append(
                {
                    "id": f"alert-{project_id}-{row['snapshot_id']}-burnout",
                    "title": f"{project.get('name', 'Project')} の炎上リスクが上昇",
                    "subtitle": subtitle,
                    "risk": health_score,
                    "severity": severity,
                    "status": "open",
                    "projectId": project_id,
                    "category": "burnout",
                    "focusMemberId": _select_focus_member(
                        project_members, analysis_by_user, project_id, focus_on="risk"
                    ),
                }
            )

        mismatch_score = None
        if row.get("manager_gap_score") is not None and row["manager_gap_score"] >= 0.35:
            mismatch_score = float(row["manager_gap_score"])
        elif row.get("variance_score") is not None and row["variance_score"] >= 0.55:
            mismatch_score = float(row["variance_score"])
        if mismatch_score is not None:
            severity = "high" if mismatch_score >= 0.6 else "medium"
            subtitle = f"gap {mismatch_score:.2f}"
            alerts.append(
                {
                    "id": f"alert-{project_id}-{row['snapshot_id']}-career",
                    "title": f"{project.get('name', 'Project')} のキャリアミスマッチ",
                    "subtitle": subtitle,
                    "risk": int(round(mismatch_score * 100)),
                    "severity": severity,
                    "status": "open",
                    "projectId": project_id,
                    "category": "career_mismatch",
                    "focusMemberId": _select_focus_member(
                        project_members, analysis_by_user, project_id, focus_on="career"
                    ),
                }
            )

    proposals = conn.execute(
        text(
            """
            SELECT proposal_id, project_id, plan_type, description, predicted_future_impact, is_recommended
            FROM ai_strategy_proposals
            ORDER BY proposal_id
            """
        )
    ).mappings().all()
    proposal_payload = [
        {
            "id": row["proposal_id"],
            "projectId": row["project_id"],
            "projectName": projects.get(row["project_id"], {}).get("name") or row["project_id"],
            "planType": row["plan_type"],
            "description": row["description"],
            "predictedFutureImpact": row.get("predicted_future_impact"),
            "recommendationScore": _proposal_score(row["plan_type"], row.get("is_recommended")),
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

    watchdog = _build_watchdog_timeline(len(members), len(pending_actions), alerts)

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

    _simulations[sim_id] = {
        "evaluation": evaluation,
        "riskScore": metrics["riskPct"],
        "project": project,
        "team": team,
    }
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

    try:
        plans, _logs = _build_plans_with_bedrock(simulation_id, simulation)
        return plans
    except BedrockError:
        logger.exception("Bedrock plan generation failed, falling back simulation_id=%s", simulation_id)

    risk_score = int(simulation.get("riskScore", 0))
    return _build_plans_fallback(simulation_id, risk_score)


@router.post(
    "/simulations/{simulation_id}/plans/{plan_type}/chat",
    response_model=PlanChatResponse,
    dependencies=[Depends(get_current_user)],
)
def chat_plan(simulation_id: str, plan_type: str, req: PlanChatRequest) -> PlanChatResponse:
    simulation = _simulations.get(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="simulation not found")

    normalized = (plan_type or "").strip().upper()
    if normalized not in {"A", "B", "C"}:
        raise HTTPException(status_code=400, detail="invalid plan type")

    plan_id = f"plan-{simulation_id}-{normalized}"
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")

    message = req.message.strip()
    history = _plan_chats.setdefault(plan_id, [])
    history.append({"role": "user", "text": message})
    if len(history) > 40:
        history[:] = history[-40:]

    if not is_bedrock_configured():
        if req.allowMock:
            assistant_message = "Bedrock が未設定のため、モック応答です。（プランは変更していません）"
            history.append({"role": "assistant", "text": assistant_message})
            if len(history) > 40:
                history[:] = history[-40:]
            return PlanChatResponse(plan=plan, message=assistant_message)
        raise HTTPException(status_code=400, detail="Bedrock is not configured.")

    evaluation = simulation.get("evaluation") or {}
    context = {
        "simulation_id": simulation_id,
        "project": simulation.get("project") or evaluation.get("project") or {},
        "team": simulation.get("team") or evaluation.get("team") or [],
        "metrics": evaluation.get("metrics") or {},
        "pattern": evaluation.get("pattern") or "",
        "requirement_result": evaluation.get("requirementResult") or [],
    }

    try:
        update = update_plan_via_chat(
            plan_type=normalized,
            plan=plan,
            simulation_context=context,
            history=history[:-1],
            user_message=message,
        )
        plan["summary"] = update.summary
        pros_cons = plan.get("prosCons")
        if not isinstance(pros_cons, dict):
            pros_cons = {}
            plan["prosCons"] = pros_cons
        pros_cons["pros"] = update.pros
        pros_cons["cons"] = update.cons
        plan["score"] = update.score
        _plans[plan_id] = plan
        assistant_message = update.assistant_message
    except BedrockError:
        logger.exception("Bedrock plan chat failed simulation_id=%s plan_type=%s", simulation_id, normalized)
        assistant_message = "AI サービスへの接続に失敗しました。もう一度お試しください。（プランは変更していません）"

    history.append({"role": "assistant", "text": assistant_message})
    if len(history) > 40:
        history[:] = history[-40:]

    return PlanChatResponse(plan=plan, message=assistant_message)


@router.get("/simulations/{simulation_id}/plans/stream")
async def stream_plans(
    simulation_id: str,
    user: AuthUser = Depends(get_current_user_or_token),
) -> StreamingResponse:
    simulation = _simulations.get(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="simulation not found")

    risk_score = int(simulation.get("riskScore", 0))
    evaluation = simulation.get("evaluation") or {}
    logs = _build_stream_logs(evaluation)
    steps = [
        {"phase": "prepare", "message": "collecting signals", "progress": 10},
        {"phase": "debate", "message": "running agent debate", "progress": 45},
        {"phase": "draft", "message": "drafting intervention plans", "progress": 75},
        {"phase": "score", "message": "scoring options", "progress": 90},
    ]

    async def event_stream():
        yield _sse_event("progress", {"phase": "queued", "message": "job queued", "progress": 5})
        await asyncio.sleep(0.2)
        for step in steps:
            yield _sse_event("progress", step)
            await asyncio.sleep(0.25)
            if step["phase"] == "debate":
                for entry in logs:
                    yield _sse_event("log", entry)
                    await asyncio.sleep(0.2)

        try:
            plans, ai_logs = await asyncio.to_thread(_build_plans_with_bedrock, simulation_id, simulation)
            for entry in ai_logs:
                yield _sse_event("log", entry)
                await asyncio.sleep(0.12)
        except BedrockError:
            logger.exception(
                "Bedrock plan generation failed during stream, falling back simulation_id=%s", simulation_id
            )
            yield _sse_event(
                "log",
                {
                    "agent": "SYSTEM",
                    "message": "Bedrock 呼び出しに失敗したため、ローカル推定のプランにフォールバックしました。",
                    "tone": "gunshi",
                },
            )
            plans = _build_plans_fallback(simulation_id, risk_score)
        yield _sse_event("complete", {"plans": plans})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), headers=headers, media_type="text/event-stream")


@router.post(
    "/actions/email",
    response_model=ActionCreateResponse,
    dependencies=[Depends(get_current_user)],
)
def create_email_action(
    req: ExternalEmailActionRequest,
    conn: Connection = Depends(get_db),
) -> ActionCreateResponse:
    payload = {"to": req.to, "subject": req.subject, "body": req.body}
    draft_content = f"Email to {req.to}: {req.subject}\n\n{json.dumps(payload, ensure_ascii=False)}"
    conn.execute(
        text(
            """
            INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
            VALUES (:proposal_id, :action_type, :draft_content, 'pending')
            """
        ),
        {
            "proposal_id": req.proposalId,
            "action_type": ACTION_TYPE_EMAIL,
            "draft_content": draft_content,
        },
    )
    action_id = conn.execute(
        text(
            """
            SELECT action_id
            FROM autonomous_actions
            ORDER BY action_id DESC
            LIMIT 1
            """
        )
    ).scalar()
    return ActionCreateResponse(
        actionId=int(action_id),
        status="pending",
        actionType=ACTION_TYPE_EMAIL,
    )


@router.post(
    "/actions/calendar",
    response_model=ActionCreateResponse,
)
def create_calendar_action(
    req: ExternalCalendarActionRequest,
    user: AuthUser = Depends(get_current_user),
    conn: Connection = Depends(get_db),
) -> ActionCreateResponse:
    payload = {
        "owner_email": req.ownerEmail,
        "owner_user_id": user.user_id,
        "attendee": req.attendee,
        "title": req.title,
        "start_at": req.startAt,
        "end_at": req.endAt,
        "timezone": req.timezone,
        "description": req.description,
        "meeting_url": req.meetingUrl,
    }
    draft_content = (
        f"Calendar booking: {req.title} ({req.startAt} - {req.endAt})\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    conn.execute(
        text(
            """
            INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
            VALUES (:proposal_id, :action_type, :draft_content, 'pending')
            """
        ),
        {
            "proposal_id": req.proposalId,
            "action_type": ACTION_TYPE_CALENDAR,
            "draft_content": draft_content,
        },
    )
    action_id = conn.execute(
        text(
            """
            SELECT action_id
            FROM autonomous_actions
            ORDER BY action_id DESC
            LIMIT 1
            """
        )
    ).scalar()
    return ActionCreateResponse(
        actionId=int(action_id),
        status="pending",
        actionType=ACTION_TYPE_CALENDAR,
    )


@router.post(
    "/actions/hr",
    response_model=ActionCreateResponse,
    dependencies=[Depends(get_current_user)],
)
def create_hr_action(
    req: ExternalHrActionRequest,
    conn: Connection = Depends(get_db),
) -> ActionCreateResponse:
    payload = {
        "employee_id": req.employeeId,
        "request_type": req.requestType,
        "summary": req.summary,
    }
    draft_content = f"HR request for {req.employeeId}: {req.summary}\n\n{json.dumps({'hr_request': payload})}"
    conn.execute(
        text(
            """
            INSERT INTO autonomous_actions (proposal_id, action_type, draft_content, status)
            VALUES (:proposal_id, :action_type, :draft_content, 'pending')
            """
        ),
        {
            "proposal_id": req.proposalId,
            "action_type": ACTION_TYPE_HR,
            "draft_content": draft_content,
        },
    )
    action_id = conn.execute(
        text(
            """
            SELECT action_id
            FROM autonomous_actions
            ORDER BY action_id DESC
            LIMIT 1
            """
        )
    ).scalar()
    return ActionCreateResponse(
        actionId=int(action_id),
        status="pending",
        actionType=ACTION_TYPE_HR,
    )


@router.get(
    "/external-actions/runs",
    response_model=list[ExternalActionRunResponse],
    dependencies=[Depends(get_current_user)],
)
def list_external_action_runs(conn: Connection = Depends(get_db)) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT run_id, action_type, status, job_id, action_id, provider, error, executed_at
            FROM external_action_runs
            ORDER BY run_id DESC
            LIMIT 50
            """
        )
    ).mappings().all()
    results: list[dict] = []
    for row in rows:
        executed_at = row.get("executed_at")
        if executed_at and hasattr(executed_at, "isoformat"):
            executed_at = executed_at.isoformat()
        results.append(
            {
                "runId": str(row.get("run_id")),
                "jobId": str(row.get("job_id") or ""),
                "actionId": int(row.get("action_id") or 0),
                "actionType": row.get("action_type"),
                "provider": row.get("provider"),
                "status": row.get("status"),
                "executedAt": executed_at,
                "error": row.get("error"),
            }
        )
    return results


@router.post(
    "/input-sources/weekly-reports/ingest",
    response_model=InputIngestionRunResponse,
    dependencies=[Depends(get_current_user)],
)
def ingest_weekly_reports_api(conn: Connection = Depends(get_db)) -> dict:
    result = ingest_weekly_reports(conn)
    return _ingestion_response(result)


@router.get(
    "/input-sources/weekly-reports/runs",
    response_model=list[InputIngestionRunResponse],
    dependencies=[Depends(get_current_user)],
)
def list_weekly_report_ingestion_runs(conn: Connection = Depends(get_db)) -> list[dict]:
    runs = fetch_ingestion_runs(conn, SOURCE_WEEKLY_REPORTS)
    return [_ingestion_response(run) for run in runs]


@router.post(
    "/input-sources/slack/ingest",
    response_model=InputIngestionRunResponse,
    dependencies=[Depends(get_current_user)],
)
def ingest_slack_logs_api(conn: Connection = Depends(get_db)) -> dict:
    result = ingest_slack_logs(conn)
    return _ingestion_response(result)


@router.get(
    "/input-sources/slack/runs",
    response_model=list[InputIngestionRunResponse],
    dependencies=[Depends(get_current_user)],
)
def list_slack_ingestion_runs(conn: Connection = Depends(get_db)) -> list[dict]:
    runs = fetch_ingestion_runs(conn, SOURCE_SLACK_LOGS)
    return [_ingestion_response(run) for run in runs]


@router.post(
    "/input-sources/attendance/ingest",
    response_model=InputIngestionRunResponse,
    dependencies=[Depends(get_current_user)],
)
def ingest_attendance_api(conn: Connection = Depends(get_db)) -> dict:
    result = ingest_attendance(conn)
    return _ingestion_response(result)


@router.get(
    "/input-sources/attendance/runs",
    response_model=list[InputIngestionRunResponse],
    dependencies=[Depends(get_current_user)],
)
def list_attendance_runs(conn: Connection = Depends(get_db)) -> list[dict]:
    runs = fetch_ingestion_runs(conn, SOURCE_ATTENDANCE)
    return [_ingestion_response(run) for run in runs]


@router.get(
    "/history",
    response_model=list[HistoryEntryResponse],
    dependencies=[Depends(get_current_user)],
)
def list_history_api(
    status: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    conn: Connection = Depends(get_db),
) -> list[dict]:
    return fetch_history(conn, status=status, project_id=project_id, limit=limit)


def _build_plans(simulation_id: str, risk_score: int) -> list[dict]:
    return _build_plans_fallback(simulation_id, risk_score)


def _build_plans_with_bedrock(simulation_id: str, simulation: dict) -> tuple[list[dict], list[dict[str, str]]]:
    if not is_bedrock_configured():
        raise BedrockError("Bedrock is not configured.")

    evaluation = simulation.get("evaluation") or {}
    project = simulation.get("project") or evaluation.get("project") or {}
    team = simulation.get("team") or []
    context = {
        "simulation_id": simulation_id,
        "project": project,
        "team": team,
        "metrics": evaluation.get("metrics") or {},
        "pattern": evaluation.get("pattern") or "",
        "requirement_result": evaluation.get("requirementResult") or [],
    }

    result = generate_simulation_plans(context)
    plans: list[dict] = []
    for draft in result.plans:
        plan_id = f"plan-{simulation_id}-{draft.plan_type}"
        plan = {
            "id": plan_id,
            "simulationId": simulation_id,
            "planType": draft.plan_type,
            "summary": draft.summary,
            "prosCons": {"pros": draft.pros, "cons": draft.cons},
            "score": draft.score,
            "recommended": draft.is_recommended,
        }
        _plans[plan_id] = plan
        plans.append(plan)

    logs = build_simulation_plan_logs(result)
    return plans, logs


def _build_plans_fallback(simulation_id: str, risk_score: int) -> list[dict]:
    recommended = "A" if risk_score <= 50 else "B"
    plans: list[dict] = []
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


def _build_stream_logs(evaluation: dict) -> list[dict]:
    meeting_log = evaluation.get("meetingLog") or []

    def tone(agent_id: str) -> str:
        if agent_id == "PM":
            return "pm"
        if agent_id == "HR":
            return "hr"
        if agent_id == "RISK":
            return "risk"
        if agent_id == "GUNSHI":
            return "gunshi"
        return "gunshi"

    logs: list[dict] = []
    for entry in meeting_log:
        agent_id = str(entry.get("agent_id") or "SYSTEM")
        message = str(entry.get("message") or "")
        if not message:
            continue
        logs.append({"agent": agent_id, "message": message, "tone": tone(agent_id)})
    if logs:
        return logs

    metrics = evaluation.get("metrics") or {}
    pattern = evaluation.get("pattern") or ""
    fallback = [
        {"agent": "SYSTEM", "message": f"pattern={pattern}", "tone": "gunshi"},
        {
            "agent": "PM",
            "message": f"budget_pct={metrics.get('budgetPct', 0)}",
            "tone": "pm",
        },
        {
            "agent": "HR",
            "message": f"career_fit={metrics.get('careerFitPct', 0)}",
            "tone": "hr",
        },
        {
            "agent": "RISK",
            "message": f"risk_pct={metrics.get('riskPct', 0)}",
            "tone": "risk",
        },
    ]
    return fallback


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\n" + f"data: {json.dumps(payload)}\n\n"


def _ingestion_response(run) -> dict:
    return {
        "runId": run.run_id,
        "sourceType": run.source_type,
        "status": run.status,
        "itemsInserted": run.items_inserted,
        "startedAt": run.started_at.isoformat(),
        "finishedAt": run.finished_at.isoformat(),
        "error": run.error,
    }


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
            SELECT analysis_id, user_id, pattern_id, final_decision
            FROM ai_analysis_results
            ORDER BY analysis_id
            """
        )
    ).mappings().all()
    latest: dict[str, dict] = {}
    for row in rows:
        pm_risk, hr_risk, risk_risk = _risk_scores_from_pattern(row["pattern_id"])
        latest[row["user_id"]] = {
            "patternId": row["pattern_id"],
            "patternName": patterns.get(row["pattern_id"]),
            "pmRiskScore": pm_risk,
            "hrRiskScore": hr_risk,
            "riskRiskScore": risk_risk,
            "finalDecision": row["final_decision"],
        }
    return latest


def _risk_scores_from_pattern(pattern_id: str) -> tuple[int, int, int]:
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


def _proposal_score(plan_type: str, is_recommended: bool | None) -> int:
    if is_recommended:
        return 82
    if plan_type == "Plan_A":
        return 65
    if plan_type == "Plan_C":
        return 55
    return 60


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
            text_value = alert.get("title") or "Watchdog alert"
            if alert.get("subtitle"):
                text_value = f"{text_value} / {alert['subtitle']}"
            timeline.append(
                {
                    "t": "auto",
                    "text": text_value,
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


def _load_project_members(conn: Connection) -> dict[str, list[str]]:
    rows = conn.execute(
        text("SELECT project_id, user_id FROM assignments")
    ).mappings().all()
    project_members: dict[str, list[str]] = {}
    for row in rows:
        project_members.setdefault(row["project_id"], []).append(row["user_id"])
    return project_members


def _select_focus_member(
    project_members: dict[str, list[str]],
    analysis_by_user: dict[str, dict],
    project_id: str,
    focus_on: str,
) -> str | None:
    candidates = project_members.get(project_id) or []
    if not candidates:
        return None
    if focus_on == "career":
        key = "hrRiskScore"
    else:
        key = "riskRiskScore"
    return max(candidates, key=lambda uid: analysis_by_user.get(uid, {}).get(key, 0) or 0)


def _load_assignments(conn: Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT assignment_id, project_id, role_in_pj, allocation_rate, start_date, end_date
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
                "allocationRate": float(row.get("allocation_rate") or 0),
                "startDate": row["start_date"].isoformat() if row["start_date"] else None,
                "endDate": row["end_date"].isoformat() if row["end_date"] else None,
            }
        )
    return assignments
