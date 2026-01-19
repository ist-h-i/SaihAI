from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.simulator_planner")

_DEFAULT_PLAN_TYPES = ("A", "B", "C")

_LOG_BEDROCK_CONTEXT = os.getenv("LOG_BEDROCK_CONTEXT", "").lower() in {"1", "true", "yes", "on"}
_LOG_BEDROCK_CONTEXT_FULL = os.getenv("LOG_BEDROCK_CONTEXT_FULL", "").lower() in {"1", "true", "yes", "on"}
_LOG_BEDROCK_CONTEXT_MAX_CHARS = max(0, int(os.getenv("LOG_BEDROCK_CONTEXT_MAX_CHARS", "8000") or "8000"))
_LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS = max(
    0, int(os.getenv("LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS", "200") or "200")
)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...(truncated,{len(text)}chars)"


def _safe_json_dumps(payload: Any, *, max_chars: int) -> str:
    try:
        dumped = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        dumped = "{unserializable_json}"
    return _truncate(dumped, max_chars)


def _sanitize_bedrock_context(context: dict[str, Any]) -> dict[str, Any]:
    if _LOG_BEDROCK_CONTEXT_FULL:
        return context

    sanitized: dict[str, Any] = dict(context)

    project = sanitized.get("project")
    if isinstance(project, dict):
        project_copy = dict(project)
        description = project_copy.get("description")
        if isinstance(description, str) and description:
            project_copy["description"] = _truncate(description, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
        sanitized["project"] = project_copy

    team = sanitized.get("team")
    if isinstance(team, list):
        sanitized_team: list[Any] = []
        for member in team:
            if not isinstance(member, dict):
                sanitized_team.append(member)
                continue
            member_copy = dict(member)
            notes = member_copy.get("notes")
            if isinstance(notes, str) and notes:
                member_copy["notes"] = _truncate(notes, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
            aspiration = member_copy.get("careerAspiration")
            if isinstance(aspiration, str) and aspiration:
                member_copy["careerAspiration"] = _truncate(aspiration, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
            sanitized_team.append(member_copy)
        sanitized["team"] = sanitized_team

    return sanitized


def _normalize_plan_type(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in _DEFAULT_PLAN_TYPES:
        return raw
    if raw.startswith("Plan_") and len(raw) == len("Plan_A"):
        candidate = raw[-1]
        if candidate in _DEFAULT_PLAN_TYPES:
            return candidate
    upper = raw.upper()
    if upper in _DEFAULT_PLAN_TYPES:
        return upper
    return "A"


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _clamp_score(value: Any, *, default: int = 50) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))


@dataclass(frozen=True)
class SimulationPlanDraft:
    plan_type: str
    summary: str
    pros: list[str]
    cons: list[str]
    score: int
    is_recommended: bool


@dataclass(frozen=True)
class SimulationPlansResult:
    plans: list[SimulationPlanDraft]
    diagnostics: dict[str, str]
    suggestions: list[str]
    raw: dict[str, Any]


def generate_simulation_plans(context: dict[str, Any]) -> SimulationPlansResult:
    system_prompt = (
        "You are an expert staffing strategist for a SI/consulting organization. "
        "Given a project and selected candidate members, you must diagnose the team and propose three plans (A/B/C). "
        "Assess: budget fit, requirement coverage, career fit, and team synergy/risks. "
        "Return ONLY valid JSON (no markdown). Required keys: "
        "recommended_plan (A|B|C), plans (array), diagnostics (object), suggestions (array). "
        "plans must include exactly 3 objects for plan_type A,B,C. "
        "Each plan object keys: plan_type (A|B|C), summary (string, concise Japanese), "
        "pros (string array), cons (string array), score (0-100 integer). "
        "diagnostics keys: budget, requirements, career, synergy (all strings, concise Japanese). "
        "suggestions is an array of actionable recommendations in concise Japanese."
    )
    prompt = (
        "以下の入力(JSON)に基づいて、チーム編成の診断と3つのプランを作成してください。"
        "出力は必ず JSON のみ。\n\n"
        "[INPUT_JSON]\n"
        f"{json.dumps(context, ensure_ascii=False)}"
    )
    if _LOG_BEDROCK_CONTEXT:
        logger.warning(
            "Bedrock plan generation context=%s",
            _safe_json_dumps(_sanitize_bedrock_context(context), max_chars=_LOG_BEDROCK_CONTEXT_MAX_CHARS),
        )
    try:
        payload = invoke_json(prompt, system_prompt=system_prompt, max_tokens=1400, temperature=0.2, retries=1)
    except BedrockInvocationError:
        logger.exception("simulator planner Bedrock invocation failed")
        raise

    if not isinstance(payload, dict):
        raise BedrockInvocationError("simulator planner returned non-object JSON")

    recommended_plan = _normalize_plan_type(payload.get("recommended_plan"))

    diagnostics: dict[str, str] = {}
    raw_diagnostics = payload.get("diagnostics")
    if isinstance(raw_diagnostics, dict):
        for key in ("budget", "requirements", "career", "synergy"):
            value = str(raw_diagnostics.get(key) or "").strip()
            if value:
                diagnostics[key] = value

    suggestions = _as_str_list(payload.get("suggestions"))

    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list):
        raw_plans = []

    draft_by_type: dict[str, SimulationPlanDraft] = {}
    for plan in raw_plans:
        if not isinstance(plan, dict):
            continue
        plan_type = _normalize_plan_type(plan.get("plan_type"))
        summary = str(plan.get("summary") or "").strip()
        pros = _as_str_list(plan.get("pros"))[:5]
        cons = _as_str_list(plan.get("cons"))[:5]
        score = _clamp_score(plan.get("score"), default=55)

        if not summary:
            summary = "編成の微調整を行い、安定運用を優先"
        if not pros:
            pros = ["短期の安定性"]
        if not cons:
            cons = ["中長期の成長投資が弱い"]

        draft_by_type[plan_type] = SimulationPlanDraft(
            plan_type=plan_type,
            summary=summary,
            pros=pros,
            cons=cons,
            score=score,
            is_recommended=plan_type == recommended_plan,
        )

    plans: list[SimulationPlanDraft] = []
    for plan_type in _DEFAULT_PLAN_TYPES:
        existing = draft_by_type.get(plan_type)
        if existing:
            plans.append(existing)
            continue
        plans.append(
            SimulationPlanDraft(
                plan_type=plan_type,
                summary="編成の微調整を行い、安定運用を優先" if plan_type == "A" else "育成/冗長性を足して未来投資"
                if plan_type == "B"
                else "予算順守を最優先し、スコープ/体制を圧縮",
                pros=["短期の安定性"] if plan_type == "A" else ["成長と安定の両立"] if plan_type == "B" else ["利益率の改善"],
                cons=["改善余地が残る"] if plan_type == "A" else ["調整コスト"] if plan_type == "B" else ["品質/リスク上昇"],
                score=60 if plan_type == "A" else 65 if plan_type == "B" else 55,
                is_recommended=plan_type == recommended_plan,
            )
        )

    if not any(p.is_recommended for p in plans):
        plans = [
            SimulationPlanDraft(
                plan_type=p.plan_type,
                summary=p.summary,
                pros=p.pros,
                cons=p.cons,
                score=p.score,
                is_recommended=p.plan_type == "A",
            )
            for p in plans
        ]

    return SimulationPlansResult(
        plans=plans,
        diagnostics=diagnostics,
        suggestions=suggestions,
        raw=payload,
    )


def build_simulation_plan_logs(result: SimulationPlansResult) -> list[dict[str, str]]:
    logs: list[dict[str, str]] = []
    diag = result.diagnostics
    if diag.get("budget") or diag.get("requirements"):
        msg = " / ".join([v for v in [diag.get("budget"), diag.get("requirements")] if v])
        logs.append({"agent": "PM", "message": msg, "tone": "pm"})
    if diag.get("career"):
        logs.append({"agent": "HR", "message": diag["career"], "tone": "hr"})
    if diag.get("synergy"):
        logs.append({"agent": "RISK", "message": diag["synergy"], "tone": "risk"})

    recommended = next((p for p in result.plans if p.is_recommended), None)
    if recommended:
        summary = f"推奨: Plan {recommended.plan_type}（{recommended.summary}）"
        if result.suggestions:
            summary = summary + f" / 次アクション: {result.suggestions[0]}"
        logs.append({"agent": "GUNSHI", "message": summary, "tone": "gunshi"})

    for suggestion in result.suggestions[:3]:
        logs.append({"agent": "GUNSHI", "message": f"提案: {suggestion}", "tone": "gunshi"})

    return logs

