from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.seed import find_members, find_project
from app.domain.models import SimulationRequest
from app.domain.patterns import Vote, detect_pattern
from app.domain.scoring import score

router = APIRouter()


def _vote_pm(metrics: dict[str, int]) -> Vote:
    return "ok" if metrics["budgetPct"] <= 100 and metrics["skillFitPct"] >= 70 else "ng"


def _vote_hr(team_notes: str, metrics: dict[str, int]) -> Vote:
    if any(w in team_notes for w in ("疲労", "飽き", "燃え尽き")):
        return "ng"
    return "ok" if metrics["careerFitPct"] >= 45 else "ng"


def _vote_risk(metrics: dict[str, int]) -> Vote:
    return "ok" if metrics["riskPct"] <= 60 else "ng"


def _decision_pm(metrics: dict[str, int]) -> tuple[str, int, str, str]:
    if metrics["budgetPct"] > 110:
        return (
            "CONDITIONAL_APPROVE",
            min(100, metrics["budgetPct"]),
            "予算超過（上限とスコープ調整が必要）",
            f"予算消化率が {metrics['budgetPct']}% です。コスト効率の観点で条件付き賛成です。",
        )
    if metrics["skillFitPct"] < 70:
        return (
            "CONDITIONAL_APPROVE",
            65,
            "必須スキルの不足（レビュー/補強が必要）",
            f"スキル適合率が {metrics['skillFitPct']}% です。補強前提で条件付き賛成です。",
        )
    return ("APPROVE", 10, "予算/スキルが許容範囲", "予算とスキル適合性の観点で問題ありません。")


def _decision_hr(team_notes: str, metrics: dict[str, int]) -> tuple[str, int, str, str]:
    if any(w in team_notes for w in ("疲労", "飽き", "燃え尽き", "限界")):
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
    return ("APPROVE", 15, "成長/エンゲージメントが許容", "成長機会とエンゲージメントの観点で問題ありません。")


def _decision_risk(metrics: dict[str, int], pattern: str) -> tuple[str, int, str, str]:
    if metrics["riskPct"] > 60:
        return (
            "REJECT",
            metrics["riskPct"],
            "炎上/離職リスクが高い（要介入）",
            f"RISK={metrics['riskPct']}%。パターンは {pattern}。放置すると損害が拡大します。",
        )
    return ("APPROVE", metrics["riskPct"], "統計上の大きな警告なし", f"RISK={metrics['riskPct']}%。現時点で致命的な警告はありません。")


@router.post("/simulate")
def simulate(req: SimulationRequest) -> dict:
    project = find_project(req.projectId)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    team = find_members(req.memberIds)
    if req.memberIds and len(team) != len(set(req.memberIds)):
        raise HTTPException(status_code=404, detail="member not found")

    metrics = score(project, team)
    notes = " ".join(str(m.get("notes") or "") for m in team)
    votes: dict[str, Vote] = {
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

    plans = [
        {
            "id": "A",
            "title": "堅実維持",
            "pros": ["短期安定"],
            "cons": ["疲労/属人化が溜まる可能性"],
            "recommended": recommend == "A",
        },
        {
            "id": "B",
            "title": "未来投資",
            "pros": ["育成と安定の両立"],
            "cons": ["調整コスト"],
            "recommended": recommend == "B",
        },
        {
            "id": "C",
            "title": "コスト重視",
            "pros": ["利益率最大"],
            "cons": ["炎上/品質リスク"],
            "recommended": recommend == "C",
        },
    ]

    risk_level = "bad" if metrics["riskPct"] >= 75 else ("ok" if metrics["riskPct"] >= 50 else "good")
    timeline = [
        {"t": "1ヶ月後", "level": risk_level, "text": f"パターン: {pattern}（兆候が顕在化）"},
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

    return {
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
        "plans": plans,
    }
