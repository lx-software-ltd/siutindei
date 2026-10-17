"""Drop suggestions the catalog already has, and refresh stale currents."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ActivityPricing, ActivitySchedule, Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal
from app.services.enrichment.apply_rows import activity_by_name, location_by_address


def prepare_proposals(
    session: Session,
    org: Organization,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Refresh organization currents and skip rows that already exist."""
    media_sources = _applied_media_sources(session, org.id)
    kept: list[dict[str, Any]] = []
    for item in items:
        raw_proposed = item.get("proposed")
        proposed: dict[str, Any] = (
            raw_proposed if isinstance(raw_proposed, dict) else {}
        )
        kind = str(item.get("kind") or "")
        current = item
        if kind == "update_organization":
            current = {**item, "current": _live_current(org, proposed)}
        if _already_saved(session, org, kind, proposed, media_sources):
            continue
        kept.append(current)
    return kept


def _live_current(org: Organization, proposed: dict[str, Any]) -> dict[str, Any] | None:
    current: dict[str, Any] = {}
    for key in proposed:
        if key == "copyright_notice":
            continue
        if key == "description_translations":
            translations = org.description_translations or {}
            current[key] = {"zh": translations.get("zh")}
            continue
        if hasattr(org, key):
            current[key] = getattr(org, key)
    return current or None


def _already_saved(
    session: Session,
    org: Organization,
    kind: str,
    proposed: dict[str, Any],
    media_sources: set[str],
) -> bool:
    if kind == "add_media":
        source = str(proposed.get("source_url") or "")
        urls = list(org.media_urls or [])
        return bool(source) and (
            source in urls or source == org.logo_media_url or source in media_sources
        )
    if kind == "create_location":
        return (
            location_by_address(session, org.id, str(proposed.get("address") or ""))
            is not None
        )
    if kind == "create_activity":
        return (
            activity_by_name(session, org.id, str(proposed.get("name") or ""))
            is not None
        )
    if kind == "create_pricing":
        return _pricing_exists(session, org, proposed)
    if kind == "create_schedule":
        return _schedule_exists(session, org, proposed)
    return False


def _pricing_exists(
    session: Session, org: Organization, proposed: dict[str, Any]
) -> bool:
    activity = activity_by_name(
        session, org.id, str(proposed.get("activity_name") or "")
    )
    location = location_by_address(
        session, org.id, str(proposed.get("location_address") or "")
    )
    if activity is None or location is None:
        return False
    try:
        amount = Decimal(str(proposed.get("amount") or "0"))
    except (InvalidOperation, ValueError):
        return False
    pricing_type = str(proposed.get("pricing_type") or "per_class")
    for row in session.scalars(
        select(ActivityPricing).where(
            ActivityPricing.activity_id == activity.id,
            ActivityPricing.location_id == location.id,
        )
    ).all():
        if (
            str(
                row.pricing_type.value
                if hasattr(row.pricing_type, "value")
                else row.pricing_type
            )
            == pricing_type
            and Decimal(str(row.amount)) == amount
        ):
            return True
    return False


def _schedule_exists(
    session: Session, org: Organization, proposed: dict[str, Any]
) -> bool:
    activity = activity_by_name(
        session, org.id, str(proposed.get("activity_name") or "")
    )
    location = location_by_address(
        session, org.id, str(proposed.get("location_address") or "")
    )
    if activity is None or location is None:
        return False
    languages = tuple(
        sorted(str(item) for item in (proposed.get("languages") or ["zh-HK"]))
    )
    for row in session.scalars(
        select(ActivitySchedule).where(
            ActivitySchedule.activity_id == activity.id,
            ActivitySchedule.location_id == location.id,
        )
    ).all():
        stored = tuple(sorted(str(item) for item in (row.languages or [])))
        if stored == languages:
            return True
    return False


def _applied_media_sources(session: Session, org_id: object) -> set[str]:
    rows = session.scalars(
        select(OrgEnrichmentProposal).where(
            OrgEnrichmentProposal.org_id == org_id,
            OrgEnrichmentProposal.kind == "add_media",
            OrgEnrichmentProposal.status == "applied",
        )
    ).all()
    sources: set[str] = set()
    for row in rows:
        value = row.proposed_value if isinstance(row.proposed_value, dict) else {}
        source = str(value.get("source_url") or "")
        if source:
            sources.add(source)
    return sources
