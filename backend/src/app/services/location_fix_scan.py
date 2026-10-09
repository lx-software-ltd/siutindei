"""Sweep organizations and activities that still need a venue."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.location_fix import LocationScanRun
from app.exceptions import ValidationError
from app.services import location_fix_quality as location_quality
from app.services.location_fix_lookup import lookup_location_ids
from app.services.location_fix_query import ENTITY_TYPES, over_budget, serialize_run
from app.services.location_fix_registers import consider_open_data
from app.services.location_fixes import (
    clear_pending,
    dismissed_same,
    upsert_proposal,
)
from app.services.name_fix_query import ilike_pattern
from app.services.name_sanitizer_areas import HK_AREAS

_MAX_SWEEP = 10000
_MAX_MODEL = 500
_BATCH_SIZE = 10
_REVIEW_SCOPES = frozenset({"pending_review", "all"})
_LOOKUPS = frozenset({"nominatim", "google"})
_ACTIVE = ("queued", "running")
STALE_AFTER = timedelta(seconds=660)


class LocationScanBusy(Exception):
    """A location sweep is already queued or running."""


def start_location_scan(
    session: Session,
    *,
    review_scope: str,
    entity_type: str | None = None,
    org_id: UUID | None = None,
    query: str | None = None,
    lookup: str | None = None,
    requested_by: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run venue rules and return model batches to enqueue after commit."""
    if review_scope not in _REVIEW_SCOPES:
        raise ValidationError("Invalid review_scope", field="review_scope")
    if entity_type is not None and entity_type not in ENTITY_TYPES:
        raise ValidationError("Invalid entity_type", field="entity_type")
    if lookup is not None and lookup not in _LOOKUPS:
        raise ValidationError("Invalid lookup", field="lookup")
    if lookup == "google" and not os.getenv("GOOGLE_PLACES_API_KEY", "").strip():
        raise ValidationError("Google Places is not configured", field="lookup")
    _fail_stale_runs(session)
    if over_budget(session):
        raise ValidationError(
            "Monthly location-sweep budget is used",
            field="monthly_cost_limit_usd",
        )
    active = session.scalar(
        select(LocationScanRun.id).where(LocationScanRun.status.in_(_ACTIVE)).limit(1)
    )
    if active is not None:
        raise LocationScanBusy()
    now = datetime.now(timezone.utc)
    run = LocationScanRun(
        status="queued",
        requested_by=requested_by,
        org_id=org_id,
        review_scope=review_scope,
        entity_type=entity_type,
        updated_at=now,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise LocationScanBusy() from exc

    counts = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "cleared": 0,
        "auto_applied": 0,
    }
    truncated = False
    queued: dict[str, list[str]] = {"organization": [], "activity": []}
    if entity_type != "location":
        orgs = list(session.scalars(_org_stmt(org_id, query, review_scope)).all())
        if len(orgs) > _MAX_SWEEP:
            orgs = orgs[:_MAX_SWEEP]
            truncated = True
    else:
        orgs = []
    activities: list[Activity] = []
    if entity_type in (None, "activity") and not truncated:
        activities = list(
            session.scalars(_activity_stmt(org_id, query, review_scope)).all()
        )
    org_ids = {org.id for org in orgs}
    org_ids.update(activity.org_id for activity in activities)
    context = _load_context(session, list(org_ids))
    seen = 0
    auto_budget: dict[str, Any] = {"applied": 0, "capped": False}
    if entity_type in (None, "organization"):
        for org in orgs:
            seen += 1
            _count(
                counts,
                _scan_org(session, org, context, run.id, queued, auto_budget),
            )
            if len(queued["organization"]) >= _MAX_MODEL or auto_budget["capped"]:
                truncated = True
    if activities and not truncated:
        for activity in activities:
            if seen >= _MAX_SWEEP:
                truncated = True
                break
            seen += 1
            _count(
                counts,
                _scan_activity(session, activity, context, run.id, queued),
            )
            if len(queued["activity"]) >= _MAX_MODEL:
                truncated = True
                break
    if entity_type in (None, "location"):
        venues = list(
            session.scalars(_location_stmt(org_id, query, review_scope)).all()
        )
        chains = location_quality.area_chains(
            session, [venue.area_id for venue in venues]
        )
        for venue in venues:
            if seen >= _MAX_SWEEP:
                truncated = True
                break
            seen += 1
            _count(
                counts,
                location_quality.record_location_finding(
                    session,
                    venue,
                    chains.get(venue.area_id, []),
                    run.id,
                ),
            )
    lookup_ids = (
        lookup_location_ids(
            session,
            review_scope=review_scope,
            org_id=org_id,
            query=query,
            provider=lookup,
        )
        if lookup
        else []
    )
    batches = _batches(queued)
    for index in range(0, len(lookup_ids), _BATCH_SIZE):
        batches.append(
            {
                "entity_type": "location",
                "entity_ids": lookup_ids[index : index + _BATCH_SIZE],
                "lookup": lookup,
            }
        )
    run.total_entities = seen
    run.batches_total = len(batches)
    run.created_count = counts["created"]
    run.updated_count = counts["updated"]
    run.skipped_count = counts["skipped"]
    run.cleared_count = counts["cleared"]
    run.auto_applied_count = counts["auto_applied"]
    model_queued = sum(len(ids) for ids in queued.values())
    run.queued_count = model_queued + len(lookup_ids)
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
    payload["queued_for_model"] = model_queued
    payload["queued_for_lookup"] = len(lookup_ids)
    return payload, batches


