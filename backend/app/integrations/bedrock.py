from __future__ import annotations

import json
import logging
import os
import re
import threading
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


_bedrock_logger = logging.getLogger("saihai.bedrock")
_client_cache: dict[tuple[str, int | None, int | None, int | None, str | None], Any] = {}
_client_cache_lock = threading.Lock()


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _optional_int(name: str, *, min_value: int | None = None) -> int | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        _bedrock_logger.warning("Invalid %s=%s (expected int); ignoring.", name, raw)
        return None
    if min_value is not None and value < min_value:
        _bedrock_logger.warning("Invalid %s=%s (min %s); ignoring.", name, raw, min_value)
        return None
    return value


def _bedrock_client_settings() -> tuple[int | None, int | None, int | None, str | None]:
    connect_timeout_ms = _optional_int("BEDROCK_CONNECT_TIMEOUT_MS", min_value=1)
    read_timeout_ms = _optional_int("BEDROCK_READ_TIMEOUT_MS", min_value=1)
    max_attempts = _optional_int("BEDROCK_MAX_ATTEMPTS", min_value=1)
    retry_mode = _env("BEDROCK_RETRY_MODE") or None
    return connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode


def _build_bedrock_client(region: str) -> tuple[Any, bool, tuple[int | None, int | None, int | None, str | None]]:
    connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode = _bedrock_client_settings()
    cache_key = (region, connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode)
    with _client_cache_lock:
        cached = _client_cache.get(cache_key)
    if cached is not None:
        return cached, True, (connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode)

    config = None
    config_kwargs: dict[str, Any] = {}
    if connect_timeout_ms is not None:
        config_kwargs["connect_timeout"] = connect_timeout_ms / 1000.0
    if read_timeout_ms is not None:
        config_kwargs["read_timeout"] = read_timeout_ms / 1000.0
    retries: dict[str, Any] = {}
    if max_attempts is not None:
        retries["max_attempts"] = max_attempts
    if retry_mode:
        retries["mode"] = retry_mode
    if retries:
        config_kwargs["retries"] = retries

    if config_kwargs:
        try:
            from botocore.config import Config  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on runtime
            raise BedrockDependencyError("Missing dependency: botocore") from exc
        config = Config(**config_kwargs)

    import boto3  # type: ignore

    client = boto3.client("bedrock-runtime", region_name=region, config=config)
    with _client_cache_lock:
        cached = _client_cache.get(cache_key)
        if cached is not None:
            return cached, True, (connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode)
        _client_cache[cache_key] = client
    return client, False, (connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode)


