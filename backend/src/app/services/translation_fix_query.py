"""Read translation proposals, the sweep budget, and their API shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Activity, Organization
from app.db.models.translation_fix import (
    TranslationFixProposal,
    TranslationFixSettings,
    TranslationScanRun,
)
from app.exceptions import NotFoundError
from app.services.data_quality.list_params import (
    choice,
    decode_cursor,
    encode_cursor,
    ilike_pattern,
    parse_uuid,
)
from app.services.data_quality.sweep_support import month_total, parse_cost_limit
from app.services.translation_gaps import language_list, text_label

STATUSES = frozenset({"pending", "applied", "dismissed"})
ENTITY_TYPES = frozenset({"organization", "activity"})
FIELDS = frozenset({"name", "description"})


def load_settings(session: Session) -> TranslationFixSettings:
    """Return the singleton budget row, creating the default when missing."""
    row = session.get(TranslationFixSettings, 1)
    if row is None:
        row = TranslationFixSettings(id=1, monthly_cost_limit_usd=Decimal("50"))
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
        row.monthly_cost_limit_usd = parse_cost_limit(body["monthly_cost_limit_usd"])
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return settings_payload(session)


def month_cost(session: Session) -> float:
    """Spend recorded on translation sweeps this calendar month."""
    return month_total(
        session, TranslationScanRun.cost_usd, TranslationScanRun.created_at
    )


def catalog_model(entity_type: str):
    """Organization or activity table. None when the type is unknown."""
    if entity_type == "organization":
        return Organization
    if entity_type == "activity":
        return Activity
    return None


def over_budget(session: Session) -> bool:
    limit = load_settings(session).monthly_cost_limit_usd
    return month_cost(session) >= float(limit)


def list_proposals(
    session: Session,
    *,
    status: str | None,
    entity_type: str | None,
    field: str | None,
    org_id: UUID | None,
    query: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    stmt = filtered_stmt(
        status=status,
        entity_type=entity_type,
        field=field,
        org_id=org_id,
        query=query,
    )
    if cursor:
        stamp, last_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                TranslationFixProposal.created_at < stamp,
                and_(
                    TranslationFixProposal.created_at == stamp,
                    TranslationFixProposal.id < last_id,
                ),
            )
        )
    stmt = stmt.order_by(
        TranslationFixProposal.created_at.desc(),
        TranslationFixProposal.id.desc(),
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
    row = session.get(TranslationFixProposal, proposal_id)
    if row is None:
        raise NotFoundError("translation_fix_proposals", str(proposal_id))
    return serialize_many(session, [row])[0]


def summarize_proposals(session: Session) -> dict[str, Any]:
    rows = session.execute(
        select(TranslationFixProposal.status, func.count()).group_by(
            TranslationFixProposal.status
        )
    ).all()
    by_status = {status: int(count) for status, count in rows}
    active = session.scalars(
        select(TranslationScanRun)
        .where(TranslationScanRun.status.in_(("queued", "running")))
        .order_by(TranslationScanRun.created_at.desc())
        .limit(1)
    ).first()
    latest = session.scalars(
        select(TranslationScanRun)
        .order_by(TranslationScanRun.created_at.desc())
        .limit(1)
    ).first()
    settings = load_settings(session)
    return {
        "by_status": by_status,
        "month_cost_usd": month_cost(session),
        "monthly_cost_limit_usd": float(settings.monthly_cost_limit_usd),
        "active_run": None if active is None else serialize_run(active),
        "latest_run": None if latest is None else serialize_run(latest),
    }


def pending_row(
    session: Session,
    entity_type: str,
    entity_id: str | UUID,
    field: str,
) -> TranslationFixProposal | None:
    return session.scalars(
        select(TranslationFixProposal).where(
            TranslationFixProposal.entity_type == entity_type,
            TranslationFixProposal.entity_id == entity_id,
            TranslationFixProposal.field == field,
            TranslationFixProposal.status == "pending",
        )
    ).first()


def filtered_stmt(
    *,
    status: str | None,
    entity_type: str | None,
    field: str | None,
    org_id: UUID | None,
    query: str | None,
):
    stmt = select(TranslationFixProposal)
    if status:
        stmt = stmt.where(TranslationFixProposal.status == status)
    if entity_type:
        stmt = stmt.where(TranslationFixProposal.entity_type == entity_type)
    if field:
        stmt = stmt.where(TranslationFixProposal.field == field)
    if org_id is not None:
        stmt = stmt.where(TranslationFixProposal.org_id == org_id)
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
                    TranslationFixProposal.entity_type == "organization",
                    TranslationFixProposal.entity_id.in_(org_ids),
                ),
                and_(
                    TranslationFixProposal.entity_type == "activity",
                    TranslationFixProposal.entity_id.in_(activity_ids),
                ),
            )
        )
    return stmt


def serialize_run(run: TranslationScanRun) -> dict[str, Any]:
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
        "queued_for_model": run.queued_count,
        "failed": run.failed_count,
        "cost_usd": float(run.cost_usd or 0),
        "truncated": bool(run.truncated),
        "error": run.error,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def serialize_many(
    session: Session, rows: list[TranslationFixProposal]
) -> list[dict[str, Any]]:
    if not rows:
        return []
    org_ids = {row.org_id for row in rows}
    activity_ids = [row.entity_id for row in rows if row.entity_type == "activity"]
    org_entity_ids = [
        row.entity_id for row in rows if row.entity_type == "organization"
    ]
    org_names = {
        org.id: org.name
        for org in session.scalars(
            select(Organization).where(
                Organization.id.in_(org_ids | set(org_entity_ids))
            )
        ).all()
    }
    activity_names = {
        activity.id: activity.name
        for activity in session.scalars(
            select(Activity).where(Activity.id.in_(activity_ids or []))
        ).all()
    }
    payload = []
    for row in rows:
        if row.entity_type == "activity":
            entity_name = activity_names.get(row.entity_id)
        else:
            entity_name = org_names.get(row.entity_id)
        missing = [str(item) for item in (row.missing_languages or [])]
        payload.append(
            {
                "id": str(row.id),
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id),
                "entity_name": entity_name,
                "org_id": str(row.org_id),
                "org_name": org_names.get(row.org_id),
                "field": row.field,
                "source_text": dict(row.source_text or {}),
                "proposed_text": dict(row.proposed_text or {}),
                "missing_languages": missing,
                "source": row.source,
                "confidence": None if row.confidence is None else float(row.confidence),
                "rationale": row.rationale,
                "status": row.status,
                "current_label": text_label(row.source_text),
                "proposed_label": text_label(row.proposed_text),
                "missing_label": language_list(missing),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "decided_at": row.decided_at,
            }
        )
    return payload


__all__ = [
    "ENTITY_TYPES",
    "FIELDS",
    "STATUSES",
    "choice",
    "parse_uuid",
]