def _scan_org(session, org, context, run_id, queued, auto_budget) -> str:
    locations = context["locations"].get(org.id, [])
    if locations:
        if clear_pending(session, "organization", org.id):
            return "cleared"
        return "unchanged"
    register_outcome = consider_open_data(session, org, run_id, auto_budget, context)
    if register_outcome is not None:
        return register_outcome
    if len(queued["organization"]) >= _MAX_MODEL:
        return "unchanged"
    if _dismissed_unresolved(session, "organization", org.id):
        return "skipped"
    if clear_pending(session, "organization", org.id):
        queued["organization"].append(str(org.id))
        return "cleared"
    queued["organization"].append(str(org.id))
    return "unchanged"


def _scan_activity(session, activity, context, run_id, queued) -> str:
    if activity.id in context["linked"]:
        if clear_pending(session, "activity", activity.id):
            return "cleared"
        return "unchanged"
    locations = context["locations"].get(activity.org_id, [])
    if len(locations) == 1:
        return _auto_link(session, activity, locations[0], run_id)
    if not locations:
        return upsert_proposal(
            session,
            entity_type="activity",
            entity_id=activity.id,
            org_id=activity.org_id,
            kind="unresolved",
            source="rule:no_venue",
            rationale="Organization has no location",
            scan_run_id=run_id,
        )
    priced = context["priced"].get(activity.id, set())
    org_location_ids = {location.id for location in locations}
    priced = {item for item in priced if item in org_location_ids}
    if len(priced) == 1:
        target_id = next(iter(priced))
        return upsert_proposal(
            session,
            entity_type="activity",
            entity_id=activity.id,
            org_id=activity.org_id,
            kind="link_existing",
            source="rule:pricing_schedule",
            target_location_id=target_id,
            rationale="Pricing or schedule already names this venue",
            scan_run_id=run_id,
        )
    matched = [
        location
        for location in locations
        if _name_matches(activity.name, context["labels"].get(location.id, []))
    ]
    if len(matched) == 1:
        return upsert_proposal(
            session,
            entity_type="activity",
            entity_id=activity.id,
            org_id=activity.org_id,
            kind="link_existing",
            source="rule:name_area",
            target_location_id=matched[0].id,
            rationale="Activity name matches the venue district",
            scan_run_id=run_id,
        )
    if len(queued["activity"]) >= _MAX_MODEL:
        return "unchanged"
    if _dismissed_unresolved(session, "activity", activity.id):
        return "skipped"
    cleared = clear_pending(session, "activity", activity.id)
    queued["activity"].append(str(activity.id))
    return "cleared" if cleared else "unchanged"


def _auto_link(session, activity, location, run_id) -> str:
    if dismissed_same(
        session,
        entity_type="activity",
        entity_id=activity.id,
        kind="link_existing",
        target_location_id=location.id,
        proposed_location=None,
    ):
        return "skipped"
    existing = session.get(ActivityLocation, (activity.id, location.id))
    if existing is None:
        session.add(ActivityLocation(activity_id=activity.id, location_id=location.id))
        session.flush()
    return upsert_proposal(
        session,
        entity_type="activity",
        entity_id=activity.id,
        org_id=activity.org_id,
        kind="link_existing",
        source="rule:single_location",
        status="applied",
        target_location_id=location.id,
        rationale="Organization has one location",
        scan_run_id=run_id,
        decided_by=f"location-scan:{run_id}",
    )


