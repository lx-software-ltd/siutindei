"""Queries and area labels for a location sweep."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
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
from app.services.name_fix_query import ilike_pattern
from app.services.name_sanitizer_areas import HK_AREAS


def load_context(session: Session, org_ids: list[UUID]) -> dict[str, Any]:
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


def org_stmt(org_id, query, review_scope):
    stmt = select(Organization).order_by(Organization.name, Organization.id)
    if org_id is not None:
        stmt = stmt.where(Organization.id == org_id)
    if query:
        stmt = stmt.where(Organization.name.ilike(ilike_pattern(query), escape="\\"))
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    return stmt


def location_stmt(org_id, query, review_scope):
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


def activity_stmt(org_id, query, review_scope):
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


def name_matches(name: str | None, labels: list[str]) -> bool:
    text = (name or "").casefold()
    return any(label in text for label in labels)


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
