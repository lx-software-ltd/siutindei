"""Read and write import baselines and change proposals."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ImportBaseline,
    ImportChangeProposal,
    Location,
    Organization,
)
from app.exceptions import ValidationError
from app.services.import_merge import FieldChange, jsonable, same_json


def job_id(session: Session) -> Any:
    """Import job stashed by the payload processor, if any."""
    raw = session.info.get("import_job_id")
    if raw in (None, ""):
        return None
    return raw


def load_baseline(
    session: Session,
    entity_type: str,
    entity_id: Any,
) -> dict[str, Any] | None:
    """Stored source shape, or None when this entity has not been seen."""
    row = session.get(ImportBaseline, (entity_type, entity_id))
    if row is None or not isinstance(row.payload, dict):
        return None
    return dict(row.payload)


def save_baseline(
    session: Session,
    entity_type: str,
    entity_id: Any,
    org_id: Any,
    payload: dict[str, Any],
    *,
    source: str | None = None,
) -> None:
    """Upsert what the source just said for this entity."""
    now = datetime.now(UTC)
    row = session.get(ImportBaseline, (entity_type, entity_id))
    stored = jsonable(payload)
    if row is None:
        session.add(
            ImportBaseline(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                source=source,
                payload=stored,
                import_job_id=job_id(session),
                created_at=now,
                updated_at=now,
            )
        )
        return
    row.payload = stored
    row.org_id = org_id
    row.source = source if source is not None else row.source
    row.import_job_id = job_id(session)
    row.updated_at = now


def save_proposals(
    session: Session,
    entity_type: str,
    entity_id: Any,
    org_id: Any,
    changes: tuple[FieldChange, ...],
) -> None:
    """Queue conflicts. A field the source no longer disputes is dismissed."""
    for change in changes:
        pending = _pending(session, entity_type, entity_id, change.field)
        if change.action != "proposal":
            if pending is not None:
                _decide(pending, "dismissed", None)
            continue
        if pending is not None:
            pending.base_value = change.base
            pending.current_value = change.current
            pending.proposed_value = change.proposed
            pending.import_job_id = job_id(session)
            pending.updated_at = datetime.now(UTC)
            continue
        if _dismissed_same(session, entity_type, entity_id, change):
            continue
        session.add(
            ImportChangeProposal(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                field=change.field,
                base_value=change.base,
                current_value=change.current,
                proposed_value=change.proposed,
                import_job_id=job_id(session),
                status="pending",
            )
        )


def find_by_payload(
    session: Session,
    entity_type: str,
    key: str,
    value: str,
    *,
    org_id: Any = None,
    folded: bool = True,
) -> list[ImportBaseline]:
    """Baselines whose stored payload text matches one key."""
    column = ImportBaseline.payload
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        extracted = column[key].astext
    else:
        extracted = func.json_extract(column, f"$.{key}")
    if folded:
        expr = func.lower(func.trim(extracted))
        wanted = value.strip().casefold()
    else:
        expr = func.trim(extracted)
        wanted = value.strip()
    stmt = select(ImportBaseline).where(
        ImportBaseline.entity_type == entity_type,
        expr == wanted,
    )
    if org_id is not None:
        stmt = stmt.where(ImportBaseline.org_id == org_id)
    return list(session.scalars(stmt).all())


def list_pending(
    session: Session,
    *,
    org_id: Any = None,
    import_job_id: Any = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[ImportChangeProposal], str | None]:
    """Pending proposals, newest first. A missing entity is dismissed."""
    stmt = (
        select(ImportChangeProposal)
        .where(ImportChangeProposal.status == "pending")
        .order_by(
            ImportChangeProposal.created_at.desc(),
            ImportChangeProposal.id.desc(),
        )
    )
    if org_id is not None:
        stmt = stmt.where(ImportChangeProposal.org_id == org_id)
    if import_job_id is not None:
        stmt = stmt.where(ImportChangeProposal.import_job_id == import_job_id)
    if cursor:
        created, ident = _cursor_bound(cursor)
        stmt = stmt.where(
            or_(
                ImportChangeProposal.created_at < created,
                and_(
                    ImportChangeProposal.created_at == created,
                    ImportChangeProposal.id < ident,
                ),
            )
        )
    rows = list(session.scalars(stmt.limit(limit + 1)).all())
    visible: list[ImportChangeProposal] = []
    for row in rows:
        if _entity_exists(session, row.entity_type, row.entity_id):
            visible.append(row)
            continue
        _decide(row, "dismissed", None)
    page = visible[:limit]
    if len(rows) <= limit:
        return page, None
    last = page[-1] if page else rows[limit - 1]
    stamp = last.created_at.astimezone(UTC).isoformat()
    return page, f"{stamp}|{last.id}"


def pending_count(session: Session, org_id: Any) -> int:
    """Pending proposals for one organization whose entity still exists."""
    rows = list(
        session.scalars(
            select(ImportChangeProposal).where(
                ImportChangeProposal.status == "pending",
                ImportChangeProposal.org_id == org_id,
            )
        ).all()
    )
    count = 0
    for row in rows:
        if _entity_exists(session, row.entity_type, row.entity_id):
            count += 1
        else:
            _decide(row, "dismissed", None)
    return count


def _pending(
    session: Session,
    entity_type: str,
    entity_id: Any,
    field: str,
) -> ImportChangeProposal | None:
    return session.scalars(
        select(ImportChangeProposal).where(
            ImportChangeProposal.entity_type == entity_type,
            ImportChangeProposal.entity_id == entity_id,
            ImportChangeProposal.field == field,
            ImportChangeProposal.status == "pending",
        )
    ).first()


def _dismissed_same(
    session: Session,
    entity_type: str,
    entity_id: Any,
    change: FieldChange,
) -> bool:
    rows = session.scalars(
        select(ImportChangeProposal)
        .where(
            ImportChangeProposal.entity_type == entity_type,
            ImportChangeProposal.entity_id == entity_id,
            ImportChangeProposal.field == change.field,
            ImportChangeProposal.status == "dismissed",
        )
        .order_by(ImportChangeProposal.decided_at.desc())
    ).all()
    if not rows:
        return False
    return same_json(rows[0].proposed_value, change.proposed)


def _decide(row: ImportChangeProposal, status: str, actor: str | None) -> None:
    row.status = status
    row.decided_by = actor
    row.decided_at = datetime.now(UTC)
    row.updated_at = row.decided_at


def _entity_exists(session: Session, entity_type: str, entity_id: Any) -> bool:
    model = {
        "organization": Organization,
        "location": Location,
        "activity": Activity,
        "pricing": ActivityPricing,
        "schedule": ActivitySchedule,
    }.get(entity_type)
    if model is None:
        return False
    return session.get(model, entity_id) is not None


def _cursor_bound(cursor: str) -> tuple[datetime, UUID]:
    """Parse ``created_at|id``. A bad cursor is a client error."""
    stamp, separator, ident = cursor.partition("|")
    parsed = parse_uuid(ident) if separator else None
    try:
        created = datetime.fromisoformat(stamp) if separator else None
    except ValueError:
        created = None
    if created is None or parsed is None:
        raise ValidationError("cursor is invalid", field="cursor")
    return created, parsed


def parse_uuid(value: Any) -> UUID | None:
    """Return a UUID or None. Callers treat a bad id as no match."""
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def proposal_json(value: Any) -> str:
    """Stable JSON for tests that compare stored proposal values."""
    return json.dumps(jsonable(value), sort_keys=True, default=str)
