"""Partner read access to pending name-fix proposals."""

from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_crud import _handle_crud
from app.api.admin_request import parse_limit, _query_param
from app.api.admin_resources import _RESOURCE_CONFIG
from app.db.engine import get_engine
from app.db.models import Activity, NameFixProposal, Organization
from app.exceptions import ValidationError
from app.services.name_fixes import list_proposals
from app.utils import json_response

_ENTITY_TYPES = frozenset({"organization", "activity"})


def handle_partner_name_fixes(
    event: Mapping[str, Any],
    org_id: str | None,
) -> dict[str, Any]:
    """List pending name proposals visible to this API key."""
    entity_type = _blank(_query_param(event, "entity_type"))
    if entity_type is not None and entity_type not in _ENTITY_TYPES:
        raise ValidationError("Invalid entity_type", field="entity_type")
    query = _blank(_query_param(event, "q"))
    with Session(get_engine()) as session:
        payload = list_proposals(
            session,
            status="pending",
            entity_type=entity_type,
            rule=_blank(_query_param(event, "rule")),
            org_id=UUID(org_id) if org_id else None,
            query=query,
            cursor=_blank(_query_param(event, "cursor")),
            limit=parse_limit(event),
        )
        _add_review_status(session, payload["items"])
        payload["items"] = [_partner_item(item) for item in payload["items"]]
    return json_response(200, payload, event=event)


def partner_get_organizations(
    event: Mapping[str, Any],
    resource_id: str | None,
    managed_org_ids: set[str] | None,
) -> dict[str, Any]:
    """List or fetch organizations and attach pending name proposals."""
    config = _RESOURCE_CONFIG["organizations"]
    response = _handle_crud(event, "GET", config, resource_id, managed_org_ids)
    if response.get("statusCode") != 200:
        return response
    payload = json.loads(response["body"])
    with Session(get_engine()) as session:
        if isinstance(payload.get("items"), list):
            grouped = _fixes_by_org(
                session,
                [UUID(item["id"]) for item in payload["items"]],
            )
            for item in payload["items"]:
                item["pending_name_fixes"] = grouped.get(item["id"], [])
        elif payload.get("id"):
            grouped = _fixes_by_org(session, [UUID(payload["id"])])
            payload["pending_name_fixes"] = grouped.get(payload["id"], [])
    response["body"] = json.dumps(payload, default=str)
    return response


def _fixes_by_org(session: Session, org_ids: list[UUID]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {str(org_id): [] for org_id in org_ids}
    if not org_ids:
        return grouped
    org_rows = session.scalars(
        select(NameFixProposal).where(
            NameFixProposal.status == "pending",
            NameFixProposal.entity_type == "organization",
            NameFixProposal.entity_id.in_(org_ids),
        )
    ).all()
    for row in org_rows:
        grouped[str(row.entity_id)].append(_partner_fix(row))
    activity_rows = session.execute(
        select(NameFixProposal, Activity.org_id)
        .join(Activity, Activity.id == NameFixProposal.entity_id)
        .where(
            NameFixProposal.status == "pending",
            NameFixProposal.entity_type == "activity",
            Activity.org_id.in_(org_ids),
        )
    ).all()
    for row, owner_id in activity_rows:
        grouped[str(owner_id)].append(_partner_fix(row))
    return grouped


def _add_review_status(session: Session, items: list[dict[str, Any]]) -> None:
    org_ids = [
        UUID(item["entity_id"])
        for item in items
        if item["entity_type"] == "organization"
    ]
    activity_ids = [
        UUID(item["entity_id"]) for item in items if item["entity_type"] == "activity"
    ]
    status_by_entity: dict[str, str] = {}
    if org_ids:
        for org in session.scalars(
            select(Organization).where(Organization.id.in_(org_ids))
        ):
            status_by_entity[str(org.id)] = org.review_status
    if activity_ids:
        for activity_id, review_status in session.execute(
            select(Activity.id, Organization.review_status)
            .join(Organization, Organization.id == Activity.org_id)
            .where(Activity.id.in_(activity_ids))
        ):
            status_by_entity[str(activity_id)] = review_status
    for item in items:
        item["review_status"] = status_by_entity.get(item["entity_id"])


def _partner_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "entity_type": item["entity_type"],
        "entity_id": item["entity_id"],
        "current_value": item["current_value"],
        "proposed_value": item["proposed_value"],
        "rules": item["rules"],
        "review_status": item.get("review_status"),
    }


def _partner_fix(row: NameFixProposal) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "current_value": row.current_value,
        "proposed_value": row.proposed_value,
        "rules": row.rules or [],
    }


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
