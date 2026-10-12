"""Read catalog version history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.admin_request import _parse_uuid, _query_param, parse_limit
from app.db.engine import get_engine
from app.db.models import CatalogVersion
from app.exceptions import NotFoundError, ValidationError
from app.utils import json_response

_ENTITY_TYPES = {
    "organization",
    "media",
    "location",
    "activity",
    "pricing",
    "schedule",
}


def handle_versions(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """GET /v1/admin/versions and GET /v1/admin/versions/{id}."""
    if method != "GET":
        return json_response(405, {"error": "Method not allowed"}, event=event)
    with Session(get_engine()) as session:
        if resource_id:
            return json_response(200, _one(session, resource_id), event=event)
        return json_response(200, _list(session, event), event=event)


def _one(session: Session, version_id: str) -> dict[str, Any]:
    try:
        parsed = _parse_uuid(version_id)
    except ValidationError as exc:
        raise NotFoundError("catalog_version", version_id) from exc
    row = session.get(CatalogVersion, parsed)
    if row is None:
        raise NotFoundError("catalog_version", version_id)
    return _serialize(row)


def _list(session: Session, event: Mapping[str, Any]) -> dict[str, Any]:
    limit = parse_limit(event)
    entity_type = _entity_type(_query_param(event, "entity_type"))
    entity_id = _optional_uuid(_query_param(event, "entity_id"), "entity_id")
    org_id = _optional_uuid(_query_param(event, "org_id"), "org_id")
    statement = select(CatalogVersion)
    if entity_type:
        statement = statement.where(CatalogVersion.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(CatalogVersion.entity_id == entity_id)
    if org_id is not None:
        statement = statement.where(CatalogVersion.org_id == org_id)
    cursor = _parse_cursor(_query_param(event, "cursor"))
    if cursor is not None:
        when, row_id = cursor
        statement = statement.where(
            or_(
                CatalogVersion.created_at < when,
                and_(
                    CatalogVersion.created_at == when,
                    CatalogVersion.id < row_id,
                ),
            )
        )
    rows = session.scalars(
        statement.order_by(
            CatalogVersion.created_at.desc(),
            CatalogVersion.id.desc(),
        ).limit(limit + 1)
    ).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return {
        "items": [_serialize(row) for row in page],
        "next_cursor": next_cursor,
    }


def _serialize(row: CatalogVersion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "org_id": str(row.org_id) if row.org_id else None,
        "version": row.version,
        "action": row.action,
        "snapshot": row.snapshot,
        "changed_fields": list(row.changed_fields or []),
        "user_id": row.user_id,
        "request_id": row.request_id,
        "import_job_id": str(row.import_job_id) if row.import_job_id else None,
        "reason": row.reason,
        "related_id": str(row.related_id) if row.related_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _entity_type(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    cleaned = str(value).strip()
    if cleaned not in _ENTITY_TYPES:
        raise ValidationError("Invalid entity_type", field="entity_type")
    return cleaned


def _optional_uuid(value: str | None, field: str) -> Any:
    del field
    if value is None or not str(value).strip():
        return None
    return _parse_uuid(str(value).strip())


def _parse_cursor(value: str | None) -> tuple[datetime, Any] | None:
    if value is None or not value.strip():
        return None
    when_raw, _, row_id = value.partition("|")
    try:
        when = datetime.fromisoformat(when_raw)
        parsed = _parse_uuid(row_id)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc
    return when, parsed
