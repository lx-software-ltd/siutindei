"""Website enrichment routes for one organization."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _is_admin, _set_session_audit_context
from app.api.admin_request import _parse_uuid, parse_object_body
from app.db.engine import get_engine
from app.db.models import Location
from app.db.models.org_enrichment import OrgEnrichmentProposal
from app.exceptions import AppError, ValidationError
from app.services.enrichment.apply import apply_proposals, dismiss_proposals
from app.services.enrichment.queue import enqueue_enrichment
from app.services.enrichment.store import (
    expire_stale_runs,
    latest_run,
    load_settings,
    serialize_proposal,
    serialize_run,
    serialize_settings,
    start_run,
    update_settings,
)
from app.utils import json_response


def organization_tail(path: str) -> list[str]:
    """Path segments after /organizations/{id}."""
    parts = [segment for segment in path.split("/") if segment]
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    if len(parts) < 3 or parts[1] != "organizations":
        return []
    return parts[3:]


def handle_org_enrichment(
    event: Mapping[str, Any],
    method: str,
    org_id_raw: str | None,
) -> dict[str, Any]:
    org_id = _parse_uuid(org_id_raw or "")
    tail = organization_tail(str(event.get("path") or ""))
    action = tail[1] if len(tail) > 1 else None
    if not tail or tail[0] != "enrichment" or action not in {None, "apply", "dismiss"}:
        return json_response(404, {"error": "Not found"}, event=event)
    if not _is_admin(event) and (action is not None or method not in {"GET", "POST"}):
        return json_response(403, {"error": "Forbidden"}, event=event)
    if method == "GET" and action is None:
        return _read(event, org_id)
    if method == "POST" and action is None:
        return _start(event, org_id)
    if method == "POST" and action == "apply":
        return _decide(event, org_id, apply=True)
    if method == "POST" and action == "dismiss":
        return _decide(event, org_id, apply=False)
    return json_response(404, {"error": "Not found"}, event=event)


def handle_enrichment_settings(event: Mapping[str, Any], method: str) -> dict[str, Any]:
    if method == "GET":
        with Session(get_engine()) as session:
            return json_response(
                200,
                serialize_settings(load_settings(session)),
                event=event,
            )
    if method == "PUT":
        body = parse_object_body(event)
        with Session(get_engine()) as session:
            row = update_settings(session, body)
            payload = serialize_settings(row)
            session.commit()
        return json_response(200, payload, event=event)
    return json_response(404, {"error": "Not found"}, event=event)


def _read(event: Mapping[str, Any], org_id: UUID) -> dict[str, Any]:
    from app.api.admin_request import _query_param

    raw_run = _query_param(event, "run_id")
    run_id = _parse_uuid(raw_run) if raw_run else None
    with Session(get_engine()) as session:
        expired = expire_stale_runs(session, org_id)
        run = latest_run(session, org_id, run_id)
        if run is None:
            payload = {"run": None, "proposals": [], "venues": []}
        else:
            proposals = session.scalars(
                select(OrgEnrichmentProposal)
                .where(OrgEnrichmentProposal.run_id == run.id)
                .order_by(OrgEnrichmentProposal.section, OrgEnrichmentProposal.label)
            ).all()
            venues = session.scalars(
                select(Location).where(Location.org_id == org_id)
            ).all()
            payload = {
                "run": serialize_run(run),
                "proposals": [serialize_proposal(row) for row in proposals],
                "venues": [
                    {"id": str(row.id), "address": row.address} for row in venues
                ],
            }
        if expired:
            session.commit()
    return json_response(200, payload, event=event)


def _start(event: Mapping[str, Any], org_id: UUID) -> dict[str, Any]:
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        run = start_run(session, org_id, requested_by=_get_user_sub(event))
        session.commit()
        run_id = run.id
        payload = serialize_run(run)
    try:
        enqueue_enrichment(run_id, stage="crawl")
    except RuntimeError as exc:
        with Session(get_engine()) as session:
            from app.db.models.org_enrichment import OrgEnrichmentRun

            row = session.get(OrgEnrichmentRun, run_id)
            if row is not None:
                row.status = "failed"
                row.error = "Enrichment queue is not configured"
                session.commit()
        raise AppError(str(exc), status_code=503) from exc
    return json_response(202, {"run": payload}, event=event)


def _decide(event: Mapping[str, Any], org_id: UUID, *, apply: bool) -> dict[str, Any]:
    body = parse_object_body(event)
    ids = body.get("ids")
    if not isinstance(ids, list):
        raise ValidationError("ids is required", field="ids")
    overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
    request_id = event.get("requestContext", {}).get("requestId", "")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        if apply:
            results = apply_proposals(
                session,
                org_id,
                [str(item) for item in ids],
                overrides,
                user_id=_get_user_sub(event),
                request_id=request_id,
            )
        else:
            results = dismiss_proposals(
                session,
                org_id,
                [str(item) for item in ids],
                user_id=_get_user_sub(event),
            )
        session.commit()
    return json_response(200, {"results": results}, event=event)
