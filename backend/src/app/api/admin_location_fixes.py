"""Alias for /v1/admin/location-fixes, plus the partner decide body."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.data_quality.list_params import parse_uuid
from app.services.data_quality.proposal_lifecycle import ProposalKind, decide
from app.utils import json_response


def handle_location_fixes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/location-fixes routes."""
    from app.api.admin_proposals import handle_proposals

    return handle_proposals(
        event,
        method,
        ProposalKind.LOCATIONS,
        resource_id,
        sub_resource,
    )


def _decide_body(
    event: Mapping[str, Any],
    proposal_id: UUID,
    body: dict[str, Any],
    decided_by: str | None,
) -> dict[str, Any]:
    """Apply or dismiss one venue proposal. Partner routes call this directly."""
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    address = body.get("address")
    area_id = body.get("area_id")
    target_raw = body.get("target_location_id")
    if address is not None and not isinstance(address, str):
        raise ValidationError("address must be a string", field="address")
    if area_id is not None and not isinstance(area_id, str):
        raise ValidationError("area_id must be a string", field="area_id")
    target_location_id = None
    lat = _coord(body.get("lat"), "lat")
    lng = _coord(body.get("lng"), "lng")
    if target_raw is not None:
        if not isinstance(target_raw, str) or not target_raw.strip():
            raise ValidationError(
                "target_location_id must be a UUID",
                field="target_location_id",
            )
        target_location_id = parse_uuid(target_raw, "target_location_id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event, user_id=decided_by)
        payload = decide(
            ProposalKind.LOCATIONS,
            session,
            proposal_id,
            action,
            decided_by,
            address=address,
            area_id=area_id,
            target_location_id=target_location_id,
            lat=lat,
            lng=lng,
        )
        session.commit()
    return json_response(200, payload, event=event)


def _coord(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number", field=field)
    return float(value)
