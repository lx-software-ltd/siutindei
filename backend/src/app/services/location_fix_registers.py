"""Match a venue-less organization to the EDB school register."""

from __future__ import annotations

import csv
import difflib
import io
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_resource_location import _create_location
from app.db.models import ActivityLocation, GeographicArea, Organization
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.aws_proxy import http_invoke
from app.services.location_fix_apply import _link_sole_venue
from app.services.location_fix_districts import in_hong_kong_bbox
from app.services.location_fix_quality import area_chains
from app.services.location_fixes import clear_pending, dismissed_same, upsert_proposal
from app.utils.logging import get_logger

logger = get_logger(__name__)

EDB_SCHOOLS_URL = (
    "https://www.edb.gov.hk/attachment/en/student-parents/"
    "sch-info/sch-search/sch-location-info/SCH_LOC_EDB.csv"
)
_MIN_SIMILARITY = 0.8
_AUTO_APPLY_SIMILARITY = 0.95
_MAX_AUTO_APPLY = 200
_KEEP_UPPER = re.compile(r"^(G/F|\d+/F|UG/F|LG/F|M/F|N\.T\.|HK|[IVX]+|\(?[IVX]+\)?)$")
_TOKEN = re.compile(r"[^a-z0-9]+")
_ROWS: dict[str, dict[str, Any]] | None = None


def edb_register() -> dict[str, dict[str, Any]]:
    """School number to register row. Empty when the file cannot be loaded."""
    global _ROWS
    if _ROWS is None:
        _ROWS = _load_register()
    return _ROWS


def clear_edb_cache() -> None:
    """Drop the cached register. Tests and a fresh deploy start empty."""
    global _ROWS
    _ROWS = None


def parse_edb_csv(text: str) -> dict[str, dict[str, Any]]:
    """Index fictional or live EDB rows by school number."""
    found: dict[str, dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    for raw in reader:
        school_no = str(raw.get("SCHOOL NO.") or "").strip()
        if not school_no:
            continue
        try:
            lat = float(raw.get("LATITUDE") or "")
            lng = float(raw.get("LONGITUDE") or "")
        except ValueError:
            continue
        if not in_hong_kong_bbox(lat, lng):
            continue
        found[school_no] = {
            "school_no": school_no,
            "name": str(raw.get("ENGLISH NAME") or "").strip(),
            "name_zh": str(raw.get("中文名稱") or "").strip(),
            "address": str(raw.get("ENGLISH ADDRESS") or "").strip(),
            "address_zh": str(raw.get("中文地址") or "").strip(),
            "lat": lat,
            "lng": lng,
            "district": str(raw.get("DISTRICT") or "").strip(),
            "category": str(raw.get("ENGLISH CATEGORY") or "").strip(),
        }
    return found


def name_similarity(left: str, right: str) -> float:
    """Ratio of two names after lower-casing and dropping punctuation."""
    return difflib.SequenceMatcher(None, _norm(left), _norm(right)).ratio()


def consider_open_data(
    session: Session,
    org: Organization,
    run_id: UUID,
    auto_budget: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> str | None:
    """Propose or create a venue from the register. None leaves the model path."""
    if (org.source or "") != "edb" or not str(org.source_id or "").strip():
        return None
    row = edb_register().get(str(org.source_id).strip())
    if row is None:
        return None
    similarity = name_similarity(org.name, row["name"])
    if similarity < _MIN_SIMILARITY or not row["address"]:
        return None
    area = _district_area(session, row["district"])
    if area is None:
        return None
    proposed = _proposed(row, area, similarity)
    if dismissed_same(
        session,
        entity_type="organization",
        entity_id=org.id,
        kind="create_location",
        target_location_id=None,
        proposed_location=proposed,
        source="rule:open_data",
    ):
        clear_pending(session, "organization", org.id)
        return "skipped"
    if similarity < _AUTO_APPLY_SIMILARITY:
        return _store(session, org, run_id, proposed, similarity, applied=False)
    if int(auto_budget.get("applied") or 0) >= _MAX_AUTO_APPLY:
        auto_budget["capped"] = True
        return _store(session, org, run_id, proposed, similarity, applied=False)
    location = _create(session, org, proposed)
    if location is None:
        return _store(session, org, run_id, proposed, similarity, applied=False)
    _link_sole_venue(session, org.id, location.id)
    _remember_venue(session, org.id, location, context)
    proposed["location_id"] = str(location.id)
    auto_budget["applied"] = int(auto_budget.get("applied") or 0) + 1
    return _store(session, org, run_id, proposed, similarity, applied=True)


def _remember_venue(session: Session, org_id, location, context) -> None:
    """The activity pass uses the preloaded context, so a new venue must be added."""
    if context is None:
        return
    context.setdefault("locations", {})[org_id] = [location]
    linked = session.scalars(
        select(ActivityLocation.activity_id).where(
            ActivityLocation.location_id == location.id
        )
    ).all()
    context.setdefault("linked", set()).update(linked)


def _load_register() -> dict[str, dict[str, Any]]:
    try:
        result = http_invoke("GET", EDB_SCHOOLS_URL, timeout=20)
    except Exception as exc:
        logger.warning("EDB register lookup failed: %s", type(exc).__name__)
        return {}
    if int(result.get("status") or 0) != 200:
        logger.warning("EDB register lookup failed")
        return {}
    return parse_edb_csv(str(result.get("body") or ""))


def _proposed(row: dict[str, Any], area: GeographicArea, similarity: float) -> dict:
    return {
        "address": _title(row["address"]),
        "address_zh": row["address_zh"],
        "area_id": str(area.id),
        "area_name": area.name,
        "lat": round(float(row["lat"]), 6),
        "lng": round(float(row["lng"]), 6),
        "register": {
            "name": row["name"],
            "name_zh": row["name_zh"],
            "school_no": row["school_no"],
            "category": row["category"],
            "name_similarity": round(similarity, 3),
        },
    }


def _store(
    session: Session,
    org: Organization,
    run_id: UUID,
    proposed: dict[str, Any],
    similarity: float,
    *,
    applied: bool,
) -> str:
    return upsert_proposal(
        session,
        entity_type="organization",
        entity_id=org.id,
        org_id=org.id,
        kind="create_location",
        source="rule:open_data",
        status="applied" if applied else "pending",
        proposed_location=proposed,
        confidence=Decimal(str(round(similarity, 3))),
        rationale=f"EDB school register match ({similarity:.0%})",
        scan_run_id=run_id,
        decided_by=f"location-scan:{run_id}" if applied else None,
    )


def _create(session: Session, org: Organization, proposed: dict[str, Any]):
    try:
        location = _create_location(
            LocationRepository(session),
            {
                "org_id": str(org.id),
                "area_id": proposed["area_id"],
                "address": proposed["address"],
                "lat": proposed["lat"],
                "lng": proposed["lng"],
            },
        )
    except ValidationError:
        logger.warning("EDB venue was not created for organization %s", org.id)
        return None
    session.add(location)
    session.flush()
    return location


def _district_area(session: Session, district: str) -> GeographicArea | None:
    wanted = district.strip().casefold()
    if not wanted:
        return None
    rows = list(
        session.scalars(
            select(GeographicArea).where(
                GeographicArea.level == "district",
                GeographicArea.active.is_(True),
            )
        ).all()
    )
    matches = [area for area in rows if _named(area, wanted)]
    if len(matches) == 1:
        return matches[0]
    chains = area_chains(session, [area.id for area in matches])
    under_hk = []
    for area in matches:
        chain = chains.get(area.id, [])
        if any(str(item.code or "").upper() == "HK" for item in chain):
            under_hk.append(area)
    if len(under_hk) == 1:
        return under_hk[0]
    return None


def _named(area: GeographicArea, wanted: str) -> bool:
    labels = [area.name, *(area.name_translations or {}).values()]
    return any(str(label or "").strip().casefold() == wanted for label in labels)


def _title(address: str) -> str:
    words = []
    for word in address.split():
        if _KEEP_UPPER.match(word) or any(char.isdigit() for char in word):
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)[:500]


def _norm(value: str) -> str:
    return _TOKEN.sub(" ", (value or "").lower()).strip()
