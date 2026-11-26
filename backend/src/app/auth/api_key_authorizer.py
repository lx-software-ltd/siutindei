"""Core logic for the partner API-key request authorizer.

Validates ``Authorization: Bearer <token>`` against hashed keys in the
``api_keys`` table and produces an IAM policy plus authorizer context.

SECURITY NOTES:
- Only SHA-256 hashes are compared; plaintext keys are never stored/logged.
- Revoked and expired keys are rejected at lookup time. The API Gateway
  authorizer cache (5 minutes) bounds how long a revoked key keeps working.
- Scope enforcement happens in the handlers (read vs crud), because a
  cached Allow policy applies to every partner route.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.auth.authorizer_helpers import get_header, policy
from app.db.engine import get_engine
from app.db.repositories import ApiKeyRepository
from app.services.api_keys import hash_api_key, looks_like_api_key
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_API_KEY_LEN = 256
_LAST_USED_REFRESH_INTERVAL = timedelta(minutes=1)


def _bearer_token(headers: dict[str, Any]) -> str | None:
    """Return the token from ``Authorization: Bearer``, or None."""
    raw = get_header(headers, "Authorization")
    if not isinstance(raw, str):
        return None
    scheme, separator, token = raw.strip().partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None
    key = token.strip()
    if not key or len(key) > _MAX_API_KEY_LEN or " " in key:
        return None
    return key


def authorize_api_key(event: dict[str, Any]) -> dict[str, Any]:
    """Validate the partner API key and build the authorizer response."""
    headers = event.get("headers") or {}
    method_arn = event.get("methodArn", "")

    plaintext = _bearer_token(headers)
    if not plaintext:
        logger.warning("Missing Authorization bearer token")
        return policy("Deny", method_arn, "anonymous", {"reason": "missing_key"})

    if not looks_like_api_key(plaintext):
        logger.warning("Malformed partner API key")
        return policy("Deny", method_arn, "invalid", {"reason": "invalid_key"})

    key_hash = hash_api_key(plaintext)

    with Session(get_engine()) as session:
        repo = ApiKeyRepository(session)
        api_key = repo.find_active_by_hash(key_hash)
        if api_key is None:
            logger.warning("Unknown, revoked, or expired partner API key")
            return policy("Deny", method_arn, "invalid", {"reason": "invalid_key"})

        _touch_last_used(session, repo, api_key)

        key_id = str(api_key.id)
        org_id = str(api_key.org_id) if api_key.org_id else ""
        logger.info(
            f"Partner API key authorized: {key_id[:8]}*** "
            f"(scope={api_key.scope}, org_scoped={bool(org_id)})"
        )
        return policy(
            "Allow",
            method_arn,
            f"api-key:{key_id}",
            {
                "apiKeyId": key_id,
                "scope": api_key.scope,
                "orgId": org_id,
                # Reuse the shared audit-context plumbing: writes made with
                # this key are attributed to "api-key:<id>" in audit logs.
                "userSub": f"api-key:{key_id}",
            },
        )


def _touch_last_used(
    session: Session,
    repo: ApiKeyRepository,
    api_key: Any,
) -> None:
    """Refresh last_used_at, throttled to avoid a write per request."""
    now = datetime.now(UTC)
    last_used = api_key.last_used_at
    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=UTC)
    if last_used is not None and now - last_used < _LAST_USED_REFRESH_INTERVAL:
        return
    try:
        repo.touch_last_used(api_key)
        session.commit()
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning(f"Failed to update last_used_at: {type(exc).__name__}")
        session.rollback()
