from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


def _clean_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value.upper() == "CHANGE_ME":
        return ""
    return value


SLACK_SIGNING_SECRET = _clean_env("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = _clean_env("SLACK_BOT_TOKEN")
SLACK_DEFAULT_CHANNEL = _clean_env("SLACK_DEFAULT_CHANNEL")
SLACK_DEMO_CHANNEL = _clean_env("SLACK_CHANNEL_ID")
SLACK_WEBHOOK_URL = _clean_env("SLACK_WEBHOOK_URL")
SLACK_REQUEST_TTL_SECONDS = int(os.getenv("SLACK_REQUEST_TTL_SECONDS", "300"))
SLACK_ALLOW_UNSIGNED = os.getenv("SLACK_ALLOW_UNSIGNED", "").lower() in {"1", "true", "yes"}

DEMO_ACTION_PLAN = "demo_plan_select"
DEMO_ACTION_INTERVENE = "demo_intervene"
DEMO_ACTION_APPROVE = "demo_approve"
DEMO_ACTION_REJECT = "demo_reject"
DEMO_ACTION_CANCEL = "demo_cancel"
DEMO_MODAL_CALLBACK_ID = "demo_intervention_modal"
DEMO_MODAL_BLOCK_ID = "demo_intervention"
DEMO_MODAL_ACTION_ID = "demo_intervention_text"


@dataclass
class SlackMeta:
    channel: str
    message_ts: str
    thread_ts: str | None = None


def verify_slack_signature(body: bytes, headers: Mapping[str, str]) -> bool:
    if not SLACK_SIGNING_SECRET:
        return SLACK_ALLOW_UNSIGNED

    timestamp = headers.get("x-slack-request-timestamp")
    signature = headers.get("x-slack-signature")
    if not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - ts) > SLACK_REQUEST_TTL_SECONDS:
        return False

    base = f"v0:{timestamp}:".encode("utf-8") + body
    digest = hmac.new(SLACK_SIGNING_SECRET.encode("utf-8"), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def parse_interaction_payload(body: bytes) -> dict[str, Any]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"))
    payload = parsed.get("payload", [""])[0]
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def build_action_value(thread_id: str, approval_request_id: str, action_id: int) -> str:
    parts = {
        "thread_id": thread_id,
        "approval_request_id": approval_request_id,
        "action_id": str(action_id),
    }
    return "|".join(f"{key}={value}" for key, value in parts.items())


def parse_action_value(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for chunk in value.split("|"):
        if "=" not in chunk:
            continue
        key, raw = chunk.split("=", 1)
        result[key] = raw
    return result


def build_demo_action_value(alert_id: str, **extra: str) -> str:
    parts: dict[str, str] = {"alert_id": alert_id}
    for key, value in extra.items():
        if value is None:
            continue
        parts[key] = str(value)
    return "|".join(f"{key}={value}" for key, value in parts.items())


def _call_slack_api(method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not SLACK_BOT_TOKEN:
        return None

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=data,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError:
        return None

    try:
        response_payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not response_payload.get("ok"):
        return None
    return response_payload


def _post_slack_api(payload: dict[str, Any]) -> dict[str, Any] | None:
    send_payload = dict(payload)
    if not send_payload.get("channel"):
        if not SLACK_DEFAULT_CHANNEL:
            return None
        send_payload["channel"] = SLACK_DEFAULT_CHANNEL
    return _call_slack_api("chat.postMessage", send_payload)

    data = json.dumps(send_payload).encode("utf-8")
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not payload.get("ok"):
        return None
    return payload


def _post_slack_webhook(payload: dict[str, Any]) -> bool:
    if not SLACK_WEBHOOK_URL:
        return False

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError:
        return False

    return body.strip().lower() == "ok"


def send_approval_message(
    action_id: int,
    approval_request_id: str,
    thread_id: str,
    summary: str | None,
    draft: str | None,
    *,
    channel: str | None = None,
    thread_ts: str | None = None,
) -> SlackMeta | None:
    target_channel = channel or SLACK_DEFAULT_CHANNEL

    title = summary or "Approval required"
    value = build_action_value(thread_id, approval_request_id, action_id)

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "SaihAI HITL Approval"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{title}*"},
        },
    ]
    if draft:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{draft}```"},
            }
        )
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "hitl_approve",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "value": value,
                },
                {
                    "type": "button",
                    "action_id": "hitl_reject",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "value": value,
                },
                {
                    "type": "button",
                    "action_id": "hitl_request_changes",
                    "text": {"type": "plain_text", "text": "Request changes"},
                    "value": value,
                },
            ],
        }
    )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"thread_id: `{thread_id}`"},
                {"type": "mrkdwn", "text": f"approval_id: `{approval_request_id}`"},
            ],
        }
    )

    payload: dict[str, Any] = {"text": title, "blocks": blocks}
    if target_channel:
        payload["channel"] = target_channel
    if thread_ts:
        payload["thread_ts"] = thread_ts
    response = _post_slack_api(payload)
    if response:
        resolved_channel = response.get("channel") or target_channel
        message_ts = response.get("ts") or response.get("message", {}).get("ts")
        if not message_ts or not resolved_channel:
            return None
        return SlackMeta(
            channel=resolved_channel,
            message_ts=message_ts,
            thread_ts=thread_ts or message_ts,
        )

    if _post_slack_webhook(payload):
        if thread_ts and target_channel:
            return SlackMeta(channel=target_channel, message_ts=thread_ts, thread_ts=thread_ts)
        return None

    return None


def post_thread_message(channel: str, thread_ts: str, text: str) -> None:
    if not channel or not thread_ts:
        return
    payload = {"channel": channel, "text": text, "thread_ts": thread_ts}
    if _post_slack_api(payload):
        return
    _post_slack_webhook(payload)


def post_thread_blocks(channel: str, thread_ts: str, text: str, blocks: list[dict[str, Any]]) -> None:
    if not channel or not thread_ts:
        return
    payload = {"channel": channel, "text": text, "thread_ts": thread_ts, "blocks": blocks}
    if _post_slack_api(payload):
        return
    _post_slack_webhook(payload)


def post_demo_alert(alert_id: str, *, channel: str | None = None) -> SlackMeta | None:
    target_channel = channel or SLACK_DEMO_CHANNEL or SLACK_DEFAULT_CHANNEL
    if not SLACK_BOT_TOKEN or not target_channel:
        return None

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": "SaihAI デモアラート"}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*疑似アラートが発生しました。*\nプランを選択するか、介入指示を入力してください。",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_PLAN,
                    "text": {"type": "plain_text", "text": "Plan A"},
                    "value": build_demo_action_value(alert_id, plan="A"),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_PLAN,
                    "text": {"type": "plain_text", "text": "Plan B (推奨)"},
                    "style": "primary",
                    "value": build_demo_action_value(alert_id, plan="B"),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_PLAN,
                    "text": {"type": "plain_text", "text": "Plan C"},
                    "value": build_demo_action_value(alert_id, plan="C"),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_INTERVENE,
                    "text": {"type": "plain_text", "text": "✋ 介入"},
                    "value": build_demo_action_value(alert_id),
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"alert_id: `{alert_id}`"},
            ],
        },
    ]

    payload: dict[str, Any] = {"text": "SaihAI demo alert", "blocks": blocks, "channel": target_channel}
    response = _post_slack_api(payload)
    if not response:
        return None
    resolved_channel = response.get("channel") or target_channel
    message_ts = response.get("ts") or response.get("message", {}).get("ts")
    if not message_ts or not resolved_channel:
        return None
    return SlackMeta(channel=resolved_channel, message_ts=message_ts, thread_ts=message_ts)


def post_demo_approval_prompt(
    channel: str,
    thread_ts: str,
    summary: str,
    alert_id: str,
) -> None:
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_APPROVE,
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "value": build_demo_action_value(alert_id),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_REJECT,
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "value": build_demo_action_value(alert_id),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_CANCEL,
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "value": build_demo_action_value(alert_id),
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"alert_id: `{alert_id}`"},
            ],
        },
    ]
    post_thread_blocks(channel, thread_ts, "Demo approval required", blocks)


def post_demo_retry_prompt(
    channel: str,
    thread_ts: str,
    alert_id: str,
    reason: str,
) -> None:
    message = f":warning: Google Calendar 作成に失敗しました。\n{reason}"
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": message}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_APPROVE,
                    "text": {"type": "plain_text", "text": "Retry"},
                    "style": "primary",
                    "value": build_demo_action_value(alert_id),
                },
                {
                    "type": "button",
                    "action_id": DEMO_ACTION_CANCEL,
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "value": build_demo_action_value(alert_id),
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"alert_id: `{alert_id}`"},
            ],
        },
    ]
    post_thread_blocks(channel, thread_ts, "Demo approval retry", blocks)


def open_demo_intervention_modal(trigger_id: str, alert_id: str) -> bool:
    if not trigger_id or not SLACK_BOT_TOKEN:
        return False

    view = {
        "type": "modal",
        "callback_id": DEMO_MODAL_CALLBACK_ID,
        "private_metadata": alert_id,
        "title": {"type": "plain_text", "text": "介入内容"},
        "submit": {"type": "plain_text", "text": "送信"},
        "close": {"type": "plain_text", "text": "キャンセル"},
        "blocks": [
            {
                "type": "input",
                "block_id": DEMO_MODAL_BLOCK_ID,
                "label": {"type": "plain_text", "text": "介入指示"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": DEMO_MODAL_ACTION_ID,
                    "multiline": True,
                    "max_length": 2000,
                },
            }
        ],
    }
    response = _call_slack_api("views.open", {"trigger_id": trigger_id, "view": view})
    return bool(response and response.get("ok"))
