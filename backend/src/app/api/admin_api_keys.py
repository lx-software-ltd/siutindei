"""Admin handlers for managing partner API keys."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import (
    _encode_cursor,
    _parse_body,
    _parse_cursor,
    _parse_uuid,
    _query_param,
    parse_limit,
)
from app.api.admin_validators import MAX_NAME_LENGTH, _validate_string_length
from app.db.engine import get_engine
from app.db.models import ApiKey
from app.db.repositories import ApiKeyRepository, OrganizationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.api_keys import generate_api_key
from app.utils import json_response, parse_datetime
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_SCOPES = ("read", "crud")


def _handle_admin_api_keys(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """Handle /admin/api-keys routes (list, create, get, revoke)."""
    if method == "GET" and resource_id is None:
        return _list_api_keys(event)
    if method == "GET" and resource_id is not None:
        return _get_api_key(event, resource_id)
    if method == "POST" and resource_id is None:
        return _create_api_key(event)
    if method == "DELETE" and resource_id is not None:
        return _revoke_api_key(event, resource_id)
    return json_response(405, {"error": "Method not allowed"}, event=event)


def _list_api_keys(event: Mapping[str, Any]) -> dict[str, Any]:
    """List API keys with cursor pagination."""
    limit = parse_limit(event)
    cursor = _parse_cursor(_query_param(event, "cursor"))

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = ApiKeyRepository(session)
        rows = repo.get_all(limit=limit + 1, cursor=cursor)

    has_more = len(rows) > limit
    trimmed = list(rows)[:limit]
    next_cursor = _encode_cursor(trimmed[-1].id) if has_more and trimmed else None

    return json_response(
        200,
        {
            "items": [_serialize_api_key(row) for row in trimmed],
            "next_cursor": next_cursor,
        },
        event=event,
    )


def _get_api_key(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    """Get a single API key by id."""
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = ApiKeyRepository(session)
        entity = repo.get_by_id(_parse_uuid(resource_id))
        if entity is None:
            raise NotFoundError("api-keys", resource_id)
        return json_response(200, _serialize_api_key(entity), event=event)


def _create_api_key(event: Mapping[str, Any]) -> dict[str, Any]:
    """Create a new API key; the plaintext value is returned once."""
    body = _parse_body(event)

    name = _validate_string_length(
        body.get("name"), "name", MAX_NAME_LENGTH, required=True
    )
    if name is None:
        raise ValidationError("name is required", field="name")

    scope = body.get("scope")
    if scope not in _ALLOWED_SCOPES:
        raise ValidationError(
            f"scope must be one of: {', '.join(_ALLOWED_SCOPES)}",
            field="scope",
        )

    org_id = _parse_optional_org_id(body.get("org_id"))
    expires_at = _parse_optional_expiry(body.get("expires_at"))

    generated = generate_api_key()

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)

        if org_id is not None:
            org_repo = OrganizationRepository(session)
            if org_repo.get_by_id(org_id) is None:
                raise ValidationError(
                    "org_id does not match an existing organization",
                    field="org_id",
                )

        repo = ApiKeyRepository(session)
        entity = ApiKey(
            name=name,
            key_prefix=generated.prefix,
            key_hash=generated.key_hash,
            scope=scope,
            org_id=org_id,
            created_by=_get_user_sub(event),
            expires_at=expires_at,
        )
        repo.create(entity)
        session.commit()
        session.refresh(entity)
        logger.info(f"Created API key {entity.id} (scope={scope})")

        payload = _serialize_api_key(entity)
        # SECURITY: the plaintext key is only returned in this response and
        # is never stored or logged.
        payload["api_key"] = generated.plaintext
        return json_response(201, payload, event=event)


def _revoke_api_key(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    """Revoke an API key (idempotent soft delete)."""
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = ApiKeyRepository(session)
        entity = repo.get_by_id(_parse_uuid(resource_id))
        if entity is None:
            raise NotFoundError("api-keys", resource_id)
        repo.revoke(entity)
        session.commit()
        session.refresh(entity)
        logger.info(f"Revoked API key {resource_id}")
        return json_response(200, _serialize_api_key(entity), event=event)


def _parse_optional_org_id(value: Any) -> Any:
    """Parse an optional organization id from the request body."""
    if value is None or value == "":
        return None
    return _parse_uuid(str(value))


def _parse_optional_expiry(value: Any) -> datetime | None:
    """Parse an optional expiry timestamp; must be in the future."""
    if value is None or value == "":
        return None
    try:
        parsed = parse_datetime(str(value))
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValidationError(
            "Invalid expires_at format. Use ISO 8601 (e.g. 2027-01-01T00:00:00Z)",
            field="expires_at",
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if parsed <= datetime.now(UTC):
        raise ValidationError(
            "expires_at must be in the future",
            field="expires_at",
        )
    return parsed


def _serialize_api_key(entity: ApiKey) -> dict[str, Any]:
    """Serialize an API key without its hash."""
    return {
        "id": str(entity.id),
        "name": entity.name,
        "key_prefix": entity.key_prefix,
        "scope": entity.scope,
        "org_id": str(entity.org_id) if entity.org_id else None,
        "status": _key_status(entity),
        "created_by": entity.created_by,
        "created_at": entity.created_at,
        "expires_at": entity.expires_at,
        "revoked_at": entity.revoked_at,
        "last_used_at": entity.last_used_at,
    }


def _key_status(entity: ApiKey) -> str:
    """Compute the display status of a key."""
    if entity.revoked_at is not None:
        return "revoked"
    expires_at = entity.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return "expired"
    return "active"
