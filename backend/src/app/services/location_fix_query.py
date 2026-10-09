"""Read venue proposals, the sweep budget, and their API shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Activity, GeographicArea, Location, Organization
from app.db.models.location_fix import (
    LocationFixProposal,
    LocationFixSettings,
    LocationScanRun,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.name_fix_query import decode_cursor, encode_cursor, ilike_pattern

KINDS = frozenset({"link_existing", "create_location", "unresolved"})
SOURCES = frozenset(
    {
        "rule:single_location",
        "rule:pricing_schedule",
        "rule:name_area",
        "rule:no_venue",
        "model",
    }
)
STATUSES = frozenset({"pending", "applied", "dismissed"})
ENTITY_TYPES = frozenset({"organization", "activity"})


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
    stmt = filtered_stmt(
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


def pending_row(
    session: Session, entity_type: str, entity_id: str | UUID
) -> LocationFixProposal | None:
    return session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.entity_type == entity_type,
            LocationFixProposal.entity_id == entity_id,
            LocationFixProposal.status == "pending",
        )
    ).first()


def filtered_stmt(
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


def choice(value: Any, allowed: frozenset[str], field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def optional_uuid(value: Any, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc


def parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc
