"""Match a location proposal to a neighbourhood, then a pin if needed."""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.hk_neighbourhoods import assign_among, neighbourhoods_for
from app.db.models.geographic_area import GeographicArea
from app.services.location_fix_geocode import AddressLookupFailed, lookup_address

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_MIN = 4
_CJK_MIN = 2
_GEOCODE_LIMIT = 5
_GEOCODE_GAP_SECONDS = 1.0

Lookup = Callable[[str], dict[str, Any] | None]
Sleep = Callable[[float], None]


class GeocodeBudget:
    """At most five Nominatim calls, one second apart. A failure is not a miss."""

    def __init__(
        self,
        lookup: Lookup | None = None,
        sleep: Sleep | None = None,
        *,
        limit: int = _GEOCODE_LIMIT,
        gap: float = _GEOCODE_GAP_SECONDS,
    ) -> None:
        self.lookup = lookup or lookup_address
        self.sleep = sleep or time.sleep
        self.limit = limit
        self.gap = gap
        self.calls = 0

    def pin(self, address: str) -> tuple[float, float] | None:
        if self.calls >= self.limit:
            return None
        if self.calls:
            self.sleep(self.gap)
        self.calls += 1
        try:
            found = self.lookup(address)
        except AddressLookupFailed:
            return None
        if not isinstance(found, dict):
            return None
        try:
            return float(found["lat"]), float(found["lng"])
        except (KeyError, TypeError, ValueError):
            return None


def place_fields(
    session: Session,
    proposed: dict[str, Any],
    budget: GeocodeBudget,
) -> dict[str, Any]:
    """Neighbourhood id and path. A district without a confident pin stays a path."""
    index = _Index.load(session)
    address = str(proposed.get("address") or "")
    district = _named_district(index, proposed)
    neighbourhood = _named_neighbourhood(index, proposed, district)
    if neighbourhood is not None:
        return _hit(index, neighbourhood, "neighbourhood")
    from_address = _address_neighbourhood(index, address, district)
    if from_address is not None:
        return _hit(index, from_address, "address")
    if district is None:
        district = _address_district(index, address)
    if district is None:
        return {}
    pin = budget.pin(address) if address.strip() else None
    if pin is None:
        return _district_only(index, district)
    choices = neighbourhoods_for(district.name)
    assigned = assign_among(choices, pin[0], pin[1]) if choices else None
    if assigned is None or not assigned.confident:
        return _district_only(index, district)
    child = _child_named(index, district, assigned.neighbourhood.name)
    if child is None:
        child = _child_named(index, district, assigned.neighbourhood.name_zh)
    if child is None:
        return _district_only(index, district)
    return _hit(index, child, "geocode", lat=pin[0], lng=pin[1])


