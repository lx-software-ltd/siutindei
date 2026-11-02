"""Lambda entrypoint for listing-event ingest."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.listing_events import lambda_handler as _handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Delegate to the listing-events ingest handler."""

    return _handler(event, context)
