"""Request parsing helpers for admin APIs."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Mapping, Optional
from uuid import UUID

from app.exceptions import ValidationError
from app.utils import parse_int
from app.utils.parsers import collect_query_params, first_param

DEFAULT_LIMIT = 50
DEFAULT_MAX_LIMIT = 200


def _parse_body(event: Mapping[str, Any]) -> dict[str, Any]:
    """Parse JSON request body."""
    raw = _raw_body(event)
    if not raw:
        raise ValidationError("Request body is required")
    return json.loads(raw)


def parse_object_body(event: Mapping[str, Any]) -> dict[str, Any]:
    """Parse a JSON object body. An empty body is an empty object."""
    raw = _raw_body(event)
    if not str(raw).strip():
        return {}
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be JSON") from exc
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    return body


def _raw_body(event: Mapping[str, Any]) -> str:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") and raw:
        raw = base64.b64decode(raw).decode("utf-8")
    return str(raw)


def _parse_path(path: str) -> tuple[str, str, Optional[str], Optional[str]]:
    """Parse base path, resource name, and id from the request path.

    Returns:
        Tuple of (base_path, resource, resource_id, sub_resource)
        base_path is "admin", "manager", "user", or "partner"
    """
    parts = [segment for segment in path.split("/") if segment]
    parts = _strip_version_prefix(parts)

    if not parts:
        return "", "", None, None

    base_path = parts[0]

    # Handle /v1/admin/... paths
    if base_path == "admin":
        if len(parts) < 2:
            return base_path, "", None, None
        resource = parts[1]
        resource_id = parts[2] if len(parts) > 2 else None
        sub_resource = parts[3] if len(parts) > 3 else None
        return base_path, resource, resource_id, sub_resource

    # Handle /v1/manager/..., /v1/user/..., and /v1/partner/... paths
    if base_path in ("manager", "user", "partner"):
        resource = parts[1] if len(parts) > 1 else ""
        resource_id = parts[2] if len(parts) > 2 else None
        sub_resource = parts[3] if len(parts) > 3 else None
        return base_path, resource, resource_id, sub_resource

    return "", "", None, None


def _strip_version_prefix(parts: list[str]) -> list[str]:
    """Drop an optional version prefix from path segments."""
    if parts and _is_version_segment(parts[0]):
        return parts[1:]
    return parts


def _is_version_segment(segment: str) -> bool:
    """Return True if the path segment matches v{number}."""
    return segment.startswith("v") and segment[1:].isdigit()


def _query_param(event: Mapping[str, Any], name: str) -> Optional[str]:
    """Return a query parameter value."""
    params = collect_query_params(event)
    return first_param(params, name)


def parse_limit(
    event: Mapping[str, Any],
    *,
    default: int = DEFAULT_LIMIT,
    max_limit: int = DEFAULT_MAX_LIMIT,
) -> int:
    """Parse and validate a standard pagination limit."""
    parsed = parse_int(_query_param(event, "limit"))
    limit = default if parsed is None else parsed
    if limit < 1 or limit > max_limit:
        raise ValidationError(
            f"limit must be between 1 and {max_limit}",
            field="limit",
        )
    return limit


def _parse_uuid(value: str) -> UUID:
    """Parse a UUID string."""
    try:
        return UUID(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Invalid UUID: {value}", field="id") from exc


def _to_uuid(value: UUID | str) -> UUID:
    """Normalize a UUID from UUID or string input."""
    if isinstance(value, UUID):
        return value
    return _parse_uuid(value)


def _parse_group_name(event: Mapping[str, Any]) -> str:
    """Parse the group name from the request."""
    raw = event.get("body") or ""
    if not raw:
        return os.getenv("ADMIN_GROUP") or "admin"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {}
    group = body.get("group") if isinstance(body, dict) else None
    return group or os.getenv("ADMIN_GROUP") or "admin"


def _require_env(name: str) -> str:
    """Return a required environment variable value."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _parse_cursor(value: Optional[str]) -> Optional[UUID]:
    """Parse cursor for admin listing."""
    if value is None or value == "":
        return None
    try:
        payload = _decode_cursor(value)
        return UUID(payload["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc


def _encode_cursor(value: Any) -> str:
    """Encode admin cursor."""
    payload = json.dumps({"id": str(value)}).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("utf-8")
    return encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode admin cursor."""
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding)
    return json.loads(raw)