def _fold(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    return " ".join(_PUNCT_RE.sub(" ", folded).split())


def _long_enough(token: str) -> bool:
    if not token:
        return False
    if _CJK_RE.search(token):
        return len(token) >= _CJK_MIN
    return len(token.replace(" ", "")) >= _LATIN_MIN


def _aliases(area: GeographicArea) -> list[str]:
    names = [area.name]
    translations = area.name_translations or {}
    if isinstance(translations, dict):
        names.extend(value for value in translations.values() if isinstance(value, str))
    folded: list[str] = []
    seen: set[str] = set()
    for name in names:
        token = _fold(name)
        if token and token not in seen:
            seen.add(token)
            folded.append(token)
    return folded


def _contains(haystack: str, alias: str) -> bool:
    if _CJK_RE.search(alias):
        return alias in haystack
    return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", haystack) is not None


class _Index:
    def __init__(self, rows: list[GeographicArea]) -> None:
        self.by_id = {str(row.id): row for row in rows}
        self.neighbourhoods = [row for row in rows if row.level == "neighbourhood"]
        self.districts = [row for row in rows if row.level == "district"]

    @classmethod
    def load(cls, session: Session) -> _Index:
        rows = list(
            session.scalars(
                select(GeographicArea).where(GeographicArea.active.is_(True))
            ).all()
        )
        return cls(rows)

    def path(self, area: GeographicArea) -> str:
        parts: list[str] = []
        current: GeographicArea | None = area
        seen: set[str] = set()
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            if current.level != "country":
                parts.append(current.name)
            parent_id = current.parent_id
            current = self.by_id.get(str(parent_id)) if parent_id else None
        return " · ".join(reversed(parts))


def _exact(areas: list[GeographicArea], text: object) -> list[GeographicArea]:
    token = _fold(str(text or ""))
    if not _long_enough(token):
        return []
    return [area for area in areas if token in _aliases(area)]


def _pick(
    hits: list[GeographicArea], district: GeographicArea | None
) -> GeographicArea | None:
    if district is not None:
        under = [area for area in hits if str(area.parent_id) == str(district.id)]
        if len(under) == 1:
            return under[0]
        if len(under) > 1:
            return None
    if len(hits) == 1:
        return hits[0]
    return None


def _named_district(_index: _Index, proposed: dict[str, Any]) -> GeographicArea | None:
    for key in ("district", "area_name"):
        found = _pick(_exact(_index.districts, proposed.get(key)), None)
        if found is not None:
            return found
    return None


def _named_neighbourhood(
    index: _Index,
    proposed: dict[str, Any],
    district: GeographicArea | None,
) -> GeographicArea | None:
    for key in ("neighbourhood", "area_name"):
        found = _pick(_exact(index.neighbourhoods, proposed.get(key)), district)
        if found is not None:
            return found
    return None


def _address_district(index: _Index, address: str) -> GeographicArea | None:
    folded = _fold(address)
    hits: list[GeographicArea] = []
    best = 0
    for area in index.districts:
        for alias in _aliases(area):
            if _long_enough(alias) and _contains(folded, alias) and len(alias) > best:
                best = len(alias)
                hits = [area]
            elif (
                _long_enough(alias) and _contains(folded, alias) and len(alias) == best
            ):
                hits.append(area)
    return _pick(hits, None)


def _district_aliases_in(index: _Index, address: str) -> list[str]:
    folded = _fold(address)
    found: list[str] = []
    for area in index.districts:
        for alias in _aliases(area):
            if _long_enough(alias) and _contains(folded, alias):
                found.append(alias)
    return found


def _blocked(alias: str, district_aliases: list[str]) -> bool:
    """Skip Central when the address really says Central and Western."""
    for name in district_aliases:
        if len(name) > len(alias) and name.startswith(f"{alias} "):
            return True
    return False


def _address_neighbourhood(
    index: _Index,
    address: str,
    district: GeographicArea | None,
) -> GeographicArea | None:
    folded = _fold(address)
    if not folded:
        return None
    blocked_by = _district_aliases_in(index, address)
    best = 0
    hits: list[GeographicArea] = []
    for area in index.neighbourhoods:
        for alias in _aliases(area):
            if not _long_enough(alias) or _blocked(alias, blocked_by):
                continue
            if not _contains(folded, alias):
                continue
            if len(alias) > best:
                best = len(alias)
                hits = [area]
            elif len(alias) == best:
                hits.append(area)
    return _pick(hits, district)


def _child_named(
    index: _Index, district: GeographicArea, name: str
) -> GeographicArea | None:
    token = _fold(name)
    if not token:
        return None
    hits = [
        area
        for area in index.neighbourhoods
        if str(area.parent_id) == str(district.id) and token in _aliases(area)
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _hit(
    index: _Index,
    area: GeographicArea,
    method: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "area_id": str(area.id),
        "area_path": index.path(area),
        "area_match": method,
    }
    if lat is not None and lng is not None:
        payload["lat"] = lat
        payload["lng"] = lng
    return payload


def _district_only(index: _Index, district: GeographicArea) -> dict[str, Any]:
    return {"area_path": index.path(district), "area_match": "district"}
