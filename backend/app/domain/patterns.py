from __future__ import annotations

from typing import Any, Literal

Vote = Literal["ok", "ng"]

PATTERNS: dict[str, str] = {
    "Unanimous": "PM/HR/Risk が全会一致でOK",
    "Burnout": "PMは許容でもHR/Riskが燃え尽き懸念でNG",
    "DiamondInTheRough": "短期は不安だが育成価値が高い（HRが推す）",
    "HighFlyer": "高スキルだが高単価/制約でPMが迷う",
    "HiddenBomb": "表面上はOKだが潜在リスクが高い（Riskが警戒）",
    "Constraint": "予算/稼働/必須スキルの制約で成立しない",
}


def detect_pattern(
    project: dict[str, Any],
    team: list[dict[str, Any]],
    metrics: dict[str, int],
    votes: dict[str, Vote],
) -> str:
    if not team:
        return "Constraint"

    if metrics["skillFitPct"] < 50 or metrics["budgetPct"] > 120:
        return "Constraint"

    if votes["pm"] == votes["hr"] == votes["risk"] == "ok":
        return "Unanimous"

    notes = " ".join(str(m.get("notes") or "") for m in team)
    has_burnout = any(w in notes for w in ("疲労", "飽き", "燃え尽き"))
    has_hidden = any(w in notes for w in ("噂", "対人トラブル"))
    if has_burnout and votes["pm"] == "ok" and (votes["hr"] == "ng" or votes["risk"] == "ng"):
        return "Burnout"
    if has_hidden and votes["risk"] == "ng" and votes["pm"] == "ok":
        return "HiddenBomb"

    high_cost = any(int(m.get("cost") or 0) >= 110 for m in team)
    low_avail = any(int(m.get("availability") or 0) <= 30 for m in team)
    if (high_cost or low_avail) and votes["pm"] == "ng" and votes["hr"] == "ok":
        return "HighFlyer"

    if votes["pm"] == "ng" and votes["hr"] == "ok" and votes["risk"] != "ng":
        return "DiamondInTheRough"

    return "HiddenBomb" if metrics["riskPct"] >= 70 else "HighFlyer"

