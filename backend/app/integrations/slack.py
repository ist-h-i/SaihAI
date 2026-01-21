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
SLACK_WEBHOOK_URL = _clean_env("SLACK_WEBHOOK_URL")
SLACK_REQUEST_TTL_SECONDS = int(os.getenv("SLACK_REQUEST_TTL_SECONDS", "300"))
SLACK_ALLOW_UNSIGNED = os.getenv("SLACK_ALLOW_UNSIGNED", "").lower() in {"1", "true", "yes"}


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


def _post_slack_api(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not SLACK_BOT_TOKEN:
        return None

    send_payload = dict(payload)
    if not send_payload.get("channel"):
        if not SLACK_DEFAULT_CHANNEL:
            return None
        send_payload["channel"] = SLACK_DEFAULT_CHANNEL

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
