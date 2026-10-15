"""Sweep organizations and activities that are missing a translation."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, Organization
from app.db.models.translation_fix import TranslationFixProposal, TranslationScanRun
from app.exceptions import ValidationError
from app.services.data_quality.list_params import ilike_pattern
from app.services.data_quality.sweep_support import (
    chunk_entity_batches,
    fail_stale_runs,
    out_of_time,
    take_limited,
)
from app.services.translation_fix_query import ENTITY_TYPES, over_budget, serialize_run
from app.services.translation_fixes import clear_pending
from app.services.translation_gaps import FIELDS, entity_gaps, source_hash

_MAX_SWEEP = 10000
_MAX_MODEL = 500
_BATCH_SIZE = 5
_SWEEP_BUDGET_SECONDS = 20
_REVIEW_SCOPES = frozenset({"pending_review", "all"})
_ACTIVE = ("queued", "running")
STALE_AFTER = timedelta(seconds=660)


class TranslationScanBusy(Exception):
    """A translation sweep is already queued or running."""


def start_translation_scan(
    session: Session,
    *,
    review_scope: str,
    entity_type: str | None = None,
    org_id: UUID | None = None,
    query: str | None = None,
    requested_by: str | None = None,
    budget_seconds: float | None = _SWEEP_BUDGET_SECONDS,
    batch_size: int = _BATCH_SIZE,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Find translation gaps and return model batches to enqueue after commit."""
    deadline = None if budget_seconds is None else time.monotonic() + budget_seconds
    if review_scope not in _REVIEW_SCOPES:
        raise ValidationError("Invalid review_scope", field="review_scope")
    if entity_type is not None and entity_type not in ENTITY_TYPES:
        raise ValidationError("Invalid entity_type", field="entity_type")
    _fail_stale_runs(session)
    if over_budget(session):
        raise ValidationError(
            "Monthly translation-sweep budget is used",
            field="monthly_cost_limit_usd",
        )
    active = session.scalar(
        select(TranslationScanRun.id)
        .where(TranslationScanRun.status.in_(_ACTIVE))
        .limit(1)
    )
    if active is not None:
        raise TranslationScanBusy()
    now = datetime.now(timezone.utc)
    run = TranslationScanRun(
        status="queued",
        requested_by=requested_by,
        org_id=org_id,
        review_scope=review_scope,
        entity_type=entity_type,
        updated_at=now,
    )
    try:
        with session.begin_nested():
            session.add(run)
            session.flush()
    except IntegrityError as exc:
        raise TranslationScanBusy() from exc

    counts = {"created": 0, "updated": 0, "skipped": 0, "cleared": 0}
    truncated = False
    queued: dict[str, list[str]] = {"organization": [], "activity": []}
    pending = _pending_fields(session)
    dismissed = _dismissed_hashes(session)
    seen = 0
    remaining = _MAX_SWEEP
    if entity_type in (None, "organization"):
        orgs, more = take_limited(
            session, org_stmt(org_id, query, review_scope), remaining
        )
        if more:
            truncated = True
        for org in orgs:
            if out_of_time(deadline):
                truncated = True
                break
            seen += 1
            _count_many(
                counts,
                _scan_entity(
                    session,
                    "organization",
                    org,
                    queued,
                    pending,
                    dismissed,
                ),
            )
            if len(queued["organization"]) >= _MAX_MODEL:
                truncated = True
                break
        remaining = _MAX_SWEEP - seen
    if entity_type in (None, "activity") and not truncated and remaining > 0:
        activities, more = take_limited(
            session, activity_stmt(org_id, query, review_scope), remaining
        )
        if more:
            truncated = True
        for activity in activities:
            if out_of_time(deadline):
                truncated = True
                break
            seen += 1
            _count_many(
                counts,
                _scan_entity(
                    session,
                    "activity",
                    activity,
                    queued,
                    pending,
                    dismissed,
                ),
            )
            if len(queued["activity"]) >= _MAX_MODEL:
                truncated = True
                break
    batches = chunk_entity_batches(queued, batch_size)
    run.total_entities = seen
    run.batches_total = len(batches)
    run.created_count = counts["created"]
    run.updated_count = counts["updated"]
    run.skipped_count = counts["skipped"]
    run.cleared_count = counts["cleared"]
    run.queued_count = sum(len(ids) for ids in queued.values())
    run.truncated = truncated
    run.updated_at = datetime.now(timezone.utc)
    if batches:
        run.status = "queued"
    else:
        run.status = "done"
        run.finished_at = run.updated_at
    session.flush()
    payload = serialize_run(run)
    payload["scan_run_id"] = str(run.id)
    payload["queued_for_model"] = run.queued_count
    return payload, batches


