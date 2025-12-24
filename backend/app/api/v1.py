from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.data.seed import find_members, find_project, get_members, get_projects
from app.domain.patterns import detect_pattern
from app.domain.scoring import score

router = APIRouter(prefix="/api/v1")


class SimulationEvaluateRequest(BaseModel):
    projectId: str = Field(min_length=1)
    memberIds: list[str] = Field(default_factory=list)


class SimulationPlanRequest(BaseModel):
    simulationId: str = Field(min_length=1)


class MessageRequest(BaseModel):
    text: str = Field(min_length=1)
    context: dict | None = None


class ApprovalAction(BaseModel):
    reason: str | None = None


class NemawashiGenerateRequest(BaseModel):
    planId: str = Field(min_length=1)


class AlertAckRequest(BaseModel):
    notedBy: str | None = None


_alerts = {
    "alert-ec": {
        "id": "alert-ec",
        "severity": "high",
        "type": "burnout",
        "subjectType": "project",
        "subjectId": "ec",
        "message": "ECリニューアル班で燃え尽き兆候。休息か人員交代が必要です。",
        "evidence": "週報で疲労/飽きの表現が増加。",
        "status": "open",
        "risk": 78,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "title": "ECリニューアル燃え尽き警戒",
        "subtitle": "燃え尽き兆候: 田中/山田",
    }
}

_kpis = [
    {"label": "Delivery", "value": "94", "suffix": "pt", "delta": "+2.1", "color": "#a5b4fc", "deltaColor": "#22c55e"},
    {"label": "Risk", "value": "18", "suffix": "%", "delta": "-1.4", "color": "#f87171", "deltaColor": "#22c55e"},
    {"label": "Morale", "value": "76", "suffix": "%", "delta": "+0.8", "color": "#34d399", "deltaColor": "#22c55e"},
    {"label": "Capacity", "value": "82", "suffix": "%", "delta": "-3.2", "color": "#38bdf8", "deltaColor": "#fbbf24"},
]

_simulations: dict[str, dict] = {}
_plans: dict[str, dict] = {}
_drafts: dict[str, dict] = {}
_approvals: dict[str, dict] = {}
_executions: dict[str, list[dict]] = {}
_messages: list[dict] = []


@router.get("/projects")
def list_projects() -> list[dict]:
    return get_projects()


@router.get("/members")
def list_members() -> list[dict]:
    return get_members()


@router.get("/dashboard/kpis")
def get_kpis() -> list[dict]:
    return _kpis


@router.get("/alerts")
def list_alerts(status: str | None = None) -> list[dict]:
    alerts = list(_alerts.values())
    if status:
        alerts = [a for a in alerts if a.get("status") == status]
    return alerts


@router.post("/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: str, req: AlertAckRequest | None = None) -> dict:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    if alert.get("status") != "open":
        return alert
    alert = dict(alert)
    alert.update({"status": "ack", "acknowledgedBy": req.notedBy if req else None, "acknowledgedAt": datetime.now(timezone.utc).isoformat()})
    _alerts[alert_id] = alert
    return alert


@router.post("/simulations/evaluate")
def evaluate(req: SimulationEvaluateRequest) -> dict:
    project = find_project(req.projectId)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    team = find_members(req.memberIds)
    if len(team) != len(set(req.memberIds)):
        raise HTTPException(status_code=404, detail="member not found")

    metrics = score(project, team)
    votes = {
        "pm": "ok" if metrics["budgetPct"] <= 100 and metrics["skillFitPct"] >= 70 else "ng",
        "hr": "ok" if metrics["careerFitPct"] >= 45 else "ng",
        "risk": "ok" if metrics["riskPct"] <= 60 else "ng",
    }
    pattern = detect_pattern(project, team, metrics, votes)

    sim_id = f"sim-{uuid4().hex[:8]}"
    result = {
        "id": sim_id,
        "projectId": project["id"],
        "selectedMembers": req.memberIds,
        "totalCost": metrics["budgetUsed"],
        "budgetStatus": "within" if metrics["budgetPct"] <= 100 else "over",
        "requirementResult": [
            {"name": skill, "fulfilled": skill in {s for m in team for s in (m.get("skills") or [])}}
            for skill in project.get("requiredSkills", [])
        ],
        "riskScore": metrics["riskPct"],
        "overallScore": max(0, 100 - metrics["riskPct"]),
        "councilLogs": [
            {"agent": "PM", "vote": votes["pm"], "message": "予算とスキルの観点で判定"},
            {"agent": "HR", "vote": votes["hr"], "message": "成長/燃え尽きの観点で判定"},
            {"agent": "RISK", "vote": votes["risk"], "message": "炎上/離職リスクの観点で判定"},
        ],
        "chartValues": metrics,
        "pattern": pattern,
    }
    _simulations[sim_id] = result
    return result


@router.post("/simulations/{simulation_id}/plans/generate")
def generate_plans(simulation_id: str):
    simulation = _simulations.get(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="simulation not found")

    recommended = "A" if simulation.get("riskScore", 0) <= 50 else "B"
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
            "score": max(0, 100 - simulation.get("riskScore", 0) - (10 if pid == "C" else 0)),
            "recommended": pid == recommended,
        }
        _plans[plan_id] = plan
        plans.append(plan)
    return plans


