from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from app.auth import AuthUser, get_current_user
from app.db import get_db
from app.db.repository import upsert_google_oauth_token
from app.integrations.google_calendar import (
    build_google_oauth_url,
    exchange_code_for_token,
    fetch_google_user_info,
    parse_google_oauth_state,
)


router = APIRouter(prefix="/v1/integrations/google", tags=["integrations"])


class GoogleOAuthStartResponse(BaseModel):
    authUrl: str


class GoogleOAuthCallbackResponse(BaseModel):
    status: str
    email: str
    scope: str | None = None


@router.get("/oauth/start", response_model=GoogleOAuthStartResponse)
def google_oauth_start(user: AuthUser = Depends(get_current_user)) -> GoogleOAuthStartResponse:
    try:
        auth_url = build_google_oauth_url(user.user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GoogleOAuthStartResponse(authUrl=auth_url)


@router.get("/oauth/callback", response_model=GoogleOAuthCallbackResponse)
def google_oauth_callback(
    code: str,
    state: str,
    conn: Connection = Depends(get_db),
) -> GoogleOAuthCallbackResponse:
    try:
        user_id = parse_google_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token_response = exchange_code_for_token(code)
    access_token = token_response.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="google oauth token missing access_token")

    user_info = fetch_google_user_info(str(access_token))
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=502, detail="google oauth userinfo missing email")

    expires_in = token_response.get("expires_in")
    expires_at = None
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    try:
        upsert_google_oauth_token(
            conn,
            user_id=user_id,
            google_email=str(email),
            access_token=str(access_token),
            refresh_token=token_response.get("refresh_token"),
            token_type=token_response.get("token_type"),
            scope=token_response.get("scope"),
            expires_at=expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return GoogleOAuthCallbackResponse(
        status="linked",
        email=str(email),
        scope=token_response.get("scope"),
    )
