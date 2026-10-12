"""Read catalog version history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.admin_request import _parse_uuid, _query_param, parse_limit
from app.db.engine import get_engine
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    CatalogVersion,
    Location,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.catalog_version_match import forget_removed_baseline
from app.utils import json_response

_BLOCKING_TYPES = ("location", "activity", "pricing", "schedule")
_LIVE_MODELS = {
    "location": Location,
    "activity": Activity,
    "pricing": ActivityPricing,
    "schedule": ActivitySchedule,
}

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
    sub_resource: str | None = None,
) -> dict[str, Any]:
    """GET /v1/admin/versions and GET /v1/admin/versions/{id}."""
    if method == "POST" and resource_id and sub_resource == "forget":
        return _forget(event, resource_id)
    if method != "GET" or sub_resource:
        return json_response(405, {"error": "Method not allowed"}, event=event)
    with Session(get_engine()) as session:
        if resource_id:
            return json_response(200, _one(session, resource_id), event=event)
        return json_response(200, _list(session, event), event=event)


def _one(session: Session, version_id: str) -> dict[str, Any]:
    return _serialize(_load(session, version_id))


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
    blocking = _truthy(_query_param(event, "blocking"))
    if blocking:
        if org_id is None:
            raise ValidationError("org_id is required", field="org_id")
        statement = statement.where(
            CatalogVersion.version == 1,
            CatalogVersion.entity_type.in_(_BLOCKING_TYPES),
            or_(
                CatalogVersion.reason.is_(None),
                CatalogVersion.reason.notin_(("forgotten", "merged")),
            ),
            _removed_clause(),
        )
    by_version = entity_id is not None and not blocking
    cursor = _parse_cursor(_query_param(event, "cursor"), by_version=by_version)
    if by_version and cursor is not None:
        version, row_id = cursor
        statement = statement.where(
            or_(
                CatalogVersion.version < version,
                and_(
                    CatalogVersion.version == version,
                    CatalogVersion.id < row_id,
                ),
            )
        )
    elif cursor is not None:
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
    if by_version:
        statement = statement.order_by(
            CatalogVersion.version.desc(),
            CatalogVersion.id.desc(),
        )
    else:
        statement = statement.order_by(
            CatalogVersion.created_at.desc(),
            CatalogVersion.id.desc(),
        )
    rows = session.scalars(statement.limit(limit + 1)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1]
        if by_version:
            next_cursor = f"v|{last.version}|{last.id}"
        else:
            next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return {
        "items": [_serialize(row) for row in page],
        "next_cursor": next_cursor,
    }


def _forget(event: Mapping[str, Any], version_id: str) -> dict[str, Any]:
    with Session(get_engine()) as session:
        row = _load(session, version_id)
        if row.entity_type not in _BLOCKING_TYPES or row.version != 1:
            raise ValidationError(
                "Only a removed child version 1 can be forgotten",
                field="id",
            )
        if row.reason == "merged":
            raise ValidationError(
                "A merged record cannot be forgotten here",
                field="id",
            )
        model = _LIVE_MODELS[row.entity_type]
        if session.get(model, row.entity_id) is not None:
            raise ValidationError(
                "The record is still in the catalog",
                field="id",
            )
        forget_removed_baseline(session, row.entity_type, row.entity_id)
        session.commit()
    return json_response(204, {}, event=event)


def _load(session: Session, version_id: str) -> CatalogVersion:
    try:
        parsed = _parse_uuid(version_id)
    except ValidationError as exc:
        raise NotFoundError("catalog_version", version_id) from exc
    row = session.get(CatalogVersion, parsed)
    if row is None:
        raise NotFoundError("catalog_version", version_id)
    return row


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


def _parse_cursor(value: str | None, *, by_version: bool) -> tuple[Any, Any] | None:
    if value is None or not value.strip():
        return None
    if by_version:
        kind, _, rest = value.partition("|")
        version_raw, _, row_id = rest.partition("|")
        try:
            if kind != "v":
                raise ValueError(kind)
            version = int(version_raw)
            parsed = _parse_uuid(row_id)
        except (TypeError, ValueError, ValidationError) as exc:
            raise ValidationError("Invalid cursor", field="cursor") from exc
        return version, parsed
    when_raw, _, row_id = value.partition("|")
    try:
        when = datetime.fromisoformat(when_raw)
        parsed = _parse_uuid(row_id)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc
    return when, parsed


def _removed_clause() -> Any:
    return or_(
        and_(
            CatalogVersion.entity_type == "location",
            ~select(Location.id)
            .where(Location.id == CatalogVersion.entity_id)
            .exists(),
        ),
        and_(
            CatalogVersion.entity_type == "activity",
            ~select(Activity.id)
            .where(Activity.id == CatalogVersion.entity_id)
            .exists(),
        ),
        and_(
            CatalogVersion.entity_type == "pricing",
            ~select(ActivityPricing.id)
            .where(ActivityPricing.id == CatalogVersion.entity_id)
            .exists(),
        ),
        and_(
            CatalogVersion.entity_type == "schedule",
            ~select(ActivitySchedule.id)
            .where(ActivitySchedule.id == CatalogVersion.entity_id)
            .exists(),
        ),
    )


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}
