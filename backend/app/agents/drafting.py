from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.drafting")


@dataclass(frozen=True)
class DraftingResult:
    email_draft: str
    approval_doc: str
    email_payload: dict[str, Any]
    raw: dict[str, Any]


def generate_drafts(context: dict[str, Any]) -> DraftingResult:
    system_prompt = (
        "You are an assistant who drafts client emails and HR approval documents. "
        "Return only JSON with keys: email_draft, approval_doc, email_payload. "
        "email_payload must include to, subject, body."
    )
    prompt = (
        "Draft the outputs based on the context. Return JSON only.\n\n"
        f"[Context]\n{context}"
    )
    try:
        payload = invoke_json(prompt, system_prompt=system_prompt, retries=1)
    except BedrockInvocationError:
        logger.exception("drafting Bedrock invocation failed")
        raise

    if not isinstance(payload, dict):
        raise BedrockInvocationError("drafting returned non-object JSON")

    email_draft = str(payload.get("email_draft") or "").strip()
    approval_doc = str(payload.get("approval_doc") or "").strip()
    email_payload = payload.get("email_payload")
    if not isinstance(email_payload, dict):
        email_payload = {}

    if not email_draft:
        email_draft = "Subject: Follow-up\n\nWe will coordinate next steps and provide updates."
    if not approval_doc:
        approval_doc = "HR approval request draft pending details."

    email_payload.setdefault("subject", "Follow-up")
    email_payload.setdefault("body", email_draft)

    return DraftingResult(
        email_draft=email_draft,
        approval_doc=approval_doc,
        email_payload=email_payload,
        raw=payload,
    )
