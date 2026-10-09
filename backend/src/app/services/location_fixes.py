"""Decide and store venue proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.location_fix import LocationFixProposal
from app.exceptions import NotFoundError, ValidationError
from app.services.location_fix_apply import apply_proposal
from app.services.location_fix_query import (
    ENTITY_TYPES,
    KINDS,
    SOURCES,
    choice,
    filtered_stmt,
    optional_uuid,
    pending_row,
    serialize_many,
)

_MAX_BULK = 200


def decide_proposal(
    session: Session,
    proposal_id: UUID,
    action: str,
    decided_by: str | None,
    *,
    address: str | None = None,
    area_id: str | None = None,
    target_location_id: str | UUID | None = None,
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
    apply_proposal(
        session,
        row,
        address=address,
        area_id=area_id,
        target_location_id=target_location_id,
    )
    _mark(row, "applied", decided_by)
    session.flush()
    return serialize_many(session, [row])[0]


def decide_bulk(
    session: Session, body: dict[str, Any], decided_by: str | None
) -> dict[str, Any]:
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    rows, truncated = _bulk_rows(session, body)
    if body.get("dry_run"):
        return {
            "dry_run": True,
            "matched": len(rows),
            "truncated": truncated,
            "decided": 0,
            "failed": 0,
            "failures": [],
        }
    decided = 0
    failures: list[dict[str, str]] = []
    for row in rows:
        try:
            with session.begin_nested():
                if action == "dismiss":
                    _mark(row, "dismissed", decided_by)
                else:
                    apply_proposal(
                        session, row, address=None, area_id=None, geocode=False
                    )
                    _mark(row, "applied", decided_by)
            decided += 1
        except (ValidationError, NotFoundError, IntegrityError) as exc:
            message = getattr(exc, "message", None) or "Could not apply the venue."
            failures.append({"id": str(row.id), "message": message})
    session.flush()
    return {
        "dry_run": False,
        "matched": len(rows),
        "truncated": truncated,
        "decided": decided,
        "failed": len(failures),
        "failures": failures,
    }


def clear_pending(session: Session, entity_type: str, entity_id: str | UUID) -> bool:
    row = pending_row(session, entity_type, entity_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def dismissed_same(
    session: Session,
    *,
    entity_type: str,
    entity_id: str | UUID,
    kind: str,
    target_location_id: str | UUID | None,
    proposed_location: dict[str, Any] | None,
    source: str | None = None,
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
        if entity_type != "location" or not source:
            return session.scalar(stmt) is not None
        stmt = stmt.where(LocationFixProposal.source == source)
        if source != "rule:pin_outside_area":
            return session.scalar(stmt) is not None
        stored_rows = session.scalars(
            select(LocationFixProposal).where(
                LocationFixProposal.entity_type == entity_type,
                LocationFixProposal.entity_id == entity_id,
                LocationFixProposal.status == "dismissed",
                LocationFixProposal.kind == "unresolved",
                LocationFixProposal.source == source,
            )
        ).all()
        wanted_pin = _pin_key(proposed_location)
        return any(
            _pin_key(item.proposed_location) == wanted_pin for item in stored_rows
        )
    if kind == "update_location":
        if target_location_id is None:
            return False
        stored_rows = session.scalars(
            select(LocationFixProposal).where(
                LocationFixProposal.entity_type == entity_type,
                LocationFixProposal.entity_id == entity_id,
                LocationFixProposal.status == "dismissed",
                LocationFixProposal.kind == "update_location",
                LocationFixProposal.target_location_id == target_location_id,
            )
        ).all()
        wanted_location = _location_key(proposed_location)
        if wanted_location is None:
            return bool(stored_rows)
        return any(
            _location_key(item.proposed_location) == wanted_location
            for item in stored_rows
        )
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
    entity_id: str | UUID,
    org_id: str | UUID,
    kind: str,
    source: str,
    status: str = "pending",
    target_location_id: str | UUID | None = None,
    proposed_location: dict[str, Any] | None = None,
    confidence: Decimal | None = None,
    rationale: str | None = None,
    scan_run_id: str | UUID | None = None,
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
        source=source,
    ):
        clear_pending(session, entity_type, entity_id)
        return "skipped"
    now = datetime.now(timezone.utc)
    row = pending_row(session, entity_type, entity_id)
    if row is None:
        applied = status == "applied"
        session.add(
            LocationFixProposal(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                kind=kind,
                source=source,
                status="applied" if applied else "pending",
                target_location_id=target_location_id,
                proposed_location=proposed_location,
                confidence=confidence,
                rationale=rationale,
                scan_run_id=scan_run_id,
                decided_by=decided_by if applied else None,
                decided_at=now if applied else None,
            )
        )
        session.flush()
        return "auto_applied" if applied else "created"
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


def _bulk_rows(
    session: Session, body: dict[str, Any]
) -> tuple[list[LocationFixProposal], bool]:
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
        stmt = filtered_stmt(
            status="pending",
            entity_type=choice(body.get("entity_type"), ENTITY_TYPES, "entity_type"),
            kind=choice(body.get("kind"), KINDS, "kind"),
            source=choice(body.get("source"), SOURCES, "source"),
            org_id=optional_uuid(body.get("org_id"), "org_id"),
            query=body.get("q") if isinstance(body.get("q"), str) else None,
        )
    rows = list(
        session.scalars(
            stmt.order_by(LocationFixProposal.created_at.desc()).limit(_MAX_BULK + 1)
        ).all()
    )
    return rows[:_MAX_BULK], len(rows) > _MAX_BULK


def _fill(row: LocationFixProposal, **kwargs: Any) -> None:
    for key, value in kwargs.items():
        setattr(row, key, value)


def _mark(row: LocationFixProposal, status: str, decided_by: str | None) -> None:
    row.status = status
    row.decided_by = decided_by
    row.decided_at = datetime.now(timezone.utc)
    row.updated_at = row.decided_at


def _pin_key(proposed: dict[str, Any] | None) -> tuple[float, float] | None:
    if not proposed or proposed.get("lat") is None or proposed.get("lng") is None:
        return None
    return (round(float(proposed["lat"]), 5), round(float(proposed["lng"]), 5))


def _location_key(proposed: dict[str, Any] | None) -> tuple[str, str] | None:
    if not proposed:
        return None
    address = str(proposed.get("address") or "").strip().casefold()
    area_id = str(proposed.get("area_id") or "").strip()
    if not address and not area_id:
        return None
    return address, area_id
