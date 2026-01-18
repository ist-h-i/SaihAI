from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.gunshi")


@dataclass(frozen=True)
class GunshiPlan:
    plan_type: str
    description: str
    predicted_future_impact: str
    is_recommended: bool


def generate_plans(context: dict[str, Any]) -> list[GunshiPlan]:
    system_prompt = (
        "You are a senior strategist. Return only JSON with keys: "
        "recommended_plan and plans. plans is an array of objects with "
        "plan_type (Plan_A/Plan_B/Plan_C), description, predicted_future_impact."
    )
    prompt = (
        "Use the context to propose two or three plans. "
        "Return JSON only.\n\n"
        f"[Context]\n{context}"
    )
    try:
        payload = invoke_json(prompt, system_prompt=system_prompt, retries=1)
    except BedrockInvocationError:
        logger.exception("gunshi Bedrock invocation failed")
        raise

    if not isinstance(payload, dict):
        raise BedrockInvocationError("gunshi returned non-object JSON")

    recommended = str(payload.get("recommended_plan") or "Plan_A")
    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list):
        raw_plans = []

    plans: list[GunshiPlan] = []
    for plan in raw_plans:
        if not isinstance(plan, dict):
            continue
        plan_type = str(plan.get("plan_type") or "").strip() or "Plan_A"
        description = str(plan.get("description") or "").strip()
        impact = str(plan.get("predicted_future_impact") or "").strip()
        if not description:
            description = "Maintain current staffing while monitoring risk signals."
        if not impact:
            impact = "Stability with moderate mitigation of risk signals."
        plans.append(
            GunshiPlan(
                plan_type=plan_type,
                description=description,
                predicted_future_impact=impact,
                is_recommended=plan_type == recommended,
            )
        )

    if not plans:
        plans = [
            GunshiPlan(
                plan_type="Plan_A",
                description="Maintain current staffing and monitor risk weekly.",
                predicted_future_impact="Short-term stability, limited mitigation.",
                is_recommended=True,
            ),
            GunshiPlan(
                plan_type="Plan_B",
                description="Adjust workload and introduce support coverage.",
                predicted_future_impact="Risk reduction with moderate disruption.",
                is_recommended=False,
            ),
        ]

    return plans
