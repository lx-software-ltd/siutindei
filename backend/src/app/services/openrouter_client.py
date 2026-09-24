"""OpenRouter chat completions via the AWS HTTP proxy.

In-VPC Lambdas must not call OpenRouter directly. All traffic goes
through ``http_invoke``. Requests are tagged as the hidden Siu Tin Dei
app so the shared LX Software invoice can group spend by product.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.services.aws_clients import get_secretsmanager_client
from app.services.aws_proxy import http_invoke
from app.services.secrets import SECRETS_CACHE_TTL_SECONDS
from app.utils.logging import get_logger

logger = get_logger(__name__)

_api_key_cache: tuple[str, float] | None = None
_model_cache: tuple[str, float] | None = None

_RETRYABLE_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_RETRYABLE_ENVELOPE_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SCHEDULE_SECONDS: tuple[float, ...] = (2.0, 4.0)
_MAX_RETRY_AFTER_SECONDS = 5.0
_MAX_FALLBACK_MODELS = 3

OPENROUTER_APP_ID = "siutindei"
OPENROUTER_APP_TITLE = "Siu Tin Dei"
OPENROUTER_APP_REFERER = "https://siutindei.com"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3-30b-a3b"

WORKLOAD_CATEGORY_SUGGESTION = "category-suggestion"
WORKLOAD_CATEGORY_SETTINGS_TEST = "category-settings-test"
WORKLOAD_JSON_REPAIR = "json-repair"

_WORKLOAD_SAFE_RE = re.compile(r"[^a-z0-9-]+")


class OpenRouterError(RuntimeError):
    """Transport or API failure talking to OpenRouter."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def require_env(name: str) -> str:
    """Return a required non-empty environment variable."""
    value = os.getenv(name, "").strip()
    if not value:
        raise OpenRouterError(f"{name} is not configured")
    return value


def attribution_headers() -> dict[str, str]:
    """Headers OpenRouter uses to split Activity by app."""
    return {
        "HTTP-Referer": OPENROUTER_APP_REFERER,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-Title": OPENROUTER_APP_TITLE,
        "X-OpenRouter-App-Visibility": "hidden",
    }


def attribution_user(workload: str) -> str:
    """Stable OpenRouter user id: ``siutindei:{workload}`` (no PII)."""
    raw = (workload or "").strip().lower()
    safe = _WORKLOAD_SAFE_RE.sub("-", raw)[:40].strip("-") or "unknown"
    return f"{OPENROUTER_APP_ID}:{safe}"


def clear_openrouter_caches() -> None:
    """Drop cached key and model (after settings save or in tests)."""
    global _api_key_cache, _model_cache
    _api_key_cache = None
    _model_cache = None


def clear_openrouter_model_cache() -> None:
    """Drop the in-process model cache after an admin settings save."""
    global _model_cache
    _model_cache = None


def get_openrouter_api_key() -> str:
    """Load and cache the OpenRouter API key from Secrets Manager."""
    global _api_key_cache
    now = time.monotonic()
    if _api_key_cache is not None:
        cached_value, loaded_at = _api_key_cache
        if now - loaded_at <= SECRETS_CACHE_TTL_SECONDS:
            return cached_value
    direct = os.getenv("OPENROUTER_API_KEY", "").strip()
    if direct:
        _api_key_cache = (direct, now)
        return direct
    secret_arn = require_env("OPENROUTER_API_KEY_SECRET_ARN")
    response = get_secretsmanager_client().get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string and response.get("SecretBinary"):
        secret_string = base64.b64decode(response["SecretBinary"]).decode("utf-8")
    if not secret_string:
        raise OpenRouterError("OpenRouter API key secret is empty")
    key = _extract_key(str(secret_string))
    _api_key_cache = (key, now)
    return key


