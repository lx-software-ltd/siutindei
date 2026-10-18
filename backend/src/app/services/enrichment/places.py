"""Match a location proposal to a neighbourhood, then a pin if needed."""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.hk_neighbourhoods import (
    DISTRICT_REGION_ID,
    NEIGHBOURHOODS,
    assign_among,
    neighbourhoods_for,
)
from app.db.models.geographic_area import GeographicArea
from app.services.location_fix_geocode import AddressLookupFailed, lookup_address

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_MIN = 4
_CJK_MIN = 2
_GEOCODE_LIMIT = 5
_GEOCODE_GAP_SECONDS = 1.0
_GEOCODE_CALL_SECONDS = 4.0
# Leave enough of the lookup budget for one Facebook and one Instagram call.
_SOCIAL_RESERVE_SECONDS = 6.0
_OUTSIDE = "The neighbourhood on the page is outside the named district."

Lookup = Callable[[str], dict[str, Any] | None]
Sleep = Callable[[float], None]


class GeocodeBudget:
    """At most five Nominatim calls, one second apart, inside the time left."""

    def __init__(
        self,
        lookup: Lookup | None = None,
        sleep: Sleep | None = None,
        *,
        limit: int = _GEOCODE_LIMIT,
        gap: float = _GEOCODE_GAP_SECONDS,
        deadline: float | None = None,
        call_timeout: float = _GEOCODE_CALL_SECONDS,
        reserve: float = _SOCIAL_RESERVE_SECONDS,
    ) -> None:
        self.lookup = lookup
        self.sleep = sleep or time.sleep
        self.limit = limit
        self.gap = gap
        self.deadline = deadline
        self.call_timeout = call_timeout
        self.reserve = reserve
        self.calls = 0

    def pin(self, address: str) -> tuple[float, float] | None:
        if self.calls >= self.limit or not self._fits(self.gap if self.calls else 0):
            return None
        if self.calls:
            self.sleep(self.gap)
        self.calls += 1
        try:
            found = self._lookup(address)
        except AddressLookupFailed:
            return None
        if not isinstance(found, dict):
            return None
        try:
            return float(found["lat"]), float(found["lng"])
        except (KeyError, TypeError, ValueError):
            return None

    def _lookup(self, address: str) -> dict[str, Any] | None:
        if self.lookup is not None:
            return self.lookup(address)
        return lookup_address(address, timeout=self._timeout())

    def _timeout(self) -> int:
        remaining = self._remaining() - self.reserve
        return max(1, min(int(self.call_timeout), int(remaining)))

    def _fits(self, extra: float) -> bool:
        return self._remaining() > self.reserve + extra

    def _remaining(self) -> float:
        if self.deadline is None:
            return 10_000.0
        return self.deadline - time.monotonic()


def load_index(session: Session) -> _Index:
    """Active areas, loaded once per extract."""
    return _Index.load(session)


def place_fields(
    session: Session,
    proposed: dict[str, Any],
    budget: GeocodeBudget,
    index: _Index | None = None,
) -> dict[str, Any]:
    """Neighbourhood id and path. A district without a confident pin stays a path."""
    index = index or _Index.load(session)
    address = str(proposed.get("address") or "")
    district = _named_district(index, proposed)
    region = _named_region(index, proposed)
    neighbourhood, note = _named_neighbourhood(index, proposed, district)
    method = "neighbourhood"
    if neighbourhood is None:
        neighbourhood, address_note = _address_neighbourhood(index, address, district)
        note = note or address_note
        method = "address"
    if neighbourhood is not None:
        return _with_note(_hit(index, neighbourhood, method), note)
    if district is None:
        district = _address_district(index, address)
    if region is None:
        region = _address_region(index, address)
    if district is not None:
        pinned = _pinned(
            index, budget, address, neighbourhoods_for(district.name), district
        )
        if pinned is not None:
            return _with_note(pinned, note)
        return _with_note(_anchor(index, district, "district"), note)
    if region is not None:
        pinned = _pinned(
            index,
            budget,
            address,
            neighbourhoods_in_region(region.name),
            None,
            region=region,
        )
        if pinned is not None:
            return _with_note(pinned, note)
        return _with_note(_anchor(index, region, "region"), note)
    return _with_note(_pinned(index, budget, address, NEIGHBOURHOODS, None), note)


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
        self.regions = [row for row in rows if row.level == "region"]

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
        return None
    if len(hits) == 1:
        return hits[0]
    return None


def _outside(hits: list[GeographicArea], district: GeographicArea) -> bool:
    return bool(hits) and all(str(area.parent_id) != str(district.id) for area in hits)


