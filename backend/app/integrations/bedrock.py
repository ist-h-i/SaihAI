from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any


class BedrockError(RuntimeError):
    pass


class BedrockNotConfiguredError(BedrockError):
    pass


class BedrockDependencyError(BedrockError):
    pass


class BedrockInvocationError(BedrockError):
    pass


@dataclass(frozen=True)
class BedrockInvokeResult:
    provider: str
    model_id: str | None
    text: str


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def bedrock_model_id() -> str | None:
    model_id = _env("AWS_BEDROCK_MODEL_ID")
    return model_id or None


def bedrock_region() -> str | None:
    region = _env("AWS_REGION")
    return region or None


def is_bedrock_configured() -> bool:
    return bool(bedrock_model_id() and bedrock_region())


def invoke_bedrock_text(
    prompt: str,
    system_prompt: str | None = None,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> BedrockInvokeResult:
    model_id = bedrock_model_id()
    region = bedrock_region()
    if not model_id or not region:
        raise BedrockNotConfiguredError("Set AWS_REGION and AWS_BEDROCK_MODEL_ID.")

    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise BedrockDependencyError("Missing dependency: boto3") from exc

    client = boto3.client("bedrock-runtime", region_name=region)
    if not hasattr(client, "converse"):
        raise BedrockInvocationError("boto3 bedrock-runtime client does not support converse().")

    system: list[dict[str, Any]] = []
    if system_prompt:
        system.append({"text": system_prompt})

    try:
        response = client.converse(
            modelId=model_id,
            system=system,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on AWS credentials/runtime
        raise BedrockInvocationError(str(exc)) from exc

    try:
        content = response["output"]["message"]["content"]
        chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
        text = "".join(chunks).strip()
    except Exception as exc:
        raise BedrockInvocationError(f"Unexpected Bedrock response shape: {exc}") from exc

    return BedrockInvokeResult(provider="bedrock", model_id=model_id, text=text)


def invoke_text(
    prompt: str,
    system_prompt: str | None = None,
    *,
    allow_mock: bool = False,
) -> BedrockInvokeResult:
    if is_bedrock_configured():
        try:
            return invoke_bedrock_text(prompt, system_prompt=system_prompt)
        except BedrockError:
            raise
    raise BedrockNotConfiguredError("Bedrock is required and not configured.")


_JSON_FENCE_RE = re.compile(r"```(?:json)?\\s*(.*?)\\s*```", flags=re.DOTALL | re.IGNORECASE)


def extract_json_text(text: str) -> str:
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()

    stripped = text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1].strip()
    return stripped


def parse_json(text: str) -> Any:
    payload = extract_json_text(text)
    return json.loads(payload)


def invoke_json(
    prompt: str,
    system_prompt: str | None = None,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.2,
    retries: int = 1,
    retry_delay: float = 0.4,
) -> Any:
    last_error: Exception | None = None
    current_prompt = prompt
    current_system = system_prompt
    for attempt in range(retries + 1):
        result = invoke_bedrock_text(
            current_prompt,
            system_prompt=current_system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            return parse_json(result.text)
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt >= retries:
                break
            current_system = (current_system or "") + "\nReturn only valid JSON. No prose."
            time.sleep(retry_delay)
    raise BedrockInvocationError(f"Failed to parse JSON: {last_error}") from last_error

