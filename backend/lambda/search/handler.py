"""Lambda entrypoint for search."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.search import lambda_handler as _handler


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Delegate to the search handler."""

    return _handler(event, context)
