"""Lambda entrypoint for health check endpoint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.health import lambda_handler as _handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Delegate to health check handler."""
    return _handler(dict(event), context)
