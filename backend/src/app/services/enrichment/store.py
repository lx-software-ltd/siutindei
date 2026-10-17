"""Persistence for enrichment runs, proposals, and the budget."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.organization import Organization
from app.db.models.org_enrichment import (
    ACTIVE_RUN_STATUSES,
    OrgEnrichmentProposal,
    OrgEnrichmentRun,
    OrgEnrichmentSettings,
)
from app.exceptions import AppError, NotFoundError, ValidationError
from app.services.enrichment.constants import STALE_RUN_MINUTES

_DEFAULT_LIMIT = Decimal("25")


def load_settings(session: Session) -> OrgEnrichmentSettings:
    row = session.get(OrgEnrichmentSettings, 1)
    if row is None:
        row = OrgEnrichmentSettings(id=1, monthly_cost_limit_usd=_DEFAULT_LIMIT)
        session.add(row)
        session.flush()
    return row


def update_settings(session: Session, body: dict[str, Any]) -> OrgEnrichmentSettings:
    row = load_settings(session)
    if "monthly_cost_limit_usd" in body:
        row.monthly_cost_limit_usd = _decimal(
            body.get("monthly_cost_limit_usd"),
            "monthly_cost_limit_usd",
            Decimal("0.01"),
            Decimal("1000"),
        )
    if "max_pages" in body:
        row.max_pages = _int_between(body.get("max_pages"), "max_pages", 1, 20)
    if "max_page_bytes" in body:
        row.max_page_bytes = _int_between(
            body.get("max_page_bytes"), "max_page_bytes", 10_000, 2_000_000
        )
    if "copy_media" in body:
        row.copy_media = bool(body.get("copy_media"))
    if "min_confidence_shown" in body:
        row.min_confidence_shown = _decimal(
            body.get("min_confidence_shown"),
            "min_confidence_shown",
            Decimal("0"),
            Decimal("1"),
        )
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return row


def month_spend(session: Session, now: datetime | None = None) -> Decimal:
    moment = now or datetime.now(timezone.utc)
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = session.scalar(
        select(func.coalesce(func.sum(OrgEnrichmentRun.cost_usd), 0)).where(
            OrgEnrichmentRun.created_at >= start
        )
    )
    return Decimal(str(total or 0))


def start_run(
    session: Session,
    org_id: UUID,
    *,
    requested_by: str | None,
) -> OrgEnrichmentRun:
    org = session.get(Organization, org_id)
    if org is None:
        raise NotFoundError("organization", str(org_id))
    website = (org.website or "").strip()
    if not website:
        raise AppError("Add a website before enriching", status_code=422)
    from app.services.enrichment.guard import CrawlError, validate_seed_url

    try:
        seed = validate_seed_url(website)
    except CrawlError as exc:
        raise ValidationError(str(exc), field="website") from exc
    expire_stale_runs(session, org_id)
    active = session.scalar(
        select(OrgEnrichmentRun.id).where(
            OrgEnrichmentRun.org_id == org_id,
            OrgEnrichmentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    if active is not None:
        raise AppError("An enrichment is already running", status_code=409)
    settings = load_settings(session)
    if month_spend(session) >= Decimal(str(settings.monthly_cost_limit_usd)):
        raise AppError("The monthly enrichment budget is spent", status_code=422)
    run = OrgEnrichmentRun(
        org_id=org_id,
        status="queued",
        requested_by=requested_by,
        seed_url=seed,
    )
    session.add(run)
    session.flush()
    return run


def expire_stale_runs(session: Session, org_id: UUID) -> bool:
    """Fail active runs that outlived the queue retries. Returns True if any changed."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)
    rows = session.scalars(
        select(OrgEnrichmentRun).where(
            OrgEnrichmentRun.org_id == org_id,
            OrgEnrichmentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    ).all()
    changed = False
    now = datetime.now(timezone.utc)
    for row in rows:
        created = row.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created >= cutoff:
            continue
        row.status = "failed"
        row.error = "Enrichment timed out"
        row.finished_at = now
        changed = True
    if changed:
        session.flush()
    return changed


def latest_run(
    session: Session, org_id: UUID, run_id: UUID | None
) -> OrgEnrichmentRun | None:
    if run_id is not None:
        row = session.get(OrgEnrichmentRun, run_id)
        if row is None or str(row.org_id) != str(org_id):
            return None
        return row
    return session.scalar(
        select(OrgEnrichmentRun)
        .where(OrgEnrichmentRun.org_id == org_id)
        .order_by(OrgEnrichmentRun.created_at.desc())
        .limit(1)
    )


def save_proposals(
    session: Session,
    run: OrgEnrichmentRun,
    items: list[dict[str, Any]],
    *,
    min_confidence: Decimal,
) -> int:
    dismissed = set(
        session.scalars(
            select(OrgEnrichmentProposal.proposed_hash).where(
                OrgEnrichmentProposal.org_id == run.org_id,
                OrgEnrichmentProposal.status == "dismissed",
            )
        ).all()
    )
    kept = 0
    for item in items:
        confidence = Decimal(str(item.get("confidence") or 0))
        if confidence < min_confidence:
            continue
        proposed = item.get("proposed") or {}
        current = item.get("current")
        if _same(current, proposed):
            continue
        digest = hashlib.sha256(
            json.dumps(proposed, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        if digest in dismissed:
            continue
        session.add(
            OrgEnrichmentProposal(
                run_id=run.id,
                org_id=run.org_id,
                section=str(item.get("section") or "Organization"),
                kind=str(item.get("kind") or "update_organization"),
                field=item.get("field"),
                label=str(item.get("label") or item.get("field") or "Change"),
                current_value=current,
                proposed_value=proposed,
                confidence=confidence,
                unverified=bool(item.get("unverified")),
                evidence=list(item.get("evidence") or []),
                proposed_hash=digest,
            )
        )
        kept += 1
    session.flush()
    return kept


def serialize_settings(row: OrgEnrichmentSettings) -> dict[str, Any]:
    return {
        "monthly_cost_limit_usd": float(row.monthly_cost_limit_usd),
        "max_pages": row.max_pages,
        "max_page_bytes": row.max_page_bytes,
        "copy_media": row.copy_media,
        "min_confidence_shown": float(row.min_confidence_shown),
    }


def serialize_run(run: OrgEnrichmentRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "org_id": str(run.org_id),
        "status": run.status,
        "seed_url": run.seed_url,
        "pages_fetched": run.pages_fetched,
        "bytes_fetched": run.bytes_fetched,
        "model": run.model,
        "cost_usd": float(run.cost_usd or 0),
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def serialize_proposal(row: OrgEnrichmentProposal) -> dict[str, Any]:
    proposed = row.proposed_value if isinstance(row.proposed_value, dict) else {}
    return {
        "id": str(row.id),
        "section": row.section,
        "kind": row.kind,
        "field": row.field,
        "label": row.label,
        "current_value": row.current_value,
        "proposed_value": proposed,
        "confidence": float(row.confidence),
        "unverified": row.unverified,
        "evidence": row.evidence,
        "status": row.status,
        "copyright_notice": proposed.get("copyright_notice"),
    }


def _same(current: object, proposed: object) -> bool:
    if not isinstance(current, dict) or not isinstance(proposed, dict):
        return False
    for key, value in proposed.items():
        if key == "copyright_notice":
            continue
        if current.get(key) != value:
            return False
    return True


def _decimal(value: object, field: str, low: Decimal, high: Decimal) -> Decimal:
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise ValidationError(f"{field} must be a number", field=field) from exc
    if number < low or number > high:
        raise ValidationError(f"{field} is out of range", field=field)
    return number


def _int_between(value: object, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValidationError(f"{field} must be an integer", field=field)
    try:
        number = int(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an integer", field=field) from exc
    if number < low or number > high:
        raise ValidationError(f"{field} is out of range", field=field)
    return number
