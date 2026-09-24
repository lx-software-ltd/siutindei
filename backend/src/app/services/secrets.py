"""Secrets Manager helpers with caching."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from app.services.aws_clients import get_secretsmanager_client

SECRETS_CACHE_TTL_SECONDS = 300

_SECRET_CACHE: dict[str, tuple[dict[str, Any], float]] = {}


def get_secret_json(secret_arn: str) -> dict[str, Any]:
    """Fetch a secret from AWS Secrets Manager and parse JSON."""
    now = time.monotonic()
    cached = _SECRET_CACHE.get(secret_arn)
    if cached is not None:
        payload, loaded_at = cached
        if now - loaded_at <= SECRETS_CACHE_TTL_SECONDS:
            return payload

    client = get_secretsmanager_client()
    response = client.get_secret_value(SecretId=secret_arn)
    secret_str = response.get("SecretString")
    if not secret_str and response.get("SecretBinary"):
        secret_str = base64.b64decode(response["SecretBinary"]).decode("utf-8")
    if not secret_str:
        raise RuntimeError("Secret value is empty")

    secret_payload = json.loads(secret_str)
    _SECRET_CACHE[secret_arn] = (secret_payload, now)
    return secret_payload


def clear_secret_cache() -> None:
    """Clear cached secrets (useful in tests)."""
    _SECRET_CACHE.clear()