def _load_context(session: Session, org_ids: list[UUID]) -> dict[str, Any]:
    locations: dict[Any, list[Location]] = {}
    labels: dict[Any, list[str]] = {}
    if not org_ids:
        return {"locations": locations, "labels": labels, "linked": set(), "priced": {}}
    rows = list(
        session.scalars(select(Location).where(Location.org_id.in_(org_ids))).all()
    )
    area_ids = {row.area_id for row in rows}
    areas = {}
    if area_ids:
        areas = {
            area.id: area
            for area in session.scalars(
                select(GeographicArea).where(GeographicArea.id.in_(area_ids))
            ).all()
        }
    for row in rows:
        locations.setdefault(row.org_id, []).append(row)
        labels[row.id] = _area_labels(areas.get(row.area_id))
    activity_ids = list(
        session.scalars(select(Activity.id).where(Activity.org_id.in_(org_ids))).all()
    )
    linked: set[Any] = set()
    priced: dict[Any, set[Any]] = {}
    if activity_ids:
        linked = set(
            session.scalars(
                select(ActivityLocation.activity_id).where(
                    ActivityLocation.activity_id.in_(activity_ids)
                )
            ).all()
        )
        for activity_id, location_id in session.execute(
            select(ActivityPricing.activity_id, ActivityPricing.location_id).where(
                ActivityPricing.activity_id.in_(activity_ids)
            )
        ):
            priced.setdefault(activity_id, set()).add(location_id)
        for activity_id, location_id in session.execute(
            select(ActivitySchedule.activity_id, ActivitySchedule.location_id).where(
                ActivitySchedule.activity_id.in_(activity_ids)
            )
        ):
            priced.setdefault(activity_id, set()).add(location_id)
    return {
        "locations": locations,
        "labels": labels,
        "linked": linked,
        "priced": priced,
    }


def _org_stmt(org_id, query, review_scope):
    stmt = select(Organization).order_by(Organization.name, Organization.id)
    if org_id is not None:
        stmt = stmt.where(Organization.id == org_id)
    if query:
        stmt = stmt.where(Organization.name.ilike(ilike_pattern(query), escape="\\"))
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    return stmt


def _location_stmt(org_id, query, review_scope):
    stmt = (
        select(Location)
        .join(Organization, Organization.id == Location.org_id)
        .order_by(Location.address, Location.id)
    )
    if review_scope != "all":
        stmt = stmt.where(Organization.review_status == "pending_review")
    if org_id is not None:
        stmt = stmt.where(Location.org_id == org_id)
    if query:
        pattern = ilike_pattern(query)
        stmt = stmt.where(
            or_(
                Location.address.ilike(pattern, escape="\\"),
                Organization.name.ilike(pattern, escape="\\"),
            )
        )
    return stmt


def _activity_stmt(org_id, query, review_scope):
    stmt = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .order_by(Activity.name, Activity.id)
    )
    if review_scope != "all":
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


def _dismissed_unresolved(session: Session, entity_type: str, entity_id) -> bool:
    """A dismissed 'nothing to propose' row is not sent to the model again."""
    return dismissed_same(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        kind="unresolved",
        target_location_id=None,
        proposed_location=None,
    )


def _area_labels(area: GeographicArea | None) -> list[str]:
    """District tags a name can carry: HK area tags, plus Latin district names."""
    if area is None:
        return []
    found: list[str] = []
    raw = [area.name, *(area.name_translations or {}).values()]
    for label in raw:
        text = str(label or "").strip()
        if len(text) < 2:
            continue
        if text in HK_AREAS:
            found.append(text.casefold())
            continue
        found.extend(tag.casefold() for tag in HK_AREAS if tag in text)
        if not _has_cjk(text):
            found.append(text.casefold())
    return list(dict.fromkeys(found))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _name_matches(name: str | None, labels: list[str]) -> bool:
    text = (name or "").casefold()
    return any(label in text for label in labels)


def _batches(queued: dict[str, list[str]]) -> list[dict[str, Any]]:
    batches = []
    for entity_type, ids in queued.items():
        for index in range(0, len(ids), _BATCH_SIZE):
            batches.append(
                {
                    "entity_type": entity_type,
                    "entity_ids": ids[index : index + _BATCH_SIZE],
                }
            )
    return batches


def _count(counts: dict[str, int], outcome: str) -> None:
    if outcome in counts:
        counts[outcome] += 1


def _fail_stale_runs(session: Session) -> None:
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    now = datetime.now(timezone.utc)
    stale = session.scalars(
        select(LocationScanRun).where(
            LocationScanRun.status.in_(_ACTIVE),
            or_(
                LocationScanRun.updated_at < cutoff,
                LocationScanRun.updated_at.is_(None),
            ),
        )
    ).all()
    for run in stale:
        run.status = "failed"
        run.error = "No batch completed before the sweep went stale"
        run.finished_at = now
        run.updated_at = now
