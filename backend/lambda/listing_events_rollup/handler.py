"""Lambda entrypoint for listing-events daily rollup."""

from __future__ import annotations

from typing import Any
from typing import Mapping

from app.services.listing_events_rollup import lambda_handler as _handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Delegate to the listing-events rollup handler."""

    return _handler(event, context)
