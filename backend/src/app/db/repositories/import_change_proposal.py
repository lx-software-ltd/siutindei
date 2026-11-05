"""Field plans, identity fallback, and accepting a queued import change."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ImportChangeProposal,
    Location,
    Organization,
)
from app.db.repositories.import_baseline import (
    find_by_payload,
    load_baseline,
    save_baseline,
    save_proposals,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.catalog_version_shape import _snapshot_shape_keys, payload_differs
from app.services.import_merge import RowPlan, decide_fields, merge_mode, next_payload
from app.services.import_settings import load_import_settings


def review_status_of(session: Session, org_id: Any) -> str | None:
    """Review state of the organization that owns a child row."""
    if org_id is None:
        return None
    org = session.get(Organization, org_id)
    if org is None:
        return None
    return org.review_status


def plan_live_row(
    session: Session,
    entity_type: str,
    entity_id: Any,
    org_id: Any,
    incoming: dict[str, Any],
    present: set[str],
    current: dict[str, Any],
    allow_updates: bool,
    warnings: list[str] | None,
    *,
    review_status: str | None = None,
    source: str | None = None,
    forced_base: dict[str, Any] | None = None,
    partial: bool = False,
) -> RowPlan:
    """Decide one existing row and store the baseline and any proposals."""
    from app.services.catalog_version_match import (
        KEPT_LATER as kept_later,
    )
    from app.services.catalog_version_match import (
        _status_for_snapshot,
        _version1,
        _warn,
    )

    settings = load_import_settings(session)
    mode = merge_mode(
        settings.existing_rows,
        settings.approved_organizations,
        review_status,
    )
    stored = (
        None
        if forced_base is not None
        else load_baseline(session, entity_type, entity_id)
    )
    version1 = _version1(session, entity_type, entity_id)
    if mode == "apply" or _base_missing(stored, forced_base, version1):
        plan = _legacy_plan(
            session,
            entity_type,
            entity_id,
            incoming,
            present,
            current,
            allow_updates,
            warnings,
            forced_base=forced_base,
            partial=partial,
            version1=version1,
            status_for=_status_for_snapshot,
        )
    else:
        base, only = _merge_base(stored, forced_base, version1, entity_type, partial)
        plan = decide_fields(
            entity_type,
            base,
            current,
            incoming,
            present,
            mode=mode,
            only=only,
        )
        if not allow_updates and plan.status != "unchanged":
            plan = RowPlan(status="skipped", apply_fields=frozenset())
        else:
            if plan.status == "unchanged" and payload_differs(
                entity_type,
                current,
                base or {},
                partial=partial,
            ):
                _warn(warnings, kept_later)
            for warning in plan.warnings:
                _warn(warnings, warning)
            if allow_updates:
                save_proposals(session, entity_type, entity_id, org_id, plan.changes)
    _store_baseline(
        session,
        entity_type,
        entity_id,
        org_id,
        incoming,
        present,
        stored if stored is not None else _snapshot_of(forced_base, version1),
        source,
    )
    return plan


def adopt_baseline_organization(
    session: Session,
    raw_org: dict[str, Any],
    incoming: dict[str, Any],
) -> Organization | None:
    """Live organization whose baseline matches this file, before version 1."""
    place_id = str(raw_org.get("place_id") or "").strip()
    if place_id:
        found = _live_orgs(
            session,
            find_by_payload(
                session, "organization", "place_id", place_id, folded=False
            ),
        )
        if found is not None:
            return found
    source = str(raw_org.get("source") or "").strip()
    source_id = str(raw_org.get("source_id") or "").strip()
    if source and source_id:
        rows = [
            row
            for row in find_by_payload(
                session,
                "organization",
                "source_id",
                source_id,
                folded=False,
            )
            if str((row.payload or {}).get("source") or "") == source
        ]
        found = _live_orgs(session, rows)
        if found is not None:
            return found
    name = normalize_org_name(str(incoming.get("name") or ""))
    if not name:
        return None
    return _live_orgs(
        session,
        find_by_payload(session, "organization", "name", name),
    )


def find_activity_baseline(
    session: Session,
    org_id: Any,
    names: set[str],
) -> Activity | None:
    """Activity renamed by an admin, still named in the source baseline."""
    found: dict[str, Activity] = {}
    for name in names:
        if not str(name or "").strip():
            continue
        rows = find_by_payload(
            session,
            "activity",
            "name",
            normalize_org_name(str(name)),
            org_id=org_id,
        )
        for row in rows:
            activity = session.get(Activity, row.entity_id)
            if activity is not None and str(activity.org_id) == str(org_id):
                found[str(activity.id)] = activity
    if len(found) > 1:
        raise ValidationError("Multiple activities found", field="name")
    return next(iter(found.values()), None)


def find_location_baseline(
    session: Session,
    org_id: Any,
    address: str,
) -> Location | None:
    """Location whose stored address matches the file after an admin edit."""
    rows = find_by_payload(
        session,
        "location",
        "address",
        normalize_org_name(address),
        org_id=org_id,
    )
    found: dict[str, Location] = {}
    for row in rows:
        location = session.get(Location, row.entity_id)
        if location is not None and str(location.org_id) == str(org_id):
            found[str(location.id)] = location
    if len(found) > 1:
        raise ValidationError("Multiple locations found", field="name")
    return next(iter(found.values()), None)


def accept_proposal(
    session: Session, proposal_id: Any, actor: str | None
) -> ImportChangeProposal:
    """Write one field through the admin update path and mark it applied."""
    row = session.get(ImportChangeProposal, proposal_id)
    if row is None or row.status != "pending":
        raise NotFoundError("Import change not found")
    entity = _load_entity(session, row.entity_type, row.entity_id)
    if entity is None:
        _mark(row, "dismissed", actor)
        raise NotFoundError("Import change not found")
    _write_field(session, row, entity)
    _mark(row, "applied", actor)
    return row


def dismiss_proposal(
    session: Session, proposal_id: Any, actor: str | None
) -> ImportChangeProposal:
    """Keep the catalog value and remember that this source value was refused."""
    row = session.get(ImportChangeProposal, proposal_id)
    if row is None or row.status != "pending":
        raise NotFoundError("Import change not found")
    _mark(row, "dismissed", actor)
    return row


def accept_all(
    session: Session,
    actor: str | None,
    *,
    org_id: Any = None,
    import_job_id: Any = None,
) -> int:
    """Accept every pending proposal for one organization or one import job."""
    stmt = select(ImportChangeProposal).where(ImportChangeProposal.status == "pending")
    if org_id is not None:
        stmt = stmt.where(ImportChangeProposal.org_id == org_id)
    if import_job_id is not None:
        stmt = stmt.where(ImportChangeProposal.import_job_id == import_job_id)
    rows = list(session.scalars(stmt).all())
    applied = 0
    for row in rows:
        entity = _load_entity(session, row.entity_type, row.entity_id)
        if entity is None:
            _mark(row, "dismissed", actor)
            continue
        _write_field(session, row, entity)
        _mark(row, "applied", actor)
        applied += 1
    return applied


def _legacy_plan(
    session: Session,
    entity_type: str,
    entity_id: Any,
    incoming: dict[str, Any],
    present: set[str],
    current: dict[str, Any],
    allow_updates: bool,
    warnings: list[str] | None,
    *,
    forced_base: dict[str, Any] | None,
    partial: bool,
    version1: Any,
    status_for: Any,
) -> RowPlan:
    snapshot = forced_base if forced_base is not None else _snapshot_of(None, version1)
    if snapshot is None:
        return RowPlan(status=None, apply_fields=None)
    status = status_for(
        session,
        entity_type,
        entity_id,
        incoming,
        snapshot,
        present,
        current,
        allow_updates,
        warnings,
        partial=partial,
    )
    return RowPlan(
        status=status,
        apply_fields=None if status is None else frozenset(),
    )


def _merge_base(
    stored: dict[str, Any] | None,
    forced_base: dict[str, Any] | None,
    version1: Any,
    entity_type: str,
    partial: bool,
) -> tuple[dict[str, Any], set[str] | None]:
    if stored is not None:
        return stored, None
    if forced_base is not None:
        only = _snapshot_shape_keys(entity_type, forced_base) if partial else None
        return forced_base, only
    snapshot = version1.snapshot if version1 is not None else {}
    return dict(snapshot or {}), None


def _base_missing(
    stored: dict[str, Any] | None, forced_base: dict[str, Any] | None, version1: Any
) -> bool:
    return stored is None and forced_base is None and version1 is None


def _snapshot_of(
    forced_base: dict[str, Any] | None, version1: Any
) -> dict[str, Any] | None:
    if forced_base is not None:
        return forced_base
    if version1 is None:
        return None
    snapshot = version1.snapshot
    return dict(snapshot) if isinstance(snapshot, dict) else None


def _store_baseline(
    session: Session,
    entity_type: str,
    entity_id: Any,
    org_id: Any,
    incoming: dict[str, Any],
    present: set[str],
    previous: dict[str, Any] | None,
    source: str | None,
) -> None:
    save_baseline(
        session,
        entity_type,
        entity_id,
        org_id,
        next_payload(entity_type, previous, incoming, present),
        source=source,
    )


def _live_orgs(session: Session, rows: list[Any]) -> Organization | None:
    found: dict[str, Organization] = {}
    for row in rows:
        org = session.get(Organization, row.entity_id)
        if org is not None:
            found[str(org.id)] = org
    if len(found) > 1:
        raise ValidationError("Multiple organizations found", field="name")
    return next(iter(found.values()), None)


def _load_entity(session: Session, entity_type: str, entity_id: Any) -> Any:
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


def _write_field(session: Session, row: ImportChangeProposal, entity: Any) -> None:
    from app.api.admin_resource_activity import _update_activity
    from app.api.admin_resource_location import _update_location
    from app.api.admin_resource_organization import _update_organization
    from app.api.admin_resource_pricing import _update_pricing
    from app.api.admin_resource_schedule import _update_schedule
    from app.db.repositories import (
        ActivityPricingRepository,
        ActivityRepository,
        ActivityScheduleRepository,
        LocationRepository,
        OrganizationRepository,
    )

    body = {row.field: row.proposed_value}
    if row.entity_type == "organization":
        updated = _update_organization(OrganizationRepository(session), entity, body)
        OrganizationRepository(session).update(updated)
        return
    if row.entity_type == "location":
        updated = _update_location(LocationRepository(session), entity, body)
        LocationRepository(session).update(updated)
        return
    if row.entity_type == "activity":
        updated = _update_activity(ActivityRepository(session), entity, body)
        ActivityRepository(session).update(updated)
        return
    if row.entity_type == "pricing":
        updated = _update_pricing(ActivityPricingRepository(session), entity, body)
        ActivityPricingRepository(session).update(updated)
        return
    updated = _update_schedule(ActivityScheduleRepository(session), entity, body)
    ActivityScheduleRepository(session).update(updated)


def _mark(row: ImportChangeProposal, status: str, actor: str | None) -> None:
    row.status = status
    row.decided_by = actor
    row.decided_at = datetime.now(UTC)
    row.updated_at = row.decided_at
