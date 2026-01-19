from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.plan_chat")


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _clamp_score(value: Any, *, default: int = 60) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))


@dataclass(frozen=True)
class PlanChatUpdate:
    assistant_message: str
    summary: str
    pros: list[str]
    cons: list[str]
    score: int
    raw: dict[str, Any]


def update_plan_via_chat(
    *,
    plan_type: str,
    plan: dict[str, Any],
    simulation_context: dict[str, Any],
    history: list[dict[str, str]],
    user_message: str,
) -> PlanChatUpdate:
    system_prompt = (
        "You are an expert staffing strategist. The user is discussing a selected intervention plan (Plan A/B/C). "
        "Update the plan content based on the user's custom instruction and the conversation so far. "
        "Return ONLY valid JSON (no markdown, no prose outside JSON). "
        "Required keys: assistant_message (string, concise Japanese), plan (object). "
        "plan object keys: summary (string, concise Japanese), pros (string array), cons (string array), score (0-100 integer). "
        "Keep pros/cons to at most 5 items each. Do not change the plan_type."
    )

    plan_payload = {
        "plan_type": plan_type,
        "summary": str(plan.get("summary") or ""),
        "pros": list((plan.get("prosCons") or {}).get("pros") or []),
        "cons": list((plan.get("prosCons") or {}).get("cons") or []),
        "score": plan.get("score"),
        "recommended": bool(plan.get("recommended")),
    }

    input_payload = {
        "simulation": simulation_context,
        "selected_plan": plan_payload,
        "history": history[-12:],
        "user_message": user_message,
    }

    prompt = (
        "Update the selected plan and respond to the user.\n"
        "Return JSON only.\n\n"
        "[INPUT_JSON]\n"
        f"{json.dumps(input_payload, ensure_ascii=False)}"
    )

    try:
        payload = invoke_json(prompt, system_prompt=system_prompt, max_tokens=1200, temperature=0.2, retries=1)
    except BedrockInvocationError:
        logger.exception("plan chat Bedrock invocation failed plan_type=%s", plan_type)
        raise

    if not isinstance(payload, dict):
        raise BedrockInvocationError("plan chat returned non-object JSON")

    assistant_message = str(payload.get("assistant_message") or "").strip()
    updated_plan = payload.get("plan")
    if not isinstance(updated_plan, dict):
        updated_plan = {}

    summary = str(updated_plan.get("summary") or "").strip()
    pros = _as_str_list(updated_plan.get("pros"))[:5]
    cons = _as_str_list(updated_plan.get("cons"))[:5]
    score = _clamp_score(updated_plan.get("score"), default=_clamp_score(plan.get("score"), default=60))

    if not assistant_message:
        assistant_message = "了解しました。ご指示を反映して Plan を更新します。"
    if not summary:
        summary = str(plan.get("summary") or "").strip() or f"Plan {plan_type}"
    if not pros:
        pros = _as_str_list((plan.get("prosCons") or {}).get("pros"))[:5] or ["実行しやすい"]
    if not cons:
        cons = _as_str_list((plan.get("prosCons") or {}).get("cons"))[:5] or ["追加検討が必要"]

    return PlanChatUpdate(
        assistant_message=assistant_message,
        summary=summary,
        pros=pros,
        cons=cons,
        score=score,
        raw=payload,
    )

