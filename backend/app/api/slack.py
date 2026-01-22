from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import db_connection
from app.domain.demo import (
    approve_demo,
    cancel_demo,
    record_demo_intervention,
    record_demo_plan_selection,
    reject_demo,
)
from app.domain.hitl import apply_steer, approve_request, reject_request
from app.integrations.slack import (
    DEMO_ACTION_APPROVE,
    DEMO_ACTION_CANCEL,
    DEMO_ACTION_INTERVENE,
    DEMO_ACTION_PLAN,
    DEMO_ACTION_REJECT,
    DEMO_MODAL_ACTION_ID,
    DEMO_MODAL_BLOCK_ID,
    DEMO_MODAL_CALLBACK_ID,
    open_demo_intervention_modal,
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

    payload_type = payload.get("type")
    if payload_type == "view_submission":
        view = payload.get("view") or {}
        if view.get("callback_id") == DEMO_MODAL_CALLBACK_ID:
            alert_id = (view.get("private_metadata") or "").strip()
            state_values = view.get("state", {}).get("values", {})
            intervention_value = ""
            if isinstance(state_values, dict):
                block = state_values.get(DEMO_MODAL_BLOCK_ID) or {}
                if isinstance(block, dict):
                    intervention_value = (block.get(DEMO_MODAL_ACTION_ID, {}) or {}).get("value", "")
            if alert_id and intervention_value:
                background_tasks.add_task(
                    record_demo_intervention,
                    alert_id=alert_id,
                    actor=payload.get("user", {}).get("id"),
                    intervention=intervention_value,
                    idempotency_key=_demo_idempotency_key(payload, None, alert_id, "view_submission"),
                )
            return JSONResponse({"response_action": "clear"})
        return JSONResponse({"ok": True})

    actions = payload.get("actions") or []
    if not actions:
        return JSONResponse({"ok": True})

    action = actions[0]
    action_id = action.get("action_id")
    value = action.get("value") or ""
    metadata = parse_action_value(value)
    alert_id = metadata.get("alert_id")

    if action_id in {
        DEMO_ACTION_PLAN,
        DEMO_ACTION_INTERVENE,
        DEMO_ACTION_APPROVE,
        DEMO_ACTION_REJECT,
        DEMO_ACTION_CANCEL,
    }:
        if action_id == DEMO_ACTION_INTERVENE:
            trigger_id = payload.get("trigger_id")
            if alert_id and trigger_id:
                open_demo_intervention_modal(str(trigger_id), alert_id)
            return JSONResponse({"ok": True})

        idempotency_key = _demo_idempotency_key(payload, action, alert_id, action_id)
        actor = payload.get("user", {}).get("id")
        if action_id == DEMO_ACTION_PLAN:
            plan = metadata.get("plan")
            if alert_id and plan:
                background_tasks.add_task(
                    record_demo_plan_selection,
                    alert_id=alert_id,
                    actor=actor,
                    plan=plan,
                    idempotency_key=idempotency_key,
                )
            return JSONResponse({"ok": True})
        if action_id == DEMO_ACTION_APPROVE:
            if alert_id:
                background_tasks.add_task(
                    approve_demo,
                    alert_id=alert_id,
                    actor=actor,
                    idempotency_key=idempotency_key,
                )
            return JSONResponse({"ok": True})
        if action_id == DEMO_ACTION_REJECT:
            if alert_id:
                background_tasks.add_task(
                    reject_demo,
                    alert_id=alert_id,
                    actor=actor,
                    idempotency_key=idempotency_key,
                )
            return JSONResponse({"ok": True})
        if action_id == DEMO_ACTION_CANCEL:
            if alert_id:
                background_tasks.add_task(
                    cancel_demo,
                    alert_id=alert_id,
                    actor=actor,
                    idempotency_key=idempotency_key,
                )
            return JSONResponse({"ok": True})

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


def _demo_idempotency_key(
    payload: dict,
    action: dict | None,
    alert_id: str | None,
    action_id: str | None,
) -> str | None:
    if not alert_id or not action_id:
        return None
    action_ts = None
    if action:
        action_ts = action.get("action_ts")
    action_ts = action_ts or payload.get("action_ts")
    message_ts = payload.get("message", {}).get("ts")
    trigger_id = payload.get("trigger_id")
    view_id = payload.get("view", {}).get("id")
    fallback = action_ts or message_ts or view_id or trigger_id or "unknown"
    return f"demo:{alert_id}:{action_id}:{fallback}"
