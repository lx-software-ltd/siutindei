"""Background pin lookup for venues that already have an address."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import Location, Organization
from app.db.models.location_fix import LocationFixProposal
from app.services.aws_proxy import AwsProxyError, http_invoke
from app.services.location_fix_districts import in_hong_kong_bbox, pin_consistency
from app.services.location_fix_geocode import AddressLookupFailed, lookup_address
from app.services.location_fix_model import _finish_batch
from app.services.location_fix_quality import area_chains
from app.services.location_fix_query import load_settings, month_cost
from app.services.name_fix_query import ilike_pattern
from app.utils.logging import get_logger

logger = get_logger(__name__)

LOOKUP_PAUSE_SECONDS = 2.2
_FRESH_DAYS = 90
_GOOGLE_URL = "https://places.googleapis.com/v1/places/"
_GOOGLE_USD = Decimal("0.017")
_PRECISE_RANK = 28
_STREET_RANK = 26
_LOOKUP_SOURCES = (
    "rule:missing_coordinates",
    "lookup:nominatim",
    "lookup:google",
)


def lookup_location_ids(
    session: Session,
    *,
    review_scope: str,
    org_id: UUID | None,
    query: str | None,
    provider: str,
) -> list[str]:
    """Pending missing-pin venues that still need this provider."""
    stmt = (
        select(
            LocationFixProposal.entity_id,
            LocationFixProposal.proposed_location,
            Location.place_id,
        )
        .join(Location, Location.id == LocationFixProposal.entity_id)
        .join(Organization, Organization.id == Location.org_id)
        .where(
            LocationFixProposal.status == "pending",
            LocationFixProposal.entity_type == "location",
            LocationFixProposal.kind == "update_location",
            LocationFixProposal.source.in_(_LOOKUP_SOURCES),
        )
        .order_by(Location.address, Location.id)
    )
    if review_scope != "all":
        stmt = stmt.where(Organization.review_status == "pending_review")
    if org_id is not None:
        stmt = stmt.where(Location.org_id == org_id)
    if query and query.strip():
        pattern = ilike_pattern(query.strip())
        stmt = stmt.where(
            or_(
                Location.address.ilike(pattern, escape="\\"),
                Organization.name.ilike(pattern, escape="\\"),
            )
        )
    found: list[str] = []
    for entity_id, proposed, place_id in session.execute(stmt):
        if provider == "google" and not str(place_id or "").strip():
            continue
        if _blocked(proposed, provider) or _fresh(proposed, provider):
            continue
        found.append(str(entity_id))
    return found


def affordable_google_lookups(session: Session) -> int:
    """How many Place Details calls the remaining monthly budget can pay."""
    limit = Decimal(str(load_settings(session).monthly_cost_limit_usd))
    room = limit - Decimal(str(month_cost(session)))
    if room < _GOOGLE_USD:
        return 0
    return int(room / _GOOGLE_USD)


def within_google_budget(session: Session, spent_here: Decimal) -> bool:
    """True when one more Place Details call still fits the monthly limit."""
    limit = Decimal(str(load_settings(session).monthly_cost_limit_usd))
    spent = Decimal(str(month_cost(session))) + spent_here
    return spent + _GOOGLE_USD <= limit


def process_lookup_batch(
    scan_run_id: UUID,
    provider: str,
    entity_ids: list[str],
    *,
    message_id: str = "",
    receive_count: int = 1,
) -> bool:
    """Grade one batch of pin lookups. Return True when SQS can delete it."""
    del receive_count
    cost = Decimal("0")
    failed = False
    error: str | None = None
    try:
        with Session(get_engine()) as session:
            venues = _venues(session, entity_ids)
            chains = area_chains(session, [venue.area_id for venue in venues.values()])
            for index, entity_id in enumerate(entity_ids):
                venue = venues.get(entity_id)
                proposal = _pending(session, entity_id)
                if venue is None or proposal is None:
                    continue
                if provider == "google" and not within_google_budget(session, cost):
                    logger.warning("Google pin lookup stopped at the monthly budget")
                    break
                hit, spent, problem = _resolve(provider, venue)
                cost += spent
                if problem:
                    failed = True
                    error = problem
                    break
                _store(proposal, hit, provider, chains.get(venue.area_id, []))
                if provider == "nominatim" and index < len(entity_ids) - 1:
                    time.sleep(LOOKUP_PAUSE_SECONDS)
            _finish_batch(
                session,
                scan_run_id,
                {"cost_usd": float(cost)},
                message_id,
                failed=failed,
                failed_entities=len(entity_ids) if failed else 0,
                error=error,
            )
            session.commit()
    except Exception as exc:
        logger.exception("Pin lookup batch failed")
        with Session(get_engine()) as session:
            _finish_batch(
                session,
                scan_run_id,
                {"cost_usd": float(cost)},
                message_id,
                failed=True,
                failed_entities=len(entity_ids),
                error=str(exc) or type(exc).__name__,
            )
            session.commit()
    return True


def grade_hit(rank: int) -> str:
    """Nominatim place rank inside Hong Kong: precise, street, or coarse."""
    if rank >= _PRECISE_RANK:
        return "precise"
    if rank >= _STREET_RANK:
        return "street"
    return "coarse"


def _resolve(
    provider: str, venue: Location
) -> tuple[dict[str, Any] | None, Decimal, str | None]:
    if provider == "google":
        return _google(str(venue.place_id or "").strip())
    try:
        return lookup_address(str(venue.address or "")), Decimal("0"), None
    except AddressLookupFailed:
        return None, Decimal("0"), "Address lookup failed"


def _google(place_id: str) -> tuple[dict[str, Any] | None, Decimal, str | None]:
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key or not place_id:
        return None, Decimal("0"), "Google Places is not configured"
    url = f"{_GOOGLE_URL}{quote(place_id)}"
    try:
        result = http_invoke(
            "GET",
            url,
            headers={
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "location,id,businessStatus",
            },
            timeout=10,
        )
    except AwsProxyError as exc:
        logger.warning("Google place lookup failed: %s", exc.code)
        return None, Decimal("0"), "Google place lookup failed"
    status = int(result.get("status") or 0)
    if status == 404:
        return None, _GOOGLE_USD, None
    if status != 200:
        logger.warning("Google place lookup failed with status %s", status)
        return None, Decimal("0"), "Google place lookup failed"
    try:
        payload = json.loads(result.get("body") or "")
    except json.JSONDecodeError:
        return None, _GOOGLE_USD, "Google place lookup failed"
    if not isinstance(payload, dict):
        return None, _GOOGLE_USD, None
    location = payload.get("location") or {}
    if not isinstance(location, dict):
        return None, _GOOGLE_USD, None
    try:
        lat = float(location["latitude"])
        lng = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, _GOOGLE_USD, None
    returned = str(payload.get("id") or "")
    if not returned.endswith(place_id):
        return None, _GOOGLE_USD, None
    if not in_hong_kong_bbox(lat, lng):
        return None, _GOOGLE_USD, None
    closed = payload.get("businessStatus") == "CLOSED_PERMANENTLY"
    return (
        {
            "lat": lat,
            "lng": lng,
            "place_rank": 30,
            "type": "google_place",
            "display_name": place_id,
            "closed": closed,
        },
        _GOOGLE_USD,
        None,
    )


def _store(
    proposal: LocationFixProposal,
    hit: dict[str, Any] | None,
    provider: str,
    areas: list,
) -> None:
    proposed = dict(proposal.proposed_location or {})
    if _blocked(proposed, provider):
        return
    lookup: dict[str, Any] = {
        "provider": provider,
        "looked_up_at": datetime.now(timezone.utc).isoformat(),
    }
    if hit is None:
        lookup["grade"] = "miss"
        lookup["district_consistent"] = None
        proposed.pop("lat", None)
        proposed.pop("lng", None)
    else:
        grade = "coarse" if hit.get("closed") else grade_hit(int(hit["place_rank"]))
        consistent, other = pin_consistency(hit["lat"], hit["lng"], areas)
        lookup.update(
            {
                "grade": grade,
                "place_rank": hit["place_rank"],
                "osm_type": hit.get("type") or "",
                "display_name": hit.get("display_name") or "",
                "district_consistent": consistent,
                "other_district": other,
            }
        )
        if grade in {"precise", "street"}:
            proposed["lat"] = round(float(hit["lat"]), 6)
            proposed["lng"] = round(float(hit["lng"]), 6)
    proposed["lookup"] = lookup
    proposal.proposed_location = proposed
    proposal.source = f"lookup:{provider}"


def _venues(session: Session, entity_ids: list[str]) -> dict[str, Location]:
    ids: list[UUID] = []
    for raw in entity_ids:
        try:
            ids.append(UUID(str(raw)))
        except ValueError:
            continue
    if not ids:
        return {}
    rows = session.scalars(select(Location).where(Location.id.in_(ids))).all()
    return {str(row.id): row for row in rows}


def _pending(session: Session, entity_id: str) -> LocationFixProposal | None:
    try:
        parsed = UUID(str(entity_id))
    except ValueError:
        return None
    return session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.entity_type == "location",
            LocationFixProposal.entity_id == parsed,
            LocationFixProposal.status == "pending",
        )
    ).first()


def _blocked(proposed: dict | None, provider: str) -> bool:
    """A pasted pin, and a Google pin, are not replaced by Nominatim."""
    lookup = (proposed or {}).get("lookup") or {}
    existing = lookup.get("provider")
    if existing == "manual":
        return True
    has_pin = (proposed or {}).get("lat") is not None and (proposed or {}).get(
        "lng"
    ) is not None
    return bool(provider == "nominatim" and existing == "google" and has_pin)


def _fresh(proposed: dict | None, provider: str) -> bool:
    lookup = (proposed or {}).get("lookup") or {}
    if lookup.get("provider") != provider or not lookup.get("looked_up_at"):
        return False
    text = str(lookup["looked_up_at"])
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - stamp < timedelta(days=_FRESH_DAYS)