def org_stmt(org_id, query, review_scope):
    stmt = select(Organization).order_by(Organization.name, Organization.id)
    if org_id is not None:
        stmt = stmt.where(Organization.id == org_id)
    if query:
        stmt = stmt.where(Organization.name.ilike(ilike_pattern(query), escape="\\"))
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    return stmt


def activity_stmt(org_id, query, review_scope):
    stmt = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .order_by(Activity.name, Activity.id)
    )
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    if org_id is not None:
        stmt = stmt.where(Activity.org_id == org_id)
    if query:
        pattern = ilike_pattern(query)
        stmt = stmt.where(
            or_(
                Activity.name.ilike(pattern, escape="\\"),
                Organization.name.ilike(pattern, escape="\\"),
            )
        )
    return stmt


def _scan_entity(
    session,
    entity_type: str,
    entity,
    queued: dict[str, list[str]],
    pending: set[tuple],
    dismissed: set[tuple],
) -> list[str]:
    gaps = entity_gaps(entity)
    outcomes: list[str] = []
    needs_model = False
    for field in FIELDS:
        key = (entity_type, entity.id, field)
        gap = gaps.get(field)
        if gap is None:
            if key in pending and clear_pending(session, entity_type, entity.id, field):
                pending.discard(key)
                outcomes.append("cleared")
            continue
        digest = source_hash(
            entity_type=entity_type,
            entity_id=entity.id,
            field=field,
            source=gap["source"],
        )
        if (entity_type, entity.id, field, digest) in dismissed:
            if key in pending and clear_pending(session, entity_type, entity.id, field):
                pending.discard(key)
            outcomes.append("skipped")
            continue
        needs_model = True
    if needs_model and len(queued[entity_type]) < _MAX_MODEL:
        queued[entity_type].append(str(entity.id))
    return outcomes


def _pending_fields(session: Session) -> set[tuple]:
    return {
        (entity_type, entity_id, field)
        for entity_type, entity_id, field in session.execute(
            select(
                TranslationFixProposal.entity_type,
                TranslationFixProposal.entity_id,
                TranslationFixProposal.field,
            ).where(TranslationFixProposal.status == "pending")
        )
    }


def _dismissed_hashes(session: Session) -> set[tuple]:
    return {
        (entity_type, entity_id, field, digest)
        for entity_type, entity_id, field, digest in session.execute(
            select(
                TranslationFixProposal.entity_type,
                TranslationFixProposal.entity_id,
                TranslationFixProposal.field,
                TranslationFixProposal.input_hash,
            ).where(
                TranslationFixProposal.status == "dismissed",
                TranslationFixProposal.input_hash.is_not(None),
            )
        )
        if digest
    }


def _count_many(counts: dict[str, int], outcomes: list[str]) -> None:
    for outcome in outcomes:
        if outcome in counts:
            counts[outcome] += 1


def _fail_stale_runs(session: Session) -> None:
    fail_stale_runs(
        session,
        TranslationScanRun,
        stale_after=STALE_AFTER,
        active=_ACTIVE,
    )
