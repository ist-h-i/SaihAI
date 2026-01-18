from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.integrations.bedrock import (
    BedrockError,
    BedrockInvokeResult,
    bedrock_model_id,
    bedrock_region,
    invoke_text,
)


router = APIRouter(prefix="/v1", tags=["bedrock"])


class BedrockStatusResponse(BaseModel):
    configured: bool
    region: str | None = None
    model_id: str | None = None


class BedrockInvokeRequest(BaseModel):
    prompt: str = Field(min_length=1)
    systemPrompt: str | None = None
    allowMock: bool = False


class BedrockInvokeResponse(BaseModel):
    provider: str
    model_id: str | None = None
    text: str


@router.get("/bedrock/status", response_model=BedrockStatusResponse, dependencies=[Depends(get_current_user)])
def bedrock_status() -> BedrockStatusResponse:
    region = bedrock_region()
    model_id = bedrock_model_id()
    return BedrockStatusResponse(configured=bool(region and model_id), region=region, model_id=model_id)


@router.post("/bedrock/invoke", response_model=BedrockInvokeResponse, dependencies=[Depends(get_current_user)])
def bedrock_invoke(req: BedrockInvokeRequest) -> BedrockInvokeResponse:
    try:
        result: BedrockInvokeResult = invoke_text(
            req.prompt,
            system_prompt=req.systemPrompt,
            allow_mock=False,
        )
    except BedrockError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BedrockInvokeResponse(provider=result.provider, model_id=result.model_id, text=result.text)