def configured_model_name() -> str:
    """Return the admin-panel model, else env, else the Qwen default."""
    global _model_cache
    now = time.monotonic()
    if _model_cache is not None:
        cached_value, loaded_at = _model_cache
        if now - loaded_at <= SECRETS_CACHE_TTL_SECONDS:
            return cached_value
    stored = _load_settings_model()
    resolved = stored or os.getenv("OPENROUTER_MODEL", "").strip()
    resolved = resolved or DEFAULT_OPENROUTER_MODEL
    _model_cache = (resolved, now)
    return resolved


def configured_fallback_models(primary: str) -> list[str]:
    """Fallback slugs from settings, excluding the primary, capped at 3."""
    stored = _load_settings_fallbacks()
    if not stored:
        from app.db.models.category_suggestion import DEFAULT_FALLBACK_MODELS

        stored = list(DEFAULT_FALLBACK_MODELS)
    seen = {primary}
    out: list[str] = []
    for raw in stored:
        slug = str(raw or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
        if len(out) >= _MAX_FALLBACK_MODELS:
            break
    return out


def openrouter_chat_completion(
    *,
    system_prompt: str,
    user_content: str,
    timeout: int,
    workload: str,
    temperature: float = 0,
    max_attempts: int | None = None,
    model: str | None = None,
    fallback_models: Sequence[str] | None = None,
    deny_data_collection: bool | None = None,
) -> str:
    """POST a chat completion and return the raw response body."""
    endpoint_url = require_env("OPENROUTER_CHAT_COMPLETIONS_URL")
    chosen = (model or "").strip() or configured_model_name()
    api_key = get_openrouter_api_key()
    fallbacks = list(fallback_models) if fallback_models is not None else (
        configured_fallback_models(chosen)
    )
    deny = (
        deny_data_collection
        if deny_data_collection is not None
        else _load_deny_data_collection()
    )
    payload: dict[str, Any] = {
        "model": chosen,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "user": attribution_user(workload),
        "usage": {"include": True},
    }
    if fallbacks:
        payload["models"] = fallbacks[:_MAX_FALLBACK_MODELS]
    if deny:
        payload["provider"] = {"data_collection": "deny"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **attribution_headers(),
    }
    attempts = max_attempts if max_attempts is not None else _MAX_RETRY_ATTEMPTS
    if attempts < 1:
        raise OpenRouterError("max_attempts must be at least 1")
    body = json.dumps(payload)
    last_status = 0
    last_body = ""
    for attempt in range(1, attempts + 1):
        response = http_invoke(
            method="POST",
            url=endpoint_url,
            headers=headers,
            body=body,
            timeout=timeout,
        )
        status_code = int(response.get("status", 0) or 0)
        last_body = str(response.get("body", "") or "")
        last_status = status_code
        envelope = _envelope_error_code(last_body) if 200 <= status_code < 300 else None
        retryable = status_code in _RETRYABLE_HTTP_STATUSES or (
            envelope is not None and envelope in _RETRYABLE_ENVELOPE_CODES
        )
        if retryable and attempt < attempts:
            delay = _retry_delay_seconds(response.get("headers"), attempt)
            logger.warning(
                "OpenRouter transient error; retrying",
                extra={
                    "attempt": attempt,
                    "status_code": status_code,
                    "envelope_error_code": envelope,
                    "delay_seconds": delay,
                },
            )
            time.sleep(delay)
            continue
        if status_code < 200 or status_code >= 300:
            preview = _format_error_preview(last_body)
            detail = f": {preview}" if preview else ""
            raise OpenRouterError(
                f"OpenRouter request failed with status {status_code}{detail}",
                status=status_code,
            )
        if envelope is not None and envelope in _RETRYABLE_ENVELOPE_CODES:
            preview = _format_error_preview(last_body)
            detail = f": {preview}" if preview else ""
            raise OpenRouterError(
                f"OpenRouter returned transient error (code={envelope}){detail}",
                status=envelope,
            )
        return last_body
    raise OpenRouterError(
        f"OpenRouter request failed with status {last_status}",
        status=last_status or None,
    )


def extract_message_text(body: str) -> str:
    """Pull assistant text from an OpenRouter chat completion body."""
    if not isinstance(body, str) or not body.strip():
        raise OpenRouterError("OpenRouter response was empty")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OpenRouterError(
            f"OpenRouter response was not valid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise OpenRouterError("OpenRouter response must be a JSON object")
    top_error = payload.get("error")
    if isinstance(top_error, dict):
        message_text = top_error.get("message") or json.dumps(top_error)[:300]
        raise OpenRouterError(f"OpenRouter returned error: {message_text}")
    if isinstance(top_error, str) and top_error.strip():
        raise OpenRouterError(f"OpenRouter returned error: {top_error.strip()[:300]}")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError("OpenRouter response choices are missing")
    first = choices[0]
    if not isinstance(first, dict):
        raise OpenRouterError("OpenRouter response choice has invalid shape")
    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenRouterError("OpenRouter response message is missing")
    refusal = message.get("refusal")
    if isinstance(refusal, str) and refusal.strip():
        raise OpenRouterError(f"Model refused: {refusal.strip()[:500]}")
    content = message.get("content")
    if isinstance(content, list):
        parts = [
            str(item.get("text"))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        ]
        text = "\n".join(parts).strip()
    elif isinstance(content, str):
        text = content.strip()
    else:
        text = ""
    if not text:
        finish = first.get("finish_reason")
        suffix = f" (finish_reason={finish})" if finish else ""
        raise OpenRouterError(f"OpenRouter response content is empty{suffix}")
    return text


def usage_from_body(body: str) -> dict[str, Any]:
    """Return token counts and cost_usd from a completion body."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    cost = usage.get("cost")
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "cost_usd": float(cost) if isinstance(cost, (int, float)) else 0.0,
        "model": str(payload.get("model") or ""),
    }


def _load_settings_model() -> str:
    try:
        from app.services.category_suggestions.settings import load_model_name

        return load_model_name() or ""
    except Exception:
        logger.debug("category suggestion model unavailable; using environment")
        return ""


def _load_settings_fallbacks() -> list[str]:
    try:
        from app.services.category_suggestions.settings import load_fallback_models

        return load_fallback_models()
    except Exception:
        return []


def _load_deny_data_collection() -> bool:
    try:
        from app.services.category_suggestions.settings import (
            load_deny_data_collection,
        )

        return load_deny_data_collection()
    except Exception:
        return True


def _extract_key(secret_string: str) -> str:
    raw = secret_string.strip()
    if not raw:
        raise OpenRouterError("OpenRouter API key value is blank")
    if raw.startswith("{"):
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise OpenRouterError("OpenRouter secret JSON must be an object")
        for key_name in (
            "siutindei",
            "openrouter_api_key",
            "OPENROUTER_API_KEY",
            "api_key",
            "key",
            "token",
        ):
            candidate = payload.get(key_name)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        raise OpenRouterError("OpenRouter API key is missing in secret JSON")
    return raw


def _envelope_error_code(body: str) -> int | None:
    if not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    err = payload.get("error")
    if not isinstance(err, dict):
        return None
    code = err.get("code")
    if isinstance(code, bool):
        return None
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.strip().lstrip("-").isdigit():
        try:
            return int(code.strip())
        except ValueError:
            return None
    return None


def _retry_delay_seconds(response_headers: Any, attempt: int) -> float:
    if isinstance(response_headers, Mapping):
        for key, value in response_headers.items():
            if isinstance(key, str) and key.lower() == "retry-after":
                parsed = _parse_retry_after(value)
                if parsed is not None:
                    return min(max(parsed, 0.0), _MAX_RETRY_AFTER_SECONDS)
                break
    idx = min(max(attempt - 1, 0), len(_RETRY_BACKOFF_SCHEDULE_SECONDS) - 1)
    return float(_RETRY_BACKOFF_SCHEDULE_SECONDS[idx])


def _parse_retry_after(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _format_error_preview(body: str) -> str:
    text = body.strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        flat = text.replace("\n", " ")
        return flat[:500]
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            return message[:500]
        if isinstance(err, str):
            return err.strip()[:500]
    return text.replace("\n", " ")[:500]
