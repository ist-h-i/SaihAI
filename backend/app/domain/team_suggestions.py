from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.domain.scoring import score


DEFAULT_MIN_AVAILABILITY_PCT = 30
DEFAULT_MIN_TEAM_SIZE = 3
DEFAULT_MAX_TEAM_SIZE = 6
DEFAULT_PROPOSAL_COUNT = 3
DEFAULT_CANDIDATE_LIMIT = 200


@dataclass(frozen=True)
class SuggestionWeights:
    skill: float
    budget: float
    availability: float
    risk: float


_WEIGHT_PRESETS: tuple[SuggestionWeights, ...] = (
    SuggestionWeights(skill=0.4, budget=0.25, availability=0.2, risk=0.15),
    SuggestionWeights(skill=0.6, budget=0.15, availability=0.15, risk=0.1),
    SuggestionWeights(skill=0.3, budget=0.45, availability=0.15, risk=0.1),
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _avg_availability(team: list[dict[str, Any]]) -> float:
    if not team:
        return 0.0
    return sum(int(m.get("availability") or 0) for m in team) / len(team)


def _budget_score(budget: int, budget_used: int) -> float:
    if budget <= 0:
        return 100.0
    pct = (budget_used / budget) * 100.0
    return _clamp(100.0 - pct, -100.0, 100.0)


def _objective(
    project: dict[str, Any],
    team: list[dict[str, Any]],
    weights: SuggestionWeights,
) -> float:
    metrics = score(project, team)
    budget = int(project.get("budget") or 0)
    skill_score = float(metrics.get("skillFitPct", 0))
    budget_score = _budget_score(budget, int(metrics.get("budgetUsed") or 0))
    availability_score = _avg_availability(team)
    risk_score = 100.0 - float(metrics.get("riskPct", 0))
    return (
        weights.skill * skill_score
        + weights.budget * budget_score
        + weights.availability * availability_score
        + weights.risk * risk_score
    )


def _candidate_skill_gain(
    required_skills: set[str],
    covered_skills: set[str],
    candidate: dict[str, Any],
) -> int:
    if not required_skills:
        return 0
    skills = {str(s) for s in (candidate.get("skills") or [])}
    gain = required_skills - covered_skills
    return sum(1 for skill in gain if skill in skills)


def _team_skills(team: list[dict[str, Any]]) -> set[str]:
    return {str(s) for member in team for s in (member.get("skills") or [])}


def _rank_candidates(project: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = {str(s) for s in (project.get("requiredSkills") or []) if s}

    def key(member: dict[str, Any]) -> tuple[int, int, int, str]:
        skills = {str(s) for s in (member.get("skills") or [])}
        match = sum(1 for s in required if s in skills) if required else 0
        availability = int(member.get("availability") or 0)
        cost = int(member.get("cost") or 0)
        return (-match, -availability, cost, str(member.get("id") or ""))

    return sorted(candidates, key=key)


def _build_team(
    project: dict[str, Any],
    candidates: list[dict[str, Any]],
    weights: SuggestionWeights,
    *,
    min_team_size: int,
    max_team_size: int,
    min_skill_fit_pct: int = 70,
    diversity_penalty_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    diversity_penalty_ids = diversity_penalty_ids or set()

    required_skills = {str(s) for s in (project.get("requiredSkills") or []) if s}
    team: list[dict[str, Any]] = []
    team_ids: set[str] = set()

    def pick_next(prefer_skill_gain: bool) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        best_score: float = float("-inf")
        covered = _team_skills(team)
        for candidate in candidates:
            cid = str(candidate.get("id") or "")
            if not cid or cid in team_ids:
                continue
            if prefer_skill_gain and _candidate_skill_gain(required_skills, covered, candidate) <= 0:
                continue
            next_team = [*team, candidate]
            next_score = _objective(project, next_team, weights)
            if cid in diversity_penalty_ids:
                next_score -= 7.5
            if next_score > best_score:
                best_score = next_score
                best = candidate
        return best

    while len(team) < min_team_size:
        candidate = pick_next(prefer_skill_gain=False)
        if not candidate:
            break
        cid = str(candidate.get("id") or "")
        team.append(candidate)
        team_ids.add(cid)

    while len(team) < max_team_size and required_skills:
        metrics = score(project, team)
        if int(metrics.get("skillFitPct") or 0) >= min_skill_fit_pct:
            break
        candidate = pick_next(prefer_skill_gain=True)
        if not candidate:
            break
        cid = str(candidate.get("id") or "")
        team.append(candidate)
        team_ids.add(cid)

    while len(team) < max_team_size:
        current_score = _objective(project, team, weights)
        candidate = pick_next(prefer_skill_gain=False)
        if not candidate:
            break
        cid = str(candidate.get("id") or "")
        next_score = _objective(project, [*team, candidate], weights)
        if cid in diversity_penalty_ids:
            next_score -= 7.5
        if next_score <= current_score:
            break
        team.append(candidate)
        team_ids.add(cid)

    return team


def _explain_team(project: dict[str, Any], team: list[dict[str, Any]], metrics: dict[str, int]) -> tuple[str, list[str]]:
    required = [str(s) for s in (project.get("requiredSkills") or []) if s]
    covered = _team_skills(team)
    missing = [s for s in required if s not in covered]

    why_parts: list[str] = []
    if required:
        if missing:
            why_parts.append(f"必須スキルの一部が不足（不足: {', '.join(missing)}）")
        else:
            why_parts.append("必須スキルを満たす構成")

    budget = int(project.get("budget") or 0)
    budget_used = int(metrics.get("budgetUsed") or 0)
    if budget > 0:
        why_parts.append(f"予算 ¥{budget_used:,} / ¥{budget:,}")
        if budget_used > budget:
            why_parts.append("予算超過のため調整が必要")

    avg_avail = _avg_availability(team)
    if team:
        why_parts.append(f"平均稼働余力 {avg_avail:.0f}%")
    why_parts.append(f"リスク推定 {int(metrics.get('riskPct') or 0)}%")

    return " / ".join(why_parts) if why_parts else "候補プールからバランス良く選定", missing


def build_team_suggestions(
    project: dict[str, Any],
    members: list[dict[str, Any]],
    *,
    exclude_member_ids: Iterable[str] = (),
    min_availability_pct: int = DEFAULT_MIN_AVAILABILITY_PCT,
    proposal_count: int = DEFAULT_PROPOSAL_COUNT,
    min_team_size: int = DEFAULT_MIN_TEAM_SIZE,
    max_team_size: int = DEFAULT_MAX_TEAM_SIZE,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> dict[str, Any]:
    exclude = {str(x) for x in exclude_member_ids if str(x)}
    min_availability_pct = int(min_availability_pct)
    if min_availability_pct < 0:
        min_availability_pct = 0
    if min_availability_pct > 100:
        min_availability_pct = 100

    pool = [
        m
        for m in members
        if str(m.get("id") or "") not in exclude and int(m.get("availability") or 0) >= min_availability_pct
    ]
    ranked = _rank_candidates(project, pool)[: max(0, int(candidate_limit))]

    suggestions: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    presets = list(_WEIGHT_PRESETS)
    if proposal_count > len(presets):
        presets.extend([presets[0]] * (proposal_count - len(presets)))
    presets = presets[: max(0, int(proposal_count))]

    for index, weights in enumerate(presets, start=1):
        team = _build_team(
            project,
            ranked,
            weights,
            min_team_size=min_team_size,
            max_team_size=max_team_size,
            diversity_penalty_ids=used_ids,
        )
        if not team:
            continue
        metrics = score(project, team)
        why, missing = _explain_team(project, team, metrics)
        suggestions.append(
            {
                "id": f"team-{index}",
                "source": "internal",
                "applyable": True,
                "memberIds": [str(m.get("id") or "") for m in team if str(m.get("id") or "")],
                "team": team,
                "metrics": metrics,
                "why": why,
                "missingSkills": missing,
                "score": _objective(project, team, _WEIGHT_PRESETS[0]),
            }
        )
        used_ids.update(str(m.get("id") or "") for m in team if str(m.get("id") or ""))

    # Ensure at least one entry exists; fall back to external procurement guidance.
    if not suggestions:
        required = [str(s) for s in (project.get("requiredSkills") or []) if s]
        placeholders = []
        for idx, skill in enumerate(required[:3] or ["--"], start=1):
            placeholders.append(
                {
                    "id": f"external-{idx}",
                    "name": "--",
                    "role": skill if skill else "--",
                    "cost": None,
                    "availability": None,
                    "skills": [],
                }
            )
        suggestions.append(
            {
                "id": "external-1",
                "source": "external",
                "applyable": False,
                "memberIds": [],
                "team": placeholders,
                "metrics": None,
                "why": "内部候補（availability 条件）で組成できないため、外部調達を検討してください。",
                "missingSkills": required,
                "score": 0.0,
            }
        )

    # Decide recommendation: prefer budget-compliant internal teams when budget is set.
    budget = int(project.get("budget") or 0)
    internal = [s for s in suggestions if s.get("source") == "internal"]
    recommended_id: str | None = None
    if internal:
        if budget > 0:
            within_budget = [s for s in internal if int((s.get("metrics") or {}).get("budgetUsed") or 0) <= budget]
            target = within_budget or internal
        else:
            target = internal
        best = max(target, key=lambda s: float(s.get("score") or 0.0))
        recommended_id = str(best.get("id") or "")
    else:
        recommended_id = str(suggestions[0].get("id") or "")

    for suggestion in suggestions:
        suggestion["isRecommended"] = str(suggestion.get("id") or "") == recommended_id
        suggestion.pop("score", None)

    return {
        "minAvailability": min_availability_pct,
        "candidateCount": len(ranked),
        "suggestions": suggestions,
    }

