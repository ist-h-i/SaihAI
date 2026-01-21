from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo


logger = logging.getLogger("saihai.google_calendar")

GOOGLE_OAUTH_AUTH_URL = os.getenv("GOOGLE_OAUTH_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
GOOGLE_OAUTH_TOKEN_URL = os.getenv("GOOGLE_OAUTH_TOKEN_URL", "https://oauth2.googleapis.com/token")
GOOGLE_OAUTH_USERINFO_URL = os.getenv(
    "GOOGLE_OAUTH_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo"
)
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
GOOGLE_OAUTH_SCOPES = os.getenv(
    "GOOGLE_OAUTH_SCOPES", "https://www.googleapis.com/auth/calendar.events"
)
GOOGLE_OAUTH_STATE_SECRET = os.getenv("GOOGLE_OAUTH_STATE_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
GOOGLE_OAUTH_STATE_TTL_SECONDS = int(os.getenv("GOOGLE_OAUTH_STATE_TTL_SECONDS", "600"))

GOOGLE_CALENDAR_API_BASE = os.getenv("GOOGLE_CALENDAR_API_BASE", "https://www.googleapis.com/calendar/v3")


class GoogleCalendarError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.details = details or {}


def _ensure_oauth_config() -> None:
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET or not GOOGLE_OAUTH_REDIRECT_URI:
        raise RuntimeError("Google OAuth client is not configured")


def _format_scopes(raw: str) -> str:
    tokens = [token for token in raw.replace(",", " ").split() if token.strip()]
    return " ".join(tokens)


def build_google_oauth_url(user_id: str) -> str:
    _ensure_oauth_config()
    state = _encode_state(user_id)
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": _format_scopes(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"


def parse_google_oauth_state(state: str) -> str:
    payload_b64, signature = _split_state(state)
    expected = _sign_state(payload_b64)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid oauth state")
    payload = _decode_state_payload(payload_b64)
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("invalid oauth state")
    issued_at = payload.get("iat")
    if isinstance(issued_at, (int, float)):
        now = datetime.now(timezone.utc).timestamp()
        if now - float(issued_at) > GOOGLE_OAUTH_STATE_TTL_SECONDS:
            raise ValueError("oauth state expired")
    return user_id


def exchange_code_for_token(code: str) -> dict[str, Any]:
    _ensure_oauth_config()
    payload = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    return _request_form(GOOGLE_OAUTH_TOKEN_URL, payload)


def refresh_google_access_token(refresh_token: str) -> dict[str, Any]:
    _ensure_oauth_config()
    payload = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    return _request_form(GOOGLE_OAUTH_TOKEN_URL, payload)


def fetch_google_user_info(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    return _request_json(GOOGLE_OAUTH_USERINFO_URL, headers=headers)


def create_google_calendar_event(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    calendar_id = _resolve_calendar_id(payload)
    payload = dict(payload)
    payload.pop("calendar_id", None)
    payload.pop("calendarId", None)
    meeting_url = str(payload.get("meeting_url") or payload.get("meetingUrl") or "").strip() or None
    include_conference = not meeting_url
    event = _build_event_payload(payload, include_conference=include_conference)
    try:
        return _insert_event(access_token, event, include_conference=include_conference, calendar_id=calendar_id)
    except GoogleCalendarError as exc:
        if not include_conference:
            raise
        logger.warning("Meet generation failed; retrying without conference data: %s", exc)
        event = _build_event_payload(payload, include_conference=False)
        return _insert_event(access_token, event, include_conference=False, calendar_id=calendar_id)


def _insert_event(
    access_token: str,
    event: dict[str, Any],
    *,
    include_conference: bool,
    calendar_id: str,
) -> dict[str, Any]:
    params = {"sendUpdates": "all"}
    if include_conference:
        params["conferenceDataVersion"] = "1"
    encoded_calendar_id = urllib.parse.quote(calendar_id, safe="")
    url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{encoded_calendar_id}/events?{urllib.parse.urlencode(params)}"
    headers = {"Authorization": f"Bearer {access_token}"}
    return _request_json(url, data=event, headers=headers, method="POST")


def _resolve_calendar_id(payload: dict[str, Any]) -> str:
    raw = payload.get("calendar_id") or payload.get("calendarId") or os.getenv("CALENDAR_ID") or "primary"
    value = str(raw or "").strip()
    return value or "primary"


def _build_event_payload(payload: dict[str, Any], *, include_conference: bool) -> dict[str, Any]:
    timezone_name = str(payload.get("timezone") or "Asia/Tokyo")
    start_at = _normalize_datetime(str(payload.get("start_at") or payload.get("startAt") or ""), timezone_name)
    end_at = _normalize_datetime(str(payload.get("end_at") or payload.get("endAt") or ""), timezone_name)

    description = payload.get("description")
    meeting_url = str(payload.get("meeting_url") or payload.get("meetingUrl") or "").strip() or None
    description = _merge_description(description, meeting_url)

    attendees = _collect_attendees(payload)
    event: dict[str, Any] = {
        "summary": str(payload.get("title") or ""),
        "start": {"dateTime": start_at.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end_at.isoformat(), "timeZone": timezone_name},
        "attendees": [{"email": email} for email in attendees],
    }
    if description:
        event["description"] = description

    if meeting_url:
        event["location"] = meeting_url
    if include_conference:
        event["conferenceData"] = {
            "createRequest": {
                "requestId": uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    return event


def _collect_attendees(payload: dict[str, Any]) -> list[str]:
    attendees: list[str] = []
    raw_attendees = payload.get("attendees")
    if isinstance(raw_attendees, list):
        attendees.extend([str(item) for item in raw_attendees if str(item).strip()])
    raw_attendee = payload.get("attendee")
    if raw_attendee and str(raw_attendee).strip():
        attendees.append(str(raw_attendee).strip())
    unique: list[str] = []
    seen: set[str] = set()
    for email in attendees:
        lowered = email.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(email)
    return unique


def _merge_description(description: Any, meeting_url: str | None) -> str | None:
    base = str(description).strip() if description else ""
    if not meeting_url:
        return base or None
    if meeting_url in base:
        return base
    line = f"Meeting URL: {meeting_url}"
    if base:
        return f"{base}\n\n{line}"
    return line


def _normalize_datetime(value: str, timezone_name: str) -> datetime:
    if not value:
        raise ValueError("missing datetime value")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("invalid datetime value") from exc
        dt = datetime.combine(parsed_date, time.min)

    tz = ZoneInfo(timezone_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _request_form(url: str, payload: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    return _request_raw(url, data=data, headers=headers)


def _request_json(
    url: str,
    *,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    headers = dict(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json; charset=utf-8")
    return _request_raw(url, data=body, headers=headers, method=method, timeout=timeout)


def _request_raw(
    url: str,
    *,
    data: bytes | None,
    headers: dict[str, str],
    method: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return _parse_json_response(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        details = _safe_parse_json(body)
        message = details.get("error_description") or details.get("error") or body or str(exc)
        raise GoogleCalendarError(message, status=exc.code, details=details) from exc
    except urllib.error.URLError as exc:
        raise GoogleCalendarError(f"connection error: {exc}") from exc


def _parse_json_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    text = raw.decode("utf-8")
    data = _safe_parse_json(text)
    if isinstance(data, dict):
        return data
    raise GoogleCalendarError("unexpected response from Google API", details={"raw": text})


def _safe_parse_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"raw": raw}


def _encode_state(user_id: str) -> str:
    payload = json.dumps(
        {"sub": user_id, "iat": int(datetime.now(timezone.utc).timestamp())}, separators=(",", ":")
    ).encode("utf-8")
    payload_b64 = _b64url_encode(payload)
    signature = _sign_state(payload_b64)
    return f"{payload_b64}.{signature}"


def _split_state(state: str) -> tuple[str, str]:
    parts = state.split(".", 1)
    if len(parts) != 2:
        raise ValueError("invalid oauth state")
    return parts[0], parts[1]


def _decode_state_payload(payload_b64: str) -> dict[str, Any]:
    raw = _b64url_decode(payload_b64)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid oauth state") from exc
    if isinstance(payload, dict):
        return payload
    raise ValueError("invalid oauth state")


def _sign_state(payload_b64: str) -> str:
    digest = hmac.new(GOOGLE_OAUTH_STATE_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    return _b64url_encode(digest.digest())


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)
