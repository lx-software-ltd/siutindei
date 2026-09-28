"""SQS worker that enriches one category suggestion per message."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.events.sqs_batch import failure_response
from app.services.category_suggestions.enrich import process_suggestion
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Enrich suggestions. Poison payloads are acknowledged."""
    del context
    failures: list[str] = []
    for record in event.get("Records", []):
        message_id = str(record.get("messageId") or "")
        try:
            payload = json.loads(record.get("body") or "")
        except json.JSONDecodeError:
            logger.warning("Category suggestion message was not JSON")
            continue
        if not isinstance(payload, dict) or not payload.get("suggestion_id"):
            logger.warning("Category suggestion message is missing suggestion_id")
            continue
        try:
            suggestion_id = UUID(str(payload["suggestion_id"]))
        except ValueError:
            logger.warning("Category suggestion id is not a UUID")
            continue
        receive_count = _receive_count(record)
        force = bool(payload.get("force"))
        try:
            acked = process_suggestion(
                suggestion_id,
                force=force,
                receive_count=receive_count,
            )
        except Exception:
            logger.exception(
                "Category suggestion enrichment will retry",
                extra={"suggestion_id": str(suggestion_id)},
            )
            if message_id:
                failures.append(message_id)
            continue
        if not acked and message_id:
            failures.append(message_id)
    return failure_response(failures)


def _receive_count(record: dict[str, Any]) -> int:
    raw = (record.get("attributes") or {}).get("ApproximateReceiveCount", "1")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1
