"""List, decide, and store venue proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin_resource_location import _create_location
from app.db.models import (
    Activity,
    ActivityLocation,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.location_fix import (
    LocationFixProposal,
    LocationFixSettings,
    LocationScanRun,
)
from app.db.repositories import LocationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.location_fix_geocode import geocode_address
from app.services.name_fix_query import decode_cursor, encode_cursor, ilike_pattern

_MAX_BULK = 200
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
_STATUSES = frozenset({"pending", "applied", "dismissed"})
_ENTITY_TYPES = frozenset({"organization", "activity"})


def load_settings(session: Session) -> LocationFixSettings:
    """Return the singleton budget row, creating the default when missing."""
    row = session.get(LocationFixSettings, 1)
    if row is None:
        row = LocationFixSettings(id=1, monthly_cost_limit_usd=Decimal("50"))
        session.add(row)
        session.flush()
    return row


def settings_payload(session: Session) -> dict[str, Any]:
    row = load_settings(session)
    return {
        "monthly_cost_limit_usd": float(row.monthly_cost_limit_usd),
        "updated_at": row.updated_at,
    }


def update_settings(session: Session, body: dict[str, Any]) -> dict[str, Any]:
    row = load_settings(session)
    if "monthly_cost_limit_usd" in body:
        row.monthly_cost_limit_usd = _parse_cost_limit(body["monthly_cost_limit_usd"])
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return settings_payload(session)


def month_cost(session: Session) -> float:
    """Spend recorded on location sweeps this calendar month."""
    start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    value = session.scalar(
        select(func.coalesce(func.sum(LocationScanRun.cost_usd), 0)).where(
            LocationScanRun.created_at >= start
        )
    )
    return float(value or 0)


def over_budget(session: Session) -> bool:
    limit = load_settings(session).monthly_cost_limit_usd
    return month_cost(session) >= float(limit)


def list_proposals(
    session: Session,
    *,
    status: str | None,
    entity_type: str | None,
    kind: str | None,
    source: str | None,
    org_id: UUID | None,
    query: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    stmt = _filtered_stmt(
        status=status,
        entity_type=entity_type,
        kind=kind,
        source=source,
        org_id=org_id,
        query=query,
    )
    if cursor:
        stamp, last_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                LocationFixProposal.created_at < stamp,
                and_(
                    LocationFixProposal.created_at == stamp,
                    LocationFixProposal.id < last_id,
                ),
            )
        )
    stmt = stmt.order_by(
        LocationFixProposal.created_at.desc(),
        LocationFixProposal.id.desc(),
    )
    rows = list(session.scalars(stmt.limit(limit + 1)).all())
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return {
        "items": serialize_many(session, page),
        "next_cursor": next_cursor,
    }


def get_proposal(session: Session, proposal_id: UUID) -> dict[str, Any]:
    row = session.get(LocationFixProposal, proposal_id)
    if row is None:
        raise NotFoundError("location_fix_proposals", str(proposal_id))
    return serialize_many(session, [row])[0]


def summarize_proposals(session: Session) -> dict[str, Any]:
    rows = session.execute(
        select(
            LocationFixProposal.status,
            LocationFixProposal.kind,
            func.count(),
        ).group_by(LocationFixProposal.status, LocationFixProposal.kind)
    ).all()
    by_status: dict[str, int] = {}
    pending_by_kind: dict[str, int] = {}
    for status, kind, count in rows:
        by_status[status] = by_status.get(status, 0) + int(count)
        if status == "pending":
            pending_by_kind[kind] = int(count)
    active = session.scalars(
        select(LocationScanRun)
        .where(LocationScanRun.status.in_(("queued", "running")))
        .order_by(LocationScanRun.created_at.desc())
        .limit(1)
    ).first()
    settings = load_settings(session)
    return {
        "by_status": by_status,
        "pending_by_kind": pending_by_kind,
        "month_cost_usd": month_cost(session),
        "monthly_cost_limit_usd": float(settings.monthly_cost_limit_usd),
        "active_run": None if active is None else serialize_run(active),
    }


def decide_proposal(
    session: Session,
    proposal_id: UUID,
    action: str,
    decided_by: str | None,
    *,
    address: str | None = None,
    area_id: str | None = None,
) -> dict[str, Any]:
    row = session.get(LocationFixProposal, proposal_id)
    if row is None:
        raise NotFoundError("location_fix_proposals", str(proposal_id))
    if row.status != "pending":
        raise ValidationError("Proposal is already decided", field="status")
    if action == "dismiss":
        _mark(row, "dismissed", decided_by)
        session.flush()
        return serialize_many(session, [row])[0]
    if action != "apply":
        raise ValidationError("action must be apply or dismiss", field="action")
    _apply(session, row, address=address, area_id=area_id)
    _mark(row, "applied", decided_by)
    session.flush()
    return serialize_many(session, [row])[0]


def decide_bulk(
    session: Session, body: dict[str, Any], decided_by: str | None
) -> dict[str, Any]:
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    rows = _bulk_rows(session, body)
    if body.get("dry_run"):
        return {
            "dry_run": True,
            "matched": len(rows),
            "decided": 0,
            "failed": 0,
            "failures": [],
        }
    decided = 0
    failures: list[dict[str, str]] = []
    for row in rows[:_MAX_BULK]:
        try:
            with session.begin_nested():
                if action == "dismiss":
                    _mark(row, "dismissed", decided_by)
                else:
                    _apply(session, row, address=None, area_id=None)
                    _mark(row, "applied", decided_by)
            decided += 1
        except (ValidationError, NotFoundError, IntegrityError) as exc:
            message = getattr(exc, "message", None) or "Could not apply the venue."
            failures.append({"id": str(row.id), "message": message})
    session.flush()
    return {
        "dry_run": False,
        "matched": len(rows),
        "decided": decided,
        "failed": len(failures),
        "failures": failures,
    }


def clear_pending(session: Session, entity_type: str, entity_id: UUID) -> bool:
    row = pending_row(session, entity_type, entity_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def pending_row(
    session: Session, entity_type: str, entity_id: UUID
) -> LocationFixProposal | None:
    return session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.entity_type == entity_type,
            LocationFixProposal.entity_id == entity_id,
            LocationFixProposal.status == "pending",
        )
    ).first()


def dismissed_same(
    session: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    kind: str,
    target_location_id: UUID | None,
    proposed_location: dict[str, Any] | None,
) -> bool:
    """True when an admin already dismissed this same suggestion."""
    stmt = select(LocationFixProposal.id).where(
        LocationFixProposal.entity_type == entity_type,
        LocationFixProposal.entity_id == entity_id,
        LocationFixProposal.status == "dismissed",
        LocationFixProposal.kind == kind,
    )
    if kind == "link_existing":
        if target_location_id is None:
            return False
        stmt = stmt.where(LocationFixProposal.target_location_id == target_location_id)
        return session.scalar(stmt) is not None
    if kind == "unresolved":
        return session.scalar(stmt) is not None
    wanted = _location_key(proposed_location)
    if wanted is None:
        return False
    stored = session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.entity_type == entity_type,
            LocationFixProposal.entity_id == entity_id,
            LocationFixProposal.status == "dismissed",
            LocationFixProposal.kind == "create_location",
        )
    ).all()
    return any(_location_key(row.proposed_location) == wanted for row in stored)


def upsert_proposal(
    session: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    org_id: UUID,
    kind: str,
    source: str,
    status: str = "pending",
    target_location_id: UUID | None = None,
    proposed_location: dict[str, Any] | None = None,
    confidence: Decimal | None = None,
    rationale: str | None = None,
    scan_run_id: UUID | None = None,
    decided_by: str | None = None,
) -> str:
    """Insert or refresh one proposal. Returns created, updated, or skipped."""
    if dismissed_same(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        kind=kind,
        target_location_id=target_location_id,
        proposed_location=proposed_location,
    ):
        if clear_pending(session, entity_type, entity_id):
            return "skipped"
        return "skipped"
    now = datetime.now(timezone.utc)
    row = pending_row(session, entity_type, entity_id)
    if status == "applied" and row is None:
        session.add(
            _new_row(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                kind=kind,
                source=source,
                status="applied",
                target_location_id=target_location_id,
                proposed_location=proposed_location,
                confidence=confidence,
                rationale=rationale,
                scan_run_id=scan_run_id,
                decided_by=decided_by,
                decided_at=now,
            )
        )
        session.flush()
        return "auto_applied"
    if row is None:
        session.add(
            _new_row(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                kind=kind,
                source=source,
                status="pending",
                target_location_id=target_location_id,
                proposed_location=proposed_location,
                confidence=confidence,
                rationale=rationale,
                scan_run_id=scan_run_id,
                decided_by=None,
                decided_at=None,
            )
        )
        session.flush()
        return "created"
    _fill(
        row,
        org_id=org_id,
        kind=kind,
        source=source,
        target_location_id=target_location_id,
        proposed_location=proposed_location,
        confidence=confidence,
        rationale=rationale,
        scan_run_id=scan_run_id,
    )
    if status == "applied":
        _mark(row, "applied", decided_by)
        return "auto_applied"
    row.updated_at = now
    session.flush()
    return "updated"


def serialize_run(run: LocationScanRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "scan_run_id": str(run.id),
        "status": run.status,
        "review_scope": run.review_scope,
        "entity_type": run.entity_type,
        "total_entities": run.total_entities,
        "batches_total": run.batches_total,
        "batches_done": run.batches_done,
        "created": run.created_count,
        "updated": run.updated_count,
        "skipped": run.skipped_count,
        "cleared": run.cleared_count,
        "auto_applied": run.auto_applied_count,
        "queued_for_model": run.queued_count,
        "failed": run.failed_count,
        "cost_usd": float(run.cost_usd or 0),
        "truncated": bool(run.truncated),
        "error": run.error,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def serialize_many(
    session: Session, rows: list[LocationFixProposal]
) -> list[dict[str, Any]]:
    if not rows:
        return []
    org_ids = {row.org_id for row in rows}
    activity_ids = [row.entity_id for row in rows if row.entity_type == "activity"]
    org_names = {
        org.id: org.name
        for org in session.scalars(
            select(Organization).where(Organization.id.in_(org_ids))
        ).all()
    }
    activity_names: dict[Any, str] = {}
    if activity_ids:
        activity_names = {
            activity.id: activity.name
            for activity in session.scalars(
                select(Activity).where(Activity.id.in_(activity_ids))
            ).all()
        }
    location_ids = [
        row.target_location_id for row in rows if row.target_location_id is not None
    ]
    locations = {}
    if location_ids:
        locations = {
            location.id: location
            for location in session.scalars(
                select(Location).where(Location.id.in_(location_ids))
            ).all()
        }
    location_counts = {
        org_id: int(count)
        for org_id, count in session.execute(
            select(Location.org_id, func.count())
            .where(Location.org_id.in_(org_ids))
            .group_by(Location.org_id)
        ).all()
    }
    area_ids = set()
    for row in rows:
        proposed = row.proposed_location or {}
        if proposed.get("area_id"):
            try:
                area_ids.add(UUID(str(proposed["area_id"])))
            except ValueError:
                continue
    areas = {}
    if area_ids:
        areas = {
            str(area.id): area.name
            for area in session.scalars(
                select(GeographicArea).where(GeographicArea.id.in_(area_ids))
            ).all()
        }
    return [
        _serialize(row, org_names, activity_names, locations, areas, location_counts)
        for row in rows
    ]


def _apply(
    session: Session,
    row: LocationFixProposal,
    *,
    address: str | None,
    area_id: str | None,
) -> None:
    if row.kind == "unresolved":
        raise ValidationError("Nothing to apply", field="kind")
    if row.kind == "link_existing":
        _apply_link(session, row)
        return
    if row.kind == "create_location":
        _apply_create(session, row, address=address, area_id=area_id)
        return
    raise ValidationError("Invalid kind", field="kind")


def _apply_link(session: Session, row: LocationFixProposal) -> None:
    if row.entity_type != "activity":
        raise ValidationError("Only an activity can link a venue", field="entity_type")
    if row.target_location_id is None:
        raise ValidationError(
            "target_location_id is required", field="target_location_id"
        )
    location = session.get(Location, row.target_location_id)
    activity = session.get(Activity, row.entity_id)
    if activity is None:
        raise NotFoundError("activities", str(row.entity_id))
    if location is None or str(location.org_id) != str(activity.org_id):
        raise ValidationError(
            "Location is no longer on this organization",
            field="target_location_id",
        )
    existing = session.get(ActivityLocation, (activity.id, location.id))
    if existing is None:
        session.add(ActivityLocation(activity_id=activity.id, location_id=location.id))
        session.flush()


def _apply_create(
    session: Session,
    row: LocationFixProposal,
    *,
    address: str | None,
    area_id: str | None,
) -> None:
    proposed = dict(row.proposed_location or {})
    stored_address = str(proposed.get("address") or "").strip()
    chosen_address = stored_address if address is None else address.strip()
    chosen_area = str(area_id or proposed.get("area_id") or "").strip()
    if not chosen_address:
        raise ValidationError("address is required", field="address")
    if not chosen_area:
        raise ValidationError("area_id is required", field="area_id")
    lat = proposed.get("lat")
    lng = proposed.get("lng")
    if chosen_address != stored_address:
        lat = None
        lng = None
    if lat is None or lng is None:
        coords = geocode_address(chosen_address)
        if coords is not None:
            lat, lng = coords
    location = _create_location(
        LocationRepository(session),
        {
            "org_id": str(row.org_id),
            "area_id": chosen_area,
            "address": chosen_address,
            "lat": lat,
            "lng": lng,
            "place_id": proposed.get("place_id"),
        },
    )
    session.add(location)
    session.flush()
    proposed["address"] = chosen_address
    proposed["area_id"] = chosen_area
    proposed["lat"] = None if lat is None else float(lat)
    proposed["lng"] = None if lng is None else float(lng)
    row.proposed_location = proposed
    row.target_location_id = location.id
    _link_sole_venue(session, row.org_id, location.id)


def _link_sole_venue(session: Session, org_id: UUID, location_id: UUID) -> None:
    count = session.scalar(
        select(func.count()).select_from(Location).where(Location.org_id == org_id)
    )
    if int(count or 0) != 1:
        return
    linked = select(ActivityLocation.activity_id)
    orphans = session.scalars(
        select(Activity).where(
            Activity.org_id == org_id,
            Activity.id.not_in(linked),
        )
    ).all()
    for activity in orphans:
        session.add(ActivityLocation(activity_id=activity.id, location_id=location_id))
        pending = pending_row(session, "activity", activity.id)
        if pending is not None:
            session.delete(pending)
    session.flush()


def _bulk_rows(session: Session, body: dict[str, Any]) -> list[LocationFixProposal]:
    ids = body.get("ids")
    stmt = select(LocationFixProposal).where(LocationFixProposal.status == "pending")
    if isinstance(ids, list) and ids:
        parsed = []
        for raw in ids:
            try:
                parsed.append(UUID(str(raw)))
            except ValueError as exc:
                raise ValidationError("id must be a UUID", field="ids") from exc
        stmt = stmt.where(LocationFixProposal.id.in_(parsed))
    else:
        stmt = _filtered_stmt(
            status="pending",
            entity_type=_optional_choice(
                body.get("entity_type"), _ENTITY_TYPES, "entity_type"
            ),
            kind=_optional_choice(body.get("kind"), _KINDS, "kind"),
            source=_optional_choice(body.get("source"), _SOURCES, "source"),
            org_id=_optional_uuid(body.get("org_id"), "org_id"),
            query=body.get("q") if isinstance(body.get("q"), str) else None,
        )
    return list(
        session.scalars(
            stmt.order_by(LocationFixProposal.created_at.desc()).limit(_MAX_BULK + 1)
        ).all()
    )


def _filtered_stmt(
    *,
    status: str | None,
    entity_type: str | None,
    kind: str | None,
    source: str | None,
    org_id: UUID | None,
    query: str | None,
):
    stmt = select(LocationFixProposal)
    if status:
        stmt = stmt.where(LocationFixProposal.status == status)
    if entity_type:
        stmt = stmt.where(LocationFixProposal.entity_type == entity_type)
    if kind:
        stmt = stmt.where(LocationFixProposal.kind == kind)
    if source:
        stmt = stmt.where(LocationFixProposal.source == source)
    if org_id is not None:
        stmt = stmt.where(LocationFixProposal.org_id == org_id)
    if query and query.strip():
        pattern = ilike_pattern(query.strip())
        org_ids = select(Organization.id).where(
            Organization.name.ilike(pattern, escape="\\")
        )
        activity_ids = select(Activity.id).where(
            Activity.name.ilike(pattern, escape="\\")
        )
        stmt = stmt.where(
            or_(
                and_(
                    LocationFixProposal.entity_type == "organization",
                    LocationFixProposal.entity_id.in_(org_ids),
                ),
                and_(
                    LocationFixProposal.entity_type == "activity",
                    LocationFixProposal.entity_id.in_(activity_ids),
                ),
            )
        )
    return stmt


def _serialize(
    row: LocationFixProposal,
    org_names: dict[Any, str],
    activity_names: dict[Any, str],
    locations: dict[Any, Location],
    areas: dict[str, str],
    location_counts: dict[Any, int],
) -> dict[str, Any]:
    proposed = row.proposed_location or {}
    entity_name = (
        activity_names.get(row.entity_id)
        if row.entity_type == "activity"
        else org_names.get(row.entity_id)
    )
    target = locations.get(row.target_location_id) if row.target_location_id else None
    area_name = proposed.get("area_name") or areas.get(
        str(proposed.get("area_id") or "")
    )
    if row.kind == "link_existing" and target is not None:
        proposed_label = target.address or "Link venue"
    elif row.kind == "create_location":
        bits = [
            str(proposed.get("address") or "").strip(),
            str(area_name or "").strip(),
        ]
        proposed_label = " · ".join(bit for bit in bits if bit) or "New location"
    else:
        proposed_label = "Needs a location"
    venue_count = int(location_counts.get(row.org_id, 0))
    if row.entity_type == "organization":
        current_label = "No location" if venue_count == 0 else f"{venue_count} venues"
    elif venue_count == 0:
        current_label = "No venue"
    else:
        current_label = f"0 of {venue_count} venues"
    confidence = None if row.confidence is None else float(row.confidence)
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "entity_name": entity_name,
        "org_id": str(row.org_id),
        "org_name": org_names.get(row.org_id),
        "kind": row.kind,
        "target_location_id": (
            None if row.target_location_id is None else str(row.target_location_id)
        ),
        "proposed_location": proposed or None,
        "source": row.source,
        "confidence": confidence,
        "rationale": row.rationale,
        "status": row.status,
        "current_label": current_label,
        "proposed_label": proposed_label,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "decided_at": row.decided_at,
    }


def _new_row(**kwargs: Any) -> LocationFixProposal:
    return LocationFixProposal(**kwargs)


def _fill(row: LocationFixProposal, **kwargs: Any) -> None:
    for key, value in kwargs.items():
        setattr(row, key, value)


def _mark(row: LocationFixProposal, status: str, decided_by: str | None) -> None:
    row.status = status
    row.decided_by = decided_by
    row.decided_at = datetime.now(timezone.utc)
    row.updated_at = row.decided_at


def _location_key(proposed: dict[str, Any] | None) -> tuple[str, str] | None:
    if not proposed:
        return None
    address = str(proposed.get("address") or "").strip().casefold()
    area_id = str(proposed.get("area_id") or "").strip()
    if not address and not area_id:
        return None
    return address, area_id


def _parse_cost_limit(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(
            "monthly_cost_limit_usd must be a number",
            field="monthly_cost_limit_usd",
        ) from exc
    if number <= 0 or number > 1000:
        raise ValidationError(
            "monthly_cost_limit_usd must be greater than 0 and at most 1000",
            field="monthly_cost_limit_usd",
        )
    return number


def _optional_choice(value: Any, allowed: frozenset[str], field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def _optional_uuid(value: Any, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc


def choice(value: Any, allowed: frozenset[str], field: str) -> str | None:
    return _optional_choice(value, allowed, field)


def parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc
