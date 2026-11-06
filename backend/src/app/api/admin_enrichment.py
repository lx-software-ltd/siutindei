"""Website enrichment routes for one organization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _is_admin, _set_session_audit_context
from app.api.admin_request import _parse_uuid, parse_object_body
from app.db.audit import AuditService
from app.db.engine import get_engine
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    Location,
    Organization,
)
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
    """Admin and importer website enrichment. Apply and dismiss are admin-only."""
    return perform_org_enrichment(
        event,
        method,
        org_id_raw,
        actor=_get_user_sub(event),
        allow_decide=_is_admin(event),
    )


def perform_org_enrichment(
    event: Mapping[str, Any],
    method: str,
    org_id_raw: str | None,
    *,
    actor: str | None,
    allow_decide: bool,
) -> dict[str, Any]:
    """Read, start, apply, or dismiss enrichment for one organization.

    ``allow_decide`` is false for an importer JWT. A full-access partner
    key passes true. ``actor`` is stored as the requester.
    """
    org_id = _parse_uuid(org_id_raw or "")
    tail = organization_tail(str(event.get("path") or ""))
    action = tail[1] if len(tail) > 1 else None
    if (
        not tail
        or tail[0] != "enrichment"
        or action not in {None, "apply", "dismiss", "leaflet-upload"}
    ):
        return json_response(404, {"error": "Not found"}, event=event)
    if not allow_decide and (action is not None or method not in {"GET", "POST"}):
        return json_response(403, {"error": "Forbidden"}, event=event)
    if method == "GET" and action is None:
        return _read(event, org_id)
    if method == "POST" and action is None:
        if not allow_decide and _body_requests_leaflet(event):
            return json_response(403, {"error": "Forbidden"}, event=event)
        return _start(event, org_id, actor)
    if method == "POST" and action == "leaflet-upload":
        return _leaflet_upload(event, org_id)
    if method == "POST" and action == "apply":
        return _decide(event, org_id, apply=True, actor=actor)
    if method == "POST" and action == "dismiss":
        return _decide(event, org_id, apply=False, actor=actor)
    return json_response(404, {"error": "Not found"}, event=event)


def handle_enrichment_settings(
    event: Mapping[str, Any],
    method: str,
    *,
    actor: str | None = None,
) -> dict[str, Any]:
    """Read or update the website enrichment settings singleton.

    ``actor`` is the audit user. When it is omitted, the authorizer
    subject is used. A partner key passes its resolved actor.
    """
    recorded = _get_user_sub(event) if actor is None else actor
    if method == "GET":
        with Session(get_engine()) as session:
            return json_response(
                200,
                serialize_settings(load_settings(session)),
                event=event,
            )
    if method == "PUT":
        body = parse_object_body(event)
        request_id = event.get("requestContext", {}).get("requestId", "")
        with Session(get_engine()) as session:
            _set_session_audit_context(session, event, user_id=recorded)
            before = serialize_settings(load_settings(session))
            row = update_settings(session, body)
            payload = serialize_settings(row)
            changed = [key for key in payload if payload[key] != before.get(key)]
            if changed:
                AuditService(
                    session,
                    user_id=recorded,
                    request_id=request_id,
                ).log_custom(
                    "org_enrichment_settings",
                    "1",
                    "UPDATE",
                    old_values={key: before.get(key) for key in changed},
                    new_values={key: payload[key] for key in changed},
                    changed_fields=changed,
                )
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
        payload: dict[str, Any]
        if run is None:
            payload = {"run": None, "proposals": [], "venues": []}
        else:
            proposals = session.scalars(
                select(OrgEnrichmentProposal)
                .where(OrgEnrichmentProposal.run_id == run.id)
                .order_by(OrgEnrichmentProposal.section, OrgEnrichmentProposal.label)
            ).all()
            organization = session.get(Organization, org_id)
            venues = session.scalars(
                select(Location).where(Location.org_id == org_id)
            ).all()
            activity_names = list(
                session.scalars(
                    select(Activity.name).where(Activity.org_id == org_id)
                ).all()
            )
            activity_ids = select(Activity.id).where(Activity.org_id == org_id)
            pricing_count = int(
                session.scalar(
                    select(func.count(ActivityPricing.id)).where(
                        ActivityPricing.activity_id.in_(activity_ids)
                    )
                )
                or 0
            )
            schedule_count = int(
                session.scalar(
                    select(func.count(ActivitySchedule.id)).where(
                        ActivitySchedule.activity_id.in_(activity_ids)
                    )
                )
                or 0
            )
            payload = {
                "run": serialize_run(run),
                "proposals": [
                    serialize_proposal(
                        row,
                        organization=organization,
                        venues=list(venues),
                        activity_names=activity_names,
                        pricing_count=pricing_count,
                        schedule_count=schedule_count,
                    )
                    for row in proposals
                ],
                "venues": [
                    {
                        "id": str(row.id),
                        "address": row.address,
                        "name": row.name,
                        "status": row.status,
                    }
                    for row in venues
                ],
            }
        if expired:
            session.commit()
    return json_response(200, payload, event=event)


def _body_requests_leaflet(event: Mapping[str, Any]) -> bool:
    try:
        body = parse_object_body(event)
    except ValidationError:
        return False
    return "leaflet" in body


def _start(
    event: Mapping[str, Any],
    org_id: UUID,
    actor: str | None,
) -> dict[str, Any]:
    body = parse_object_body(event)
    website = body.get("website")
    if website is not None and not isinstance(website, str):
        raise ValidationError("website must be a string", field="website")
    has_leaflet = "leaflet" in body
    leaflet = body.get("leaflet") if has_leaflet else None
    if has_leaflet and leaflet is None:
        raise ValidationError("leaflet is required", field="leaflet")
    stage = "leaflet" if has_leaflet else "crawl"
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event, user_id=actor)
        try:
            run = start_run(
                session,
                org_id,
                requested_by=actor,
                website=website if isinstance(website, str) else None,
                leaflet=leaflet,
            )
        except ValidationError:
            if has_leaflet:
                from app.services.enrichment.leaflet_objects import discard_request

                discard_request(org_id, leaflet)
            raise
        session.commit()
        run_id = run.id
        payload = serialize_run(run)
    try:
        enqueue_enrichment(run_id, stage=stage)
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


def _leaflet_upload(event: Mapping[str, Any], org_id: UUID) -> dict[str, Any]:
    from app.services.enrichment.leaflet import presign_leaflet

    body = parse_object_body(event)
    file_name = body.get("file_name")
    content_type = body.get("content_type")
    if not isinstance(file_name, str):
        raise ValidationError("file_name is required", field="file_name")
    if not isinstance(content_type, str):
        raise ValidationError("content_type is required", field="content_type")
    return json_response(
        200,
        presign_leaflet(org_id, file_name, content_type),
        event=event,
    )


def _decide(
    event: Mapping[str, Any],
    org_id: UUID,
    *,
    apply: bool,
    actor: str | None,
) -> dict[str, Any]:
    body = parse_object_body(event)
    ids = body.get("ids")
    if not isinstance(ids, list):
        raise ValidationError("ids is required", field="ids")
    raw_overrides = body.get("overrides")
    overrides: dict[str, dict[str, Any]] = {}
    if isinstance(raw_overrides, dict):
        overrides = {
            str(key): value
            for key, value in raw_overrides.items()
            if isinstance(value, dict)
        }
    request_id = event.get("requestContext", {}).get("requestId", "")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event, user_id=actor)
        quality_run_id = None
        if apply:
            results, quality_run_id = apply_proposals(
                session,
                org_id,
                [str(item) for item in ids],
                overrides,
                user_id=actor,
                request_id=request_id,
            )
        else:
            results = dismiss_proposals(
                session,
                org_id,
                [str(item) for item in ids],
                user_id=actor,
            )
        session.commit()
    if quality_run_id:
        from app.services.data_quality.runs import enqueue_staged_run

        enqueue_staged_run(quality_run_id)
    payload: dict[str, Any] = {"results": results}
    if quality_run_id:
        payload["data_quality_run_id"] = quality_run_id
    return json_response(200, payload, event=event)
