from __future__ import annotations

from typing import Any

BURNOUT_WORDS = ("疲労", "飽き", "燃え尽き", "限界")
RISK_WORDS = ("対人トラブル", "噂", "炎上", "不満")
GROWTH_WORDS = ("挑戦", "伸びしろ", "育成", "学び")

LEADER_NAME_TOKENS = ("sato", "佐藤")
VETERAN_NAME_TOKENS = ("tanaka", "田中")
MENTOR_NAME_TOKENS = ("yamada", "山田")
MENTOR_ROLE_TOKENS = ("mentor", "advisor", "顧問", "メンター")

COMPRESSED_COST = 30
RISK_OFFSET = 15


def _clamp_pct(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _count_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(text.count(word) for word in keywords)


def _member_text(member: dict[str, Any]) -> str:
    return f"{member.get('name', '')} {member.get('role', '')}".strip().lower()


def _has_member(team: list[dict[str, Any]], tokens: tuple[str, ...]) -> bool:
    return any(any(token in _member_text(m) for token in tokens) for m in team)


def _has_high_risk_member(team: list[dict[str, Any]]) -> bool:
    for member in team:
        notes = str(member.get("notes") or "")
        if any(word in notes for word in BURNOUT_WORDS + RISK_WORDS):
            return True
    return False


def _compressed_cost_for_member(
    member: dict[str, Any],
    leader_present: bool,
    veteran_present: bool,
) -> int:
    cost = int(member.get("cost") or 0)
    if not (leader_present and veteran_present):
        return cost
    name = _member_text(member)
    if any(token in name for token in VETERAN_NAME_TOKENS):
        return min(cost, COMPRESSED_COST)
    return cost


def score(project: dict[str, Any], team: list[dict[str, Any]]) -> dict[str, int]:
    budget = int(project.get("budget") or 0)
    leader_present = _has_member(team, LEADER_NAME_TOKENS)
    veteran_present = _has_member(team, VETERAN_NAME_TOKENS)
    budget_used = int(
        sum(_compressed_cost_for_member(m, leader_present, veteran_present) for m in team)
    )
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
    if _has_high_risk_member(team) and (
        _has_member(team, MENTOR_NAME_TOKENS) or _has_member(team, MENTOR_ROLE_TOKENS)
        or leader_present
    ):
        risk -= RISK_OFFSET
    risk_pct = _clamp_pct(risk)

    return {
        "budgetUsed": budget_used,
        "budgetPct": budget_pct,
        "skillFitPct": skill_fit_pct,
        "careerFitPct": career_fit_pct,
        "riskPct": risk_pct,
    }
