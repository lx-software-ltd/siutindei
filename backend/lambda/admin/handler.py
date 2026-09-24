"""Lambda entrypoint for admin CRUD APIs and suggestion enrichment."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Mapping

from app.api.admin import lambda_handler as _handler

_EnrichHandler = Callable[[Mapping[str, Any], Any], dict[str, Any]]
_enrich_handler: _EnrichHandler | None = None


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Dispatch SQS enrichment, otherwise admin HTTP."""
    if _is_sqs_event(event):
        return _category_suggestion_handler()(event, context)
    return _handler(event, context)


def _is_sqs_event(event: Mapping[str, Any]) -> bool:
    records = event.get("Records")
    if not isinstance(records, list) or not records:
        return False
    first = records[0]
    return isinstance(first, dict) and first.get("eventSource") == "aws:sqs"


def _category_suggestion_handler() -> _EnrichHandler:
    """Load the SQS handler without importing the lambda package name."""
    global _enrich_handler
    if _enrich_handler is not None:
        return _enrich_handler
    module_path = (
        Path(__file__).resolve().parents[1] / "category_suggestions" / "handler.py"
    )
    spec = importlib.util.spec_from_file_location(
        "category_suggestion_sqs_handler",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Category suggestion handler is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = module.lambda_handler
    _enrich_handler = handler
    return handler
