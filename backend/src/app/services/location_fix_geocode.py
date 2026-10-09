"""Nominatim lookup for a proposed venue address."""

from __future__ import annotations

import json
from urllib.parse import urlencode

from app.api.admin_address_search import (
    NOMINATIM_SEARCH_URL,
    _get_nominatim_headers,
)
from app.services.aws_proxy import AwsProxyError, http_invoke
from app.utils.logging import get_logger

logger = get_logger(__name__)


def geocode_address(address: str) -> tuple[float, float] | None:
    """Return a map pin for an address, or None when lookup is unavailable."""
    text = address.strip()
    if len(text) < 3:
        return None
    headers = _get_nominatim_headers()
    if headers is None:
        logger.warning("Nominatim headers are not configured")
        return None
    params = urlencode(
        {
            "q": text,
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "hk",
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
    except (TypeError, ValueError):
        return None
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        return None
    return lat, lng