def _clear_bedrock_client_cache() -> None:
    with _client_cache_lock:
        _client_cache.clear()


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
    total_started = time.perf_counter()
    model_id = bedrock_invoke_id()
    region = bedrock_region()
    if not model_id or not region:
        raise BedrockNotConfiguredError(
            "Set AWS_REGION (or AWS_DEFAULT_REGION) and AWS_BEDROCK_MODEL_ID (or AWS_BEDROCK_INFERENCE_PROFILE_ID)."
        )

    prompt_chars = len(prompt or "")
    system_chars = len(system_prompt or "")
    client_ms = 0.0
    bedrock_call_ms = 0.0
    parse_ms = 0.0
    response_bytes: int | None = None
    response_chars: int | None = None
    attempts = 1
    fallback_used = False
    operation = "unknown"
    client_reused = False
    connect_timeout_ms: int | None = None
    read_timeout_ms: int | None = None
    max_attempts: int | None = None
    retry_mode: str | None = None
    effective_model_id = model_id
    error_kind = "-"
    error_message = "-"
    request_started = None

    try:
        client_started = time.perf_counter()
        try:
            client, client_reused, client_settings = _build_bedrock_client(region)
        except ModuleNotFoundError as exc:
            raise BedrockDependencyError("Missing dependency: boto3") from exc
        client_ms = (time.perf_counter() - client_started) * 1000
        connect_timeout_ms, read_timeout_ms, max_attempts, retry_mode = client_settings

        if hasattr(client, "converse"):
            operation = "converse"
            request_started = time.perf_counter()
            system: list[dict[str, Any]] = []
            if system_prompt:
                system.append({"text": system_prompt})

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
                        attempts = 2
                        fallback_used = True
                    except Exception as retry_exc:  # pragma: no cover - depends on AWS credentials/runtime
                        raise BedrockInvocationError(
                            _with_inference_profile_hint(error_message, model_id=effective_model_id)
                        ) from retry_exc
                else:
                    raise BedrockInvocationError(
                        _with_inference_profile_hint(error_message, model_id=effective_model_id)
                    ) from exc

            bedrock_call_ms = (time.perf_counter() - request_started) * 1000
            parse_started = time.perf_counter()
            try:
                content = response["output"]["message"]["content"]
                chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
                text = "".join(chunks).strip()
            except Exception as exc:
                raise BedrockInvocationError(f"Unexpected Bedrock response shape: {exc}") from exc
            parse_ms = (time.perf_counter() - parse_started) * 1000
            response_chars = len(text)
            return BedrockInvokeResult(provider="bedrock", model_id=effective_model_id, text=text)

        if not hasattr(client, "invoke_model"):
            raise BedrockInvocationError("boto3 bedrock-runtime client does not support converse() or invoke_model().")

        operation = "invoke_model"
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

        request_started = time.perf_counter()
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
                    attempts = 2
                    fallback_used = True
                except Exception as retry_exc:  # pragma: no cover - depends on AWS credentials/runtime
                    raise BedrockInvocationError(
                        _with_inference_profile_hint(error_message, model_id=effective_model_id)
                    ) from retry_exc
            else:
                raise BedrockInvocationError(_with_inference_profile_hint(error_message, model_id=effective_model_id)) from exc

        bedrock_call_ms = (time.perf_counter() - request_started) * 1000
        parse_started = time.perf_counter()
        try:
            body = response.get("body")
            raw = body.read() if hasattr(body, "read") else body
            if isinstance(raw, (bytes, bytearray)):
                response_bytes = len(raw)
                raw = raw.decode("utf-8")
            elif isinstance(raw, str):
                response_bytes = len(raw.encode("utf-8"))
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
        parse_ms = (time.perf_counter() - parse_started) * 1000
        response_chars = len(text)
        return BedrockInvokeResult(provider="bedrock", model_id=effective_model_id, text=text)
    except Exception as exc:
        error_kind = type(exc).__name__
        error_message = str(exc)
        raise
    finally:
        total_ms = (time.perf_counter() - total_started) * 1000
        if request_started is None:
            request_started = total_started
        if bedrock_call_ms <= 0:
            bedrock_call_ms = (time.perf_counter() - request_started) * 1000
        log_level = logging.INFO if error_kind == "-" else logging.WARNING
        _bedrock_logger.log(
            log_level,
            "bedrock.invoke result=%s region=%s model_id=%s effective_model_id=%s operation=%s attempts=%s "
            "fallback=%s prompt_chars=%s system_chars=%s response_chars=%s response_bytes=%s "
            "client_reused=%s client_ms=%.1f bedrock_ms=%.1f parse_ms=%.1f total_ms=%.1f "
            "connect_timeout_ms=%s read_timeout_ms=%s max_attempts=%s retry_mode=%s error=%s error_message=%s",
            "ok" if error_kind == "-" else "error",
            region,
            model_id,
            effective_model_id,
            operation,
            attempts,
            fallback_used,
            prompt_chars,
            system_chars,
            response_chars,
            response_bytes,
            client_reused,
            client_ms,
            bedrock_call_ms,
            parse_ms,
            total_ms,
            connect_timeout_ms,
            read_timeout_ms,
            max_attempts,
            retry_mode,
            error_kind,
            error_message,
        )


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
            _bedrock_logger.warning(
                "bedrock.json_parse_retry attempt=%s retries=%s prompt_chars=%s system_chars=%s response_chars=%s error=%s",
                attempt + 1,
                retries,
                len(current_prompt or ""),
                len(current_system or ""),
                len(result.text or ""),
                str(exc),
            )
            current_system = (current_system or "") + "\nReturn only valid JSON. No prose."
            time.sleep(retry_delay)
    raise BedrockInvocationError(f"Failed to parse JSON: {last_error}") from last_error
