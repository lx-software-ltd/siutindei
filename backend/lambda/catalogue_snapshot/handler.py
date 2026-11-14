"""Lambda entrypoint for the public website catalogue snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.catalogue_snapshot import lambda_handler as _handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Delegate to the catalogue snapshot handler."""

    return _handler(event, context)
