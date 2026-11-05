"""List, accept, and dismiss queued catalog import changes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.db.engine import get_engine
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    CatalogVersion,
    ImportChangeProposal,
    Location,
    Organization,
)
from app.db.repositories.import_baseline import (
    list_pending,
    parse_uuid,
    pending_count,
)
from app.db.repositories.import_change_proposal import (
    accept_all,
    accept_proposal,
    dismiss_proposal,
)
from app.exceptions import ValidationError
from app.utils import json_response


def handle_import_changes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch the import-change queue.

    A list commits because it dismisses a proposal whose record is gone.
    """
    if method == "GET" and resource_id is None and sub_resource is None:
        return _list(event)
    if method == "POST" and resource_id == "accept-all" and sub_resource is None:
        return _accept_all(event)
    if method == "POST" and resource_id and sub_resource == "accept":
        return _decide(event, resource_id, accept_proposal)
    if method == "POST" and resource_id and sub_resource == "dismiss":
        return _decide(event, resource_id, dismiss_proposal)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    org_id = _optional_uuid(_query_param(event, "org_id"), "org_id")
    job_id = _optional_uuid(_query_param(event, "import_job_id"), "import_job_id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        rows, cursor = list_pending(
            session,
            org_id=org_id,
            import_job_id=job_id,
            limit=parse_limit(event),
            cursor=_query_param(event, "cursor"),
        )
        items = [_item(session, row) for row in rows]
        count = (
            pending_count(session, org_id)
            if org_id is not None
            else _pending_total(session)
        )
        session.commit()
    return json_response(
        200,
        {"items": items, "next_cursor": cursor, "pending_count": count},
        event=event,
    )


def _accept_all(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    org_id = _optional_uuid(body.get("org_id"), "org_id")
    job_id = _optional_uuid(body.get("import_job_id"), "import_job_id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        applied = accept_all(
            session,
            _get_user_sub(event),
            org_id=org_id,
            import_job_id=job_id,
        )
        session.commit()
    return json_response(200, {"applied": applied}, event=event)


def _decide(event: Mapping[str, Any], resource_id: str, action: Any) -> dict[str, Any]:
    proposal_id = parse_uuid(resource_id)
    if proposal_id is None:
        raise ValidationError("id must be a UUID", field="id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        row = action(session, proposal_id, _get_user_sub(event))
        payload = _item(session, row)
        session.commit()
    return json_response(200, payload, event=event)


def _item(session: Session, row: ImportChangeProposal) -> dict[str, Any]:
    actor = _current_actor(session, row.entity_type, row.entity_id, row.field)
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "org_id": None if row.org_id is None else str(row.org_id),
        "org_name": _org_name(session, row.org_id),
        "record_name": _record_name(session, row),
        "field": row.field,
        "base_value": row.base_value,
        "current_value": row.current_value,
        "proposed_value": row.proposed_value,
        "import_job_id": None if row.import_job_id is None else str(row.import_job_id),
        "created_at": row.created_at.isoformat(),
        "current_user_id": actor[0],
        "current_import_job_id": actor[1],
        "status": row.status,
    }


def _org_name(session: Session, org_id: Any) -> str | None:
    if org_id is None:
        return None
    org = session.get(Organization, org_id)
    if org is None:
        return None
    return org.name


def _record_name(session: Session, row: ImportChangeProposal) -> str:
    entity = _entity(session, row.entity_type, row.entity_id)
    if isinstance(entity, Organization):
        return entity.name or row.entity_type
    if isinstance(entity, Activity):
        return entity.name or row.entity_type
    if isinstance(entity, Location):
        return entity.address or row.entity_type
    if isinstance(entity, ActivityPricing):
        kind = entity.pricing_type
        return kind.value if hasattr(kind, "value") else str(kind)
    if isinstance(entity, ActivitySchedule):
        return ", ".join(entity.languages or []) or row.entity_type
    return row.entity_type


def _entity(session: Session, entity_type: str, entity_id: Any) -> Any:
    model = {
        "organization": Organization,
        "location": Location,
        "activity": Activity,
        "pricing": ActivityPricing,
        "schedule": ActivitySchedule,
    }.get(entity_type)
    if model is None:
        return None
    return session.get(model, entity_id)


def _current_actor(
    session: Session, entity_type: str, entity_id: Any, field: str
) -> tuple[str | None, str | None]:
    """Actor of the version that last changed this field."""
    versions = list(
        session.scalars(
            select(CatalogVersion)
            .where(
                CatalogVersion.entity_type == entity_type,
                CatalogVersion.entity_id == entity_id,
            )
            .order_by(CatalogVersion.version.desc())
        ).all()
    )
    chosen = _version_for_field(versions, field)
    if chosen is None or chosen.version <= 1:
        return None, None
    job = None if chosen.import_job_id is None else str(chosen.import_job_id)
    return chosen.user_id, job


def _version_for_field(
    versions: list[CatalogVersion], field: str
) -> CatalogVersion | None:
    if not any(_snap_has(version.snapshot, field) for version in versions):
        return next((version for version in versions if version.version > 1), None)
    for index, version in enumerate(versions):
        older = versions[index + 1] if index + 1 < len(versions) else None
        if older is None or _snap_field(version.snapshot, field) != _snap_field(
            older.snapshot, field
        ):
            return version if version.version > 1 else None
    return None


def _snap_has(snapshot: Any, field: str) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if field == "weekly_entries":
        return "entries" in snapshot or "weekly_entries" in snapshot
    if field in {"age_min", "age_max"}:
        return field in snapshot or "age_range" in snapshot
    return field in snapshot


def _snap_field(snapshot: Any, field: str) -> Any:
    if not isinstance(snapshot, dict):
        return None
    if field == "weekly_entries":
        return snapshot.get("entries", snapshot.get("weekly_entries"))
    if field in {"age_min", "age_max"}:
        return snapshot.get(field, snapshot.get("age_range"))
    return snapshot.get(field)


def _pending_total(session: Session) -> int:
    return len(
        session.scalars(
            select(ImportChangeProposal.id).where(
                ImportChangeProposal.status == "pending"
            )
        ).all()
    )


def _optional_uuid(value: Any, field: str) -> Any:
    if value in (None, ""):
        return None
    parsed = parse_uuid(value)
    if parsed is None:
        raise ValidationError(f"{field} must be a UUID", field=field)
    return parsed
