"""Audit log handlers for admin APIs."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import (
    _parse_cursor,
    _parse_uuid,
    _query_param,
    parse_limit,
)
from app.db.audit import AuditLogRepository
from app.db.engine import get_engine
from app.db.models import AuditLog
from app.exceptions import NotFoundError, ValidationError
from app.utils import json_response, parse_datetime
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Fields to redact from audit log old_values/new_values for security
AUDIT_REDACTED_FIELDS: frozenset[str] = frozenset(
    [
        "password",
        "secret",
        "token",
        "api_key",
        "key_hash",
    ]
)

# Valid table names that can be queried via the audit logs endpoint.
# Keep in A–Z lockstep with apps/admin_web/src/lib/audit-tables.ts.
AUDITABLE_TABLES: frozenset[str] = frozenset(
    [
        "activities",
        "activity_categories",
        "activity_locations",
        "activity_pricing",
        "activity_schedule",
        "api_keys",
        "category_suggestion_settings",
        "category_suggestions",
        "cognito_user",
        "feedback_labels",
        "import_settings",
        "locations",
        "organization_duplicate_dismissals",
        "organization_feedback",
        "organization_merges",
        "organizations",
        "tickets",
    ]
)


def _handle_audit_logs(
    event: Mapping[str, Any],
    audit_id: Optional[str],
) -> dict[str, Any]:
    """Handle audit log queries."""
    if audit_id:
        logger.info(f"Fetching audit log entry: {audit_id}")
        return _get_audit_log_by_id(event, audit_id)

    logger.info("Listing audit logs with filters")
    return _list_audit_logs(event)


def _get_audit_log_by_id(
    event: Mapping[str, Any],
    audit_id: str,
) -> dict[str, Any]:
    """Get a single audit log entry by ID."""
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = AuditLogRepository(session)

        try:
            entry = repo.get_by_id(_parse_uuid(audit_id))
        except ValidationError:
            raise NotFoundError("audit_log", audit_id)

        if entry is None:
            raise NotFoundError("audit_log", audit_id)

        return json_response(200, _serialize_audit_log(entry), event=event)


def _list_audit_logs(event: Mapping[str, Any]) -> dict[str, Any]:
    """List audit logs with optional filtering."""
    limit = parse_limit(event)

    table_name = _query_param(event, "table")
    record_id = _query_param(event, "record_id")
    user_id = _query_param(event, "user_id")
    action = _query_param(event, "action")
    since_str = _query_param(event, "since")

    if table_name and table_name not in AUDITABLE_TABLES:
        raise ValidationError(
            (
                f"Invalid table: {table_name}. Must be one of: "
                f"{', '.join(sorted(AUDITABLE_TABLES))}"
            ),
            field="table",
        )

    if record_id and not table_name:
        raise ValidationError(
            "table parameter is required when filtering by record_id",
            field="table",
        )

    valid_actions = {"INSERT", "UPDATE", "DELETE"}
    if action and action.upper() not in valid_actions:
        raise ValidationError(
            f"Invalid action: {action}. Must be one of: INSERT, UPDATE, DELETE",
            field="action",
        )

    since = None
    if since_str:
        since = parse_datetime(since_str)
        if since is None:
            raise ValidationError(
                (
                    "Invalid since format. Use ISO 8601 format "
                    "(e.g., 2024-01-01T00:00:00Z)"
                ),
                field="since",
            )

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = AuditLogRepository(session)
        cursor = _parse_cursor(_query_param(event, "cursor"))

        if record_id and table_name:
            rows = repo.get_record_history(
                table_name=table_name,
                record_id=record_id,
                limit=limit + 1,
            )
        elif user_id:
            rows = repo.get_user_activity(
                user_id=user_id,
                limit=limit + 1,
                since=since,
            )
        elif table_name:
            rows = repo.get_table_activity(
                table_name=table_name,
                limit=limit + 1,
                since=since,
                action=action.upper() if action else None,
            )
        else:
            rows = repo.get_recent_activity(
                limit=limit + 1,
                since=since,
                cursor=cursor,
            )

        has_more = len(rows) > limit
        trimmed = list(rows)[:limit]

        logger.info(
            (f"Audit logs query returned {len(trimmed)} entries (has_more={has_more})"),
            extra={
                "table": table_name,
                "action": action,
                "since": since_str,
                "result_count": len(trimmed),
            },
        )

        return json_response(
            200,
            {"items": [_serialize_audit_log(row) for row in trimmed]},
            event=event,
        )


def _serialize_audit_log(entry: AuditLog) -> dict[str, Any]:
    """Serialize audit log entry with redaction."""
    old_values = entry.old_values or {}
    new_values = entry.new_values or {}

    def redact_values(values: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for key, value in values.items():
            if key.lower() in AUDIT_REDACTED_FIELDS:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted

    return {
        "id": str(entry.id),
        "table_name": entry.table_name,
        "record_id": entry.record_id,
        "action": entry.action,
        "user_id": entry.user_id,
        "request_id": entry.request_id,
        "old_values": redact_values(old_values),
        "new_values": redact_values(new_values),
        "changed_fields": entry.changed_fields,
        "timestamp": entry.timestamp,
    }
