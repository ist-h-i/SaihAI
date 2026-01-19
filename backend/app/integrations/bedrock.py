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


def bedrock_inference_profile_id() -> str | None:
    profile_id = _env("AWS_BEDROCK_INFERENCE_PROFILE_ID") or _env("AWS_BEDROCK_INFERENCE_PROFILE_ARN")
    return profile_id or None


def bedrock_invoke_id() -> str | None:
    return bedrock_inference_profile_id() or bedrock_model_id()


def bedrock_region() -> str | None:
    region = _env("AWS_REGION") or _env("AWS_DEFAULT_REGION")
    return region or None


def is_bedrock_configured() -> bool:
    return bool(bedrock_invoke_id() and bedrock_region())


_ON_DEMAND_THROUGHPUT_UNSUPPORTED_RE = re.compile(
    r"on-demand throughput\s+isn['’]?t supported",
    flags=re.IGNORECASE,
)


_SYSTEM_INFERENCE_PROFILE_PREFIXES = ("global.", "us.", "eu.", "apac.")


def _should_try_global_inference_profile(model_id: str) -> bool:
    if not model_id or model_id.startswith("arn:"):
        return False
    if model_id.startswith(_SYSTEM_INFERENCE_PROFILE_PREFIXES):
        return False
    return ":" in model_id and "." in model_id


def _with_inference_profile_hint(message: str, *, model_id: str | None = None) -> str:
    if not _ON_DEMAND_THROUGHPUT_UNSUPPORTED_RE.search(message):
        return message
    hint = (
        "Hint: This model cannot be invoked with on-demand throughput. "
        "Create/use an inference profile that contains this model and set AWS_BEDROCK_INFERENCE_PROFILE_ID "
        "(or AWS_BEDROCK_INFERENCE_PROFILE_ARN)."
    )
    if model_id and _should_try_global_inference_profile(model_id):
        hint = (
            hint
            + f" For system-defined inference profiles, try setting AWS_BEDROCK_MODEL_ID=global.{model_id} "
            f"or AWS_BEDROCK_INFERENCE_PROFILE_ID=global.{model_id}."
        )
    return (
        f"{message}\n"
        f"{hint}"
    )


def invoke_bedrock_text(
    prompt: str,
    system_prompt: str | None = None,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> BedrockInvokeResult:
    model_id = bedrock_invoke_id()
    region = bedrock_region()
    if not model_id or not region:
        raise BedrockNotConfiguredError(
            "Set AWS_REGION (or AWS_DEFAULT_REGION) and AWS_BEDROCK_MODEL_ID (or AWS_BEDROCK_INFERENCE_PROFILE_ID)."
        )

    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise BedrockDependencyError("Missing dependency: boto3") from exc

    client = boto3.client("bedrock-runtime", region_name=region)
    if hasattr(client, "converse"):
        system: list[dict[str, Any]] = []
        if system_prompt:
            system.append({"text": system_prompt})

        effective_model_id = model_id
        try:
            response = client.converse(
                modelId=effective_model_id,
                system=system,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
            )
        except Exception as exc:  # pragma: no cover - depends on AWS credentials/runtime
            error_message = str(exc)
            if _ON_DEMAND_THROUGHPUT_UNSUPPORTED_RE.search(error_message) and _should_try_global_inference_profile(
                effective_model_id
            ):
                fallback_model_id = f"global.{effective_model_id}"
                try:
                    response = client.converse(
                        modelId=fallback_model_id,
                        system=system,
                        messages=[{"role": "user", "content": [{"text": prompt}]}],
                        inferenceConfig={
                            "maxTokens": max_tokens,
                            "temperature": temperature,
                        },
                    )
                    effective_model_id = fallback_model_id
                except Exception as retry_exc:  # pragma: no cover - depends on AWS credentials/runtime
                    raise BedrockInvocationError(
                        _with_inference_profile_hint(error_message, model_id=effective_model_id)
                    ) from retry_exc
            else:
                raise BedrockInvocationError(_with_inference_profile_hint(error_message, model_id=effective_model_id)) from exc

        try:
            content = response["output"]["message"]["content"]
            chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
            text = "".join(chunks).strip()
        except Exception as exc:
            raise BedrockInvocationError(f"Unexpected Bedrock response shape: {exc}") from exc

        return BedrockInvokeResult(provider="bedrock", model_id=effective_model_id, text=text)

    if not hasattr(client, "invoke_model"):
        raise BedrockInvocationError("boto3 bedrock-runtime client does not support converse() or invoke_model().")

    request_body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    }
    if system_prompt:
        request_body["system"] = system_prompt

    effective_model_id = model_id
    try:
        response = client.invoke_model(
            modelId=effective_model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )
    except Exception as exc:  # pragma: no cover - depends on AWS credentials/runtime
        error_message = str(exc)
        if _ON_DEMAND_THROUGHPUT_UNSUPPORTED_RE.search(error_message) and _should_try_global_inference_profile(
            effective_model_id
        ):
            fallback_model_id = f"global.{effective_model_id}"
            try:
                response = client.invoke_model(
                    modelId=fallback_model_id,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json",
                )
                effective_model_id = fallback_model_id
            except Exception as retry_exc:  # pragma: no cover - depends on AWS credentials/runtime
                raise BedrockInvocationError(_with_inference_profile_hint(error_message, model_id=effective_model_id)) from retry_exc
        else:
            raise BedrockInvocationError(_with_inference_profile_hint(error_message, model_id=effective_model_id)) from exc

    try:
        body = response.get("body")
        raw = body.read() if hasattr(body, "read") else body
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        result = json.loads(raw or "{}")

        text = ""
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list):
                chunks = [
                    str(part.get("text") or "")
                    for part in content
                    if isinstance(part, dict) and str(part.get("text") or "").strip()
                ]
                text = "".join(chunks).strip()

            if not text:
                completion = result.get("completion") or result.get("generation")
                if isinstance(completion, str):
                    text = completion.strip()

            if not text:
                output = result.get("output")
                if isinstance(output, dict):
                    message = output.get("message")
                    if isinstance(message, dict) and isinstance(message.get("content"), list):
                        chunks = [
                            str(part.get("text") or "")
                            for part in message["content"]
                            if isinstance(part, dict) and str(part.get("text") or "").strip()
                        ]
                        text = "".join(chunks).strip()
        else:
            text = str(result).strip()
    except Exception as exc:
        raise BedrockInvocationError(f"Unexpected Bedrock invoke_model response shape: {exc}") from exc

    return BedrockInvokeResult(provider="bedrock", model_id=effective_model_id, text=text)


def invoke_text(
    prompt: str,
    system_prompt: str | None = None,
    *,
    allow_mock: bool = False,
) -> BedrockInvokeResult:
    if is_bedrock_configured():
        return invoke_bedrock_text(prompt, system_prompt=system_prompt)

    if allow_mock:
        wants_json = bool(re.search(r"\bjson\b", prompt, flags=re.IGNORECASE)) or ("{" in prompt and "}" in prompt)
        if wants_json:
            text = json.dumps({"ok": True, "provider": "mock"}, ensure_ascii=False)
        else:
            text = "mock response (Bedrock is not configured)"
        return BedrockInvokeResult(provider="mock", model_id=None, text=text)

    raise BedrockNotConfiguredError(
        "Bedrock is required and not configured. Set AWS_REGION (or AWS_DEFAULT_REGION) and AWS_BEDROCK_MODEL_ID "
        "(or AWS_BEDROCK_INFERENCE_PROFILE_ID). Auth uses boto3 credential resolution (e.g., AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)."
    )


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
