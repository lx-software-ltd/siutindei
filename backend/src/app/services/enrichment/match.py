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
        if key in {"description_translations", "name_translations"}:
            stored = getattr(org, key, None) or {}
            wanted = proposed.get(key)
            languages = list(wanted) if isinstance(wanted, dict) and wanted else ["zh"]
            current[key] = {
                language: stored.get(language)
                for language in languages
                if isinstance(stored, dict)
            }
            continue
        if hasattr(org, key):
            current[key] = getattr(org, key)
    return current or None


def display_current(
    org: Organization,
    *,
    kind: str,
    field: str | None,
    proposed: dict[str, Any],
    venues: list[Any],
    activity_names: list[str],
    stored_current: object = None,
    pricing_count: int = 0,
    schedule_count: int = 0,
) -> dict[str, Any] | None:
    """Live catalog for the enrichment Now line.

    The stored crawl snapshot stays on the proposal. Apply still
    compares against that snapshot.
    """
    if kind == "update_organization":
        raw = _live_current(org, proposed) or {}
    elif kind == "add_media":
        raw = _media_current(org, proposed, field)
    elif kind == "create_location":
        raw = _location_current(proposed, venues)
    elif kind == "create_activity":
        raw = _activity_current(proposed, activity_names)
    elif kind == "create_pricing":
        raw = {"prices": pricing_count} if pricing_count else {}
    elif kind == "create_schedule":
        raw = {"schedules": schedule_count} if schedule_count else {}
    else:
        return None
    kept = {key: value for key, value in raw.items() if _present(value)}
    if kind == "update_organization" and _changed_since_crawl(
        org, stored_current, proposed
    ):
        kept["changed_since_crawl"] = True
    return kept or None


def _media_current(
    org: Organization, proposed: dict[str, Any], field: str | None
) -> dict[str, Any]:
    source = str(proposed.get("source_url") or "")
    urls = [str(url) for url in (org.media_urls or []) if url]
    saved = bool(source) and (source in urls or source == (org.logo_media_url or ""))
    if proposed.get("logo") or field == "logo":
        current: dict[str, Any] = {}
        if org.logo_media_url:
            current["logo"] = "saved"
        if saved:
            current["already_saved"] = True
        return current
    current = {}
    if urls:
        current["photos"] = len(urls)
    if saved:
        current["already_saved"] = True
    return current


def _changed_since_crawl(
    org: Organization, stored: object, proposed: dict[str, Any]
) -> bool:
    """True when apply would refuse because the catalog moved."""
    if "description_translations" in proposed or "name_translations" in proposed:
        key = (
            "description_translations"
            if "description_translations" in proposed
            else "name_translations"
        )
        live_map = getattr(org, key, None) or {}
        stored_map: dict[str, Any] = {}
        if isinstance(stored, dict):
            raw = stored.get(key) or {}
            if isinstance(raw, dict):
                stored_map = raw
        raw_wanted = proposed.get(key)
        wanted = raw_wanted if isinstance(raw_wanted, dict) else {}
        languages = list(wanted) or ["zh"]
        for language in languages:
            live = (
                live_map.get(language) or None if isinstance(live_map, dict) else None
            )
            expected = stored_map.get(language) or None
            if live != expected:
                return True
        return False
    for field in proposed:
        if field == "copyright_notice":
            continue
        live = getattr(org, field, None) or None
        expected = stored.get(field) if isinstance(stored, dict) else None
        expected = expected or None
        if live != expected:
            return True
    return False


def _location_current(proposed: dict[str, Any], venues: list[Any]) -> dict[str, Any]:
    wanted = _folded(proposed.get("address"))
    for venue in venues:
        address = getattr(venue, "address", None)
        if wanted and _folded(address) == wanted:
            return {"address": address}
    if venues:
        return {"venues": len(venues)}
    return {}


def _activity_current(
    proposed: dict[str, Any], activity_names: list[str]
) -> dict[str, Any]:
    wanted = _folded(proposed.get("name"))
    for name in activity_names:
        if wanted and _folded(name) == wanted:
            return {"name": name}
    if activity_names:
        return {"activities": len(activity_names)}
    return {}


def _folded(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _present(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_present(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return bool(value) and any(_present(item) for item in value)
    return True


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