@router.post("/plans/{plan_id}/nemawashi/generate")
def generate_nemawashi(plan_id: str, _req: NemawashiGenerateRequest | None = None):
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    draft_id = f"draft-{uuid4().hex[:8]}"
    draft = {
        "id": draft_id,
        "planId": plan_id,
        "items": [
            {"type": "email", "subject": "根回しメール案", "body": "関係者への合意形成メール草案"},
            {"type": "calendar", "subject": "1on1候補", "body": "来週の1on1候補枠を確保"},
            {"type": "hr", "subject": "申請ドラフト", "body": "HR申請のドラフト"},
        ],
        "status": "draft",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "approvalId": None,
    }
    _drafts[draft_id] = draft
    return draft


@router.post("/nemawashi/{draft_id}/request-approval")
def request_approval(draft_id: str):
    draft = _drafts.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    approval_id = f"appr-{uuid4().hex[:8]}"
    approval = {
        "id": approval_id,
        "targetType": "nemawashi",
        "targetId": draft_id,
        "status": "pending",
        "requestedAt": datetime.now(timezone.utc).isoformat(),
    }
    _approvals[approval_id] = approval
    draft = dict(draft)
    draft.update({"status": "pending_approval", "approvalId": approval_id})
    _drafts[draft_id] = draft
    return approval


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, payload: ApprovalAction | None = None):
    approval = _approvals.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="approval not found")
    approval = dict(approval)
    approval.update({
        "status": "approved",
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "reason": payload.reason if payload else None,
    })
    _approvals[approval_id] = approval
    draft_id = approval.get("targetId")
    if draft_id and draft_id in _drafts:
        draft = dict(_drafts[draft_id])
        draft["status"] = "approved"
        _drafts[draft_id] = draft
    return approval


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, payload: ApprovalAction | None = None):
    approval = _approvals.get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="approval not found")
    approval = dict(approval)
    approval.update({
        "status": "rejected",
        "approvedAt": None,
        "reason": payload.reason if payload else None,
    })
    _approvals[approval_id] = approval
    draft_id = approval.get("targetId")
    if draft_id and draft_id in _drafts:
        draft = dict(_drafts[draft_id])
        draft["status"] = "draft"
        _drafts[draft_id] = draft
    return approval


@router.post("/nemawashi/{draft_id}/execute")
def execute_draft(draft_id: str):
    draft = _drafts.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    approval_id = draft.get("approvalId")
    approval = _approvals.get(approval_id) if approval_id else None
    if not approval or approval.get("status") != "approved":
        raise HTTPException(status_code=403, detail="approval required")

    log_entry = {
        "id": f"exec-{uuid4().hex[:8]}",
        "approvalId": approval_id,
        "actionType": "batch",
        "payload": draft.get("items", []),
        "result": "success",
        "executedAt": datetime.now(timezone.utc).isoformat(),
    }
    _executions.setdefault(draft_id, []).append(log_entry)
    draft = dict(draft)
    draft["status"] = "executed"
    _drafts[draft_id] = draft
    return _executions[draft_id]


@router.get("/channels")
def list_channels():
    return [
        {"id": "ai-council", "name": "AI Council", "badge": len(_messages)},
    ]


@router.get("/channels/{channel_id}/messages")
def list_messages(channel_id: str):
    if channel_id != "ai-council":
        raise HTTPException(status_code=404, detail="channel not found")
    return _messages


@router.post("/channels/{channel_id}/messages")
def post_message(channel_id: str, req: MessageRequest):
    if channel_id != "ai-council":
        raise HTTPException(status_code=404, detail="channel not found")
    message = {
        "id": f"msg-{uuid4().hex[:8]}",
        "channelId": channel_id,
        "text": req.text,
        "context": req.context or {},
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "from": "user",
    }
    _messages.append(message)
    return message
