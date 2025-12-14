from __future__ import annotations

from typing import Any

BURNOUT_WORDS = ("疲労", "飽き", "燃え尽き", "限界")
RISK_WORDS = ("対人トラブル", "噂", "炎上", "不満")
GROWTH_WORDS = ("挑戦", "伸びしろ", "育成", "学び")


def _clamp_pct(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _count_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(text.count(word) for word in keywords)


def score(project: dict[str, Any], team: list[dict[str, Any]]) -> dict[str, int]:
    budget = int(project.get("budget") or 0)
    budget_used = int(sum(int(m.get("cost") or 0) for m in team))
    budget_pct = _clamp_pct((budget_used / budget * 100) if budget else 0)

    required = list(project.get("requiredSkills") or [])
    team_skills = {s for m in team for s in (m.get("skills") or [])}
    covered = sum(1 for s in required if s in team_skills)
    skill_fit_pct = _clamp_pct((covered / len(required) * 100) if required else 100)

    notes = " ".join(str(m.get("notes") or "") for m in team)
    growth = _count_hits(notes, GROWTH_WORDS)
    burnout = _count_hits(notes, BURNOUT_WORDS)
    career_fit_pct = _clamp_pct(50 + growth * 10 - burnout * 20)

    avg_avail = (sum(int(m.get("availability") or 0) for m in team) / len(team)) if team else 0
    risk = 20 + _count_hits(notes, RISK_WORDS) * 20 + burnout * 25
    if avg_avail < 50:
        risk += 20
    if budget_pct > 100:
        risk += 20
    risk_pct = _clamp_pct(risk)

    return {
        "budgetUsed": budget_used,
        "budgetPct": budget_pct,
        "skillFitPct": skill_fit_pct,
        "careerFitPct": career_fit_pct,
        "riskPct": risk_pct,
    }