_REGION_KEYS = {
    "kowloon": "kowloon",
    "hong kong island": "hong_kong_island",
    "new territories": "new_territories",
    "islands": "islands",
}


def neighbourhoods_in_region(name: str) -> tuple[Any, ...]:
    """Catalog neighbourhoods under one Hong Kong region."""
    key = _REGION_KEYS.get(_fold(name))
    if key is None:
        return ()
    districts = {
        district for district, region in DISTRICT_REGION_ID.items() if region == key
    }
    return tuple(item for item in NEIGHBOURHOODS if item.district in districts)


def _named_region(index: _Index, proposed: dict[str, Any]) -> GeographicArea | None:
    """A region named on the page, including one written in the district field."""
    for key in ("region", "district", "area_name"):
        found = _pick(_exact(index.regions, proposed.get(key)), None)
        if found is not None:
            return found
    return None


def _address_region(index: _Index, address: str) -> GeographicArea | None:
    folded = _fold(address)
    hits: list[GeographicArea] = []
    best = 0
    for area in index.regions:
        for alias in _aliases(area):
            if not _long_enough(alias) or not _contains(folded, alias):
                continue
            if len(alias) > best:
                best = len(alias)
                hits = [area]
            elif len(alias) == best:
                hits.append(area)
    return _pick(hits, None)


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
) -> tuple[GeographicArea | None, str]:
    note = ""
    for key in ("neighbourhood", "area_name"):
        hits = _exact(index.neighbourhoods, proposed.get(key))
        found = _pick(hits, district)
        if found is not None:
            return found, ""
        if district is not None and _outside(hits, district):
            note = _OUTSIDE
    return None, note


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
) -> tuple[GeographicArea | None, str]:
    folded = _fold(address)
    if not folded:
        return None, ""
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
    found = _pick(hits, district)
    if found is not None:
        return found, ""
    if district is not None and _outside(hits, district):
        return None, _OUTSIDE
    return None, ""


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
        "area_anchor_id": str(area.id),
        "area_path": index.path(area),
        "area_match": method,
    }
    if lat is not None and lng is not None:
        payload["lat"] = lat
        payload["lng"] = lng
    return payload


def _anchor(index: _Index, area: GeographicArea, method: str) -> dict[str, Any]:
    """Region or district, so the picker can start there. Not a saved leaf."""
    return {
        "area_anchor_id": str(area.id),
        "area_path": index.path(area),
        "area_match": method,
    }


def _with_note(payload: dict[str, Any] | None, note: str) -> dict[str, Any]:
    body = dict(payload or {})
    if note:
        body["area_note"] = note
    return body


def _pinned(
    index: _Index,
    budget: GeocodeBudget,
    address: str,
    choices: tuple[Any, ...] | list[Any],
    district: GeographicArea | None,
    region: GeographicArea | None = None,
) -> dict[str, Any] | None:
    if not address.strip() or not choices:
        return None
    pin = budget.pin(address)
    if pin is None:
        return None
    assigned = assign_among(choices, pin[0], pin[1])
    if assigned is None or not assigned.confident:
        return None
    child = _match_catalog(index, assigned.neighbourhood, district, region)
    if child is None:
        return None
    return _hit(index, child, "geocode", lat=pin[0], lng=pin[1])


def _match_catalog(
    index: _Index,
    neighbourhood: Any,
    district: GeographicArea | None,
    region: GeographicArea | None = None,
) -> GeographicArea | None:
    names = (neighbourhood.name, neighbourhood.name_zh)
    if district is not None:
        for name in names:
            found = _child_named(index, district, name)
            if found is not None:
                return found
        return None
    if region is not None:
        for name in names:
            found = _under_region(index, region, name)
            if found is not None:
                return found
        return None
    for name in names:
        found = _one_named(index, name)
        if found is not None:
            return found
    return None


def _under_region(
    index: _Index, region: GeographicArea, name: str
) -> GeographicArea | None:
    token = _fold(name)
    if not token:
        return None
    district_ids = {
        str(area.id)
        for area in index.districts
        if str(area.parent_id) == str(region.id)
    }
    hits = [
        area
        for area in index.neighbourhoods
        if str(area.parent_id) in district_ids and token in _aliases(area)
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _one_named(index: _Index, name: str) -> GeographicArea | None:
    token = _fold(name)
    if not token:
        return None
    hits = [area for area in index.neighbourhoods if token in _aliases(area)]
    if len(hits) == 1:
        return hits[0]
    return None
