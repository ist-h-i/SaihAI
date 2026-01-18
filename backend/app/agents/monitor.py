from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.monitor")


@dataclass(frozen=True)
class MonitorResult:
    risk_level: int
    reason: str
    urgency: str
    raw: dict[str, Any]


def analyze_risk(text_bundle: str) -> MonitorResult:
    system_prompt = (
        "You are a HR risk analyst. Return only JSON with keys: "
        "risk_level (0-100), reason (string), urgency (High|Med|Low)."
    )
    prompt = (
        "Analyze the following weekly reports and Slack logs. "
        "Return JSON only.\n\n"
        f"[Input]\n{text_bundle}"
    )
    try:
        payload = invoke_json(prompt, system_prompt=system_prompt, retries=1)
    except BedrockInvocationError:
        logger.exception("monitor Bedrock invocation failed")
        raise

    if not isinstance(payload, dict):
        raise BedrockInvocationError("monitor returned non-object JSON")

    risk_level = payload.get("risk_level")
    try:
        risk_value = int(float(risk_level))
    except (TypeError, ValueError):
        risk_value = 0

    risk_value = max(0, min(100, risk_value))
    reason = str(payload.get("reason") or "")
    urgency = str(payload.get("urgency") or "Low")
    if urgency not in {"High", "Med", "Low"}:
        urgency = "Low"

    if not reason:
        reason = "No clear risk detected."

    return MonitorResult(
        risk_level=risk_value,
        reason=reason,
        urgency=urgency,
        raw=payload,
    )
