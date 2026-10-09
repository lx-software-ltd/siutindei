"""Nominatim lookup for a proposed venue address."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode

from app.api.admin_address_search import (
    NOMINATIM_SEARCH_URL,
    _get_nominatim_headers,
)
from app.services.aws_proxy import AwsProxyError, http_invoke
from app.services.location_fix_districts import in_hong_kong_bbox
from app.utils.logging import get_logger

logger = get_logger(__name__)

_HONG_KONG = re.compile(r"hong kong|香港", re.IGNORECASE)


def geocode_address(address: str) -> tuple[float, float] | None:
    """Return a map pin for an address, or None when lookup finds nothing."""
    found = lookup_address(address)
    if found is None:
        return None
    return found["lat"], found["lng"]


def lookup_address(address: str) -> dict[str, Any] | None:
    """Return the first Hong Kong Nominatim hit, without a country filter.

    Nominatim files Hong Kong under China, so ``countrycodes=hk`` matches
    nothing. Results outside the Hong Kong box are dropped.
    """
    text = address.strip()
    if len(text) < 3:
        return None
    headers = _get_nominatim_headers()
    if headers is None:
        logger.warning("Nominatim headers are not configured")
        return None
    query = text if _HONG_KONG.search(text) else f"{text}, Hong Kong"
    params = urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": "1",
        }
    )
    url = f"{NOMINATIM_SEARCH_URL}?{params}"
    try:
        result = http_invoke("GET", url, headers=headers, timeout=10)
    except AwsProxyError as exc:
        logger.warning("Address geocode failed: %s", exc.code)
        return None
    status = int(result.get("status") or 0)
    if status != 200:
        logger.warning("Address geocode failed with status %s", status)
        return None
    try:
        payload = json.loads(result.get("body") or "")
    except json.JSONDecodeError:
        logger.warning("Address geocode returned invalid JSON")
        return None
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    try:
        lat = float(first.get("lat"))
        lng = float(first.get("lon"))
        rank = int(first.get("place_rank") or 0)
    except (TypeError, ValueError):
        return None
    if not in_hong_kong_bbox(lat, lng):
        return None
    display = str(first.get("display_name") or "")
    return {
        "lat": lat,
        "lng": lng,
        "place_rank": rank,
        "type": str(first.get("type") or ""),
        "display_name": display[:300],
    }
