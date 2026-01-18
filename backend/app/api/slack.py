from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import db_connection
from app.domain.hitl import apply_steer, approve_request, reject_request
from app.integrations.slack import (
    parse_action_value,
    parse_interaction_payload,
    post_thread_message,
    verify_slack_signature,
)

router = APIRouter(prefix="/slack", tags=["slack"])
logger = logging.getLogger("saihai.slack")


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    body = await request.body()
    if not verify_slack_signature(body, request.headers):
        raise HTTPException(status_code=401, detail="invalid slack signature")

    payload = parse_interaction_payload(body)
    if not payload:
        return JSONResponse({"ok": True})

    actions = payload.get("actions") or []
    if not actions:
        return JSONResponse({"ok": True})

    action = actions[0]
    action_id = action.get("action_id")
    value = action.get("value") or ""
    metadata = parse_action_value(value)
    approval_request_id = metadata.get("approval_request_id")
    action_ref = metadata.get("action_id")
    actor = payload.get("user", {}).get("id")
    idempotency_key = _interaction_idempotency_key(payload, action, approval_request_id, action_id)

    if not approval_request_id:
        return JSONResponse({"ok": True})

    if action_id == "hitl_approve":
        background_tasks.add_task(
            _handle_interaction,
            approval_request_id=approval_request_id,
            action_id=action_id,
            actor=actor,
            idempotency_key=idempotency_key,
        )
        return JSONResponse({"text": "approved"})
    if action_id == "hitl_reject":
        background_tasks.add_task(
            _handle_interaction,
            approval_request_id=approval_request_id,
            action_id=action_id,
            actor=actor,
            idempotency_key=idempotency_key,
        )
        return JSONResponse({"text": "rejected"})
    if action_id == "hitl_request_changes":
        background_tasks.add_task(
            _handle_interaction,
            approval_request_id=approval_request_id,
            action_id=action_id,
            actor=actor,
            idempotency_key=idempotency_key or f"slack:{approval_request_id}:request_changes",
        )
        return JSONResponse({"text": "request changes"})

    return JSONResponse({"ok": True, "action_id": action_id, "action_ref": action_ref})


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    body = await request.body()
    if not verify_slack_signature(body, request.headers):
        raise HTTPException(status_code=401, detail="invalid slack signature")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge")})

    event = payload.get("event") or {}
    if event.get("type") != "message" or event.get("subtype"):
        return JSONResponse({"ok": True})

    text_value = (event.get("text") or "").strip()
    if not text_value:
        return JSONResponse({"ok": True})

    thread_ts = event.get("thread_ts") or event.get("ts")
    if not thread_ts:
        return JSONResponse({"ok": True})

    background_tasks.add_task(_handle_event, payload)

    return JSONResponse({"ok": True})


def _handle_interaction(
    *,
    approval_request_id: str,
    action_id: str | None,
    actor: str | None,
    idempotency_key: str | None,
) -> None:
    logger.info(
        "slack interaction action_id=%s approval_request_id=%s",
        action_id,
        approval_request_id,
    )
    with db_connection() as conn:
        if action_id == "hitl_approve":
            approve_request(conn, approval_request_id, actor, idempotency_key=idempotency_key)
            return
        if action_id == "hitl_reject":
            reject_request(conn, approval_request_id, actor, idempotency_key=idempotency_key)
            return
        if action_id == "hitl_request_changes":
            apply_steer(
                conn,
                approval_request_id=approval_request_id,
                actor=actor,
                feedback="request_changes",
                idempotency_key=idempotency_key,
            )


def _handle_event(payload: dict) -> None:
    event = payload.get("event") or {}
    text_value = (event.get("text") or "").strip()
    thread_ts = event.get("thread_ts") or event.get("ts")
    if not text_value or not thread_ts:
        return
    logger.info("slack event thread_ts=%s event_id=%s", thread_ts, payload.get("event_id"))
    with db_connection() as conn:
        approval = _find_approval_by_thread(conn, thread_ts)
        if not approval:
            return

        selected_plan = _parse_plan(text_value)
        if not selected_plan and not _contains_action_keyword(text_value):
            channel = event.get("channel")
            post_thread_message(
                channel=str(channel) if channel else "",
                thread_ts=thread_ts,
                text="対象が不明です。メール/カレンダー/稟議のどれを調整しますか？",
            )
            return

        apply_steer(
            conn,
            approval_request_id=approval["approval_request_id"],
            actor=event.get("user"),
            feedback=text_value,
            selected_plan=selected_plan,
            idempotency_key=payload.get("event_id") or f"slack-event:{thread_ts}",
        )


def _find_approval_by_thread(conn: Connection, thread_ts: str) -> dict | None:
    rows = conn.execute(
        text("SELECT metadata FROM langgraph_checkpoints")
    ).mappings().all()
    for row in rows:
        metadata = row.get("metadata")
        if isinstance(metadata, (bytes, bytearray, memoryview)):
            try:
                metadata = metadata.decode("utf-8")
            except UnicodeDecodeError:
                continue
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                continue
        if not isinstance(metadata, dict):
            continue
        slack = metadata.get("slack") or {}
        if slack.get("thread_ts") == thread_ts or slack.get("message_ts") == thread_ts:
            approval_request_id = metadata.get("approval_request_id")
            if approval_request_id:
                return {"approval_request_id": approval_request_id}
    return None


def _parse_plan(text_value: str) -> str | None:
    lowered = text_value.lower()
    if "plan a" in lowered or "プランa" in text_value or "a案" in text_value:
        return "A"
    if "plan b" in lowered or "プランb" in text_value or "b案" in text_value:
        return "B"
    if "plan c" in lowered or "プランc" in text_value or "c案" in text_value:
        return "C"
    return None


def _contains_action_keyword(text_value: str) -> bool:
    lowered = text_value.lower()
    keywords = [
        "mail",
        "email",
        "メール",
        "カレンダー",
        "calendar",
        "meeting",
        "会議",
        "稟議",
        "承認",
    ]
    return any(key in lowered or key in text_value for key in keywords)


def _interaction_idempotency_key(
    payload: dict,
    action: dict,
    approval_request_id: str | None,
    action_id: str | None,
) -> str | None:
    if not approval_request_id or not action_id:
        return None
    action_ts = action.get("action_ts") or payload.get("action_ts")
    message_ts = payload.get("message", {}).get("ts")
    fallback = action_ts or message_ts or "unknown"
    return f"slack-interaction:{fallback}:{approval_request_id}:{action_id}"
