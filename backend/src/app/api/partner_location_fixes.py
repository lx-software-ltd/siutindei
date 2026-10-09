"""Partner read and decide access for venue proposals."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_location_fixes import _decide_body
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.api.partner_auth import PartnerContext, require_full_access
from app.db.engine import get_engine
from app.db.models import ActivityLocation
from app.db.models.location_fix import LocationFixProposal
from app.exceptions import ValidationError
from app.services.location_fixes import (
    choice,
    decide_bulk,
    list_proposals,
    parse_uuid,
)
from app.utils import json_response

_STATUSES = frozenset({"pending", "applied", "dismissed"})
_ENTITY_TYPES = frozenset({"organization", "activity"})
_KINDS = frozenset({"link_existing", "create_location", "unresolved"})
_SOURCES = frozenset(
    {
        "rule:single_location",
        "rule:pricing_schedule",
        "rule:name_area",
        "rule:no_venue",
        "model",
    }
)


def handle_partner_location_fixes(
    event: Mapping[str, Any],
    org_id: str | None,
) -> dict[str, Any]:
    """List venue proposals visible to this API key."""
    scoped = UUID(org_id) if org_id else None
    requested = _blank(_query_param(event, "org_id"))
    if scoped is None and requested:
        scoped = parse_uuid(requested, "org_id")
    elif scoped is not None and requested and requested != str(scoped):
        raise ValidationError("org_id is outside this key", field="org_id")
    with Session(get_engine()) as session:
        payload = list_proposals(
            session,
            status=choice(_query_param(event, "status"), _STATUSES, "status")
            or "pending",
            entity_type=choice(
                _query_param(event, "entity_type"), _ENTITY_TYPES, "entity_type"
            ),
            kind=choice(_query_param(event, "kind"), _KINDS, "kind"),
            source=choice(_query_param(event, "source"), _SOURCES, "source"),
            org_id=scoped,
            query=_blank(_query_param(event, "q")),
            cursor=_blank(_query_param(event, "cursor")),
            limit=parse_limit(event),
        )
        payload["items"] = [_partner_item(item) for item in payload["items"]]
    return json_response(200, payload, event=event)


def handle_partner_location_fix_write(
    event: Mapping[str, Any],
    partner: PartnerContext,
    resource_id: str,
) -> dict[str, Any]:
    """Apply or dismiss proposals. Full-access crud keys only."""
    require_full_access(partner)
    decided_by = _get_user_sub(event) or f"api-key:{partner.api_key_id}"
    if resource_id == "bulk":
        body = parse_object_body(event)
        with Session(get_engine()) as session:
            _set_session_audit_context(session, event)
            payload = decide_bulk(session, body, decided_by)
            if not body.get("dry_run"):
                session.commit()
        return json_response(200, payload, event=event)
    body = parse_object_body(event)
    return _decide_body(event, parse_uuid(resource_id, "id"), body, decided_by)


def pending_location_fixes_by_org(
    session: Session, org_ids: list[UUID]
) -> dict[str, list[dict[str, Any]]]:
    """Pending venue proposals for each organization and its activities."""
    grouped: dict[str, list[dict[str, Any]]] = {str(org_id): [] for org_id in org_ids}
    if not org_ids:
        return grouped
    rows = session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.status == "pending",
            LocationFixProposal.org_id.in_(org_ids),
        )
    ).all()
    for row in rows:
        grouped[str(row.org_id)].append(_partner_row(row))
    return grouped


def location_ids_by_activity(
    session: Session, activity_ids: list[UUID]
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {
        str(activity_id): [] for activity_id in activity_ids
    }
    if not activity_ids:
        return grouped
    rows = session.execute(
        select(ActivityLocation.activity_id, ActivityLocation.location_id).where(
            ActivityLocation.activity_id.in_(activity_ids)
        )
    ).all()
    for activity_id, location_id in rows:
        grouped[str(activity_id)].append(str(location_id))
    return grouped


def pending_location_fix_by_activity(
    session: Session, activity_ids: list[UUID]
) -> dict[str, dict[str, Any]]:
    if not activity_ids:
        return {}
    rows = session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.status == "pending",
            LocationFixProposal.entity_type == "activity",
            LocationFixProposal.entity_id.in_(activity_ids),
        )
    ).all()
    return {str(row.entity_id): _partner_row(row) for row in rows}


def _partner_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "entity_type": item["entity_type"],
        "entity_id": item["entity_id"],
        "org_id": item["org_id"],
        "kind": item["kind"],
        "target_location_id": item.get("target_location_id"),
        "proposed_location": item.get("proposed_location"),
        "source": item["source"],
        "confidence": item.get("confidence"),
        "rationale": item.get("rationale"),
        "status": item["status"],
    }


def _partner_row(row: LocationFixProposal) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "org_id": str(row.org_id),
        "kind": row.kind,
        "target_location_id": (
            None if row.target_location_id is None else str(row.target_location_id)
        ),
        "proposed_location": row.proposed_location,
        "source": row.source,
        "confidence": None if row.confidence is None else float(row.confidence),
        "rationale": row.rationale,
        "status": row.status,
    }


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
