"""SQS worker that enriches one category suggestion per message."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.events.sqs_batch import failure_response
from app.services.category_suggestions.enrich import process_suggestion
from app.services.category_suggestions.scan import process_scan_batch
from app.services.category_suggestions.scan_discover_batch import (
    process_discover_batch,
)
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
        if not isinstance(payload, dict):
            logger.warning("Category suggestion message is missing a payload")
            continue
        receive_count = _receive_count(record)
        if payload.get("scan_run_id") and isinstance(
            payload.get("suggestion_ids"), list
        ):
            _handle_discover(payload, message_id, receive_count, failures)
            continue
        if payload.get("scan_run_id"):
            _handle_scan(payload, message_id, receive_count, failures)
            continue
        if not payload.get("suggestion_id"):
            logger.warning("Category suggestion message is missing suggestion_id")
            continue
        try:
            suggestion_id = UUID(str(payload["suggestion_id"]))
        except ValueError:
            logger.warning("Category suggestion id is not a UUID")
            continue
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


def _handle_discover(
    payload: dict[str, Any],
    message_id: str,
    receive_count: int,
    failures: list[str],
) -> None:
    raw_ids = payload.get("suggestion_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        logger.warning("Category discovery message is missing suggestion_ids")
        return
    try:
        scan_run_id = UUID(str(payload.get("scan_run_id")))
    except ValueError:
        logger.warning("Category discovery id is not a UUID")
        return
    try:
        acked = process_discover_batch(
            scan_run_id,
            [str(item) for item in raw_ids],
            message_id=message_id,
            receive_count=receive_count,
        )
    except Exception:
        logger.exception(
            "Category discovery batch will retry",
            extra={"scan_run_id": str(scan_run_id)},
        )
        if message_id:
            failures.append(message_id)
        return
    if not acked and message_id:
        failures.append(message_id)


def _handle_scan(
    payload: dict[str, Any],
    message_id: str,
    receive_count: int,
    failures: list[str],
) -> None:
    raw_ids = payload.get("activity_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        logger.warning("Category check message is missing activity_ids")
        return
    try:
        scan_run_id = UUID(str(payload.get("scan_run_id")))
    except ValueError:
        logger.warning("Category check id is not a UUID")
        return
    try:
        acked = process_scan_batch(
            scan_run_id,
            [str(item) for item in raw_ids],
            message_id=message_id,
            receive_count=receive_count,
        )
    except Exception:
        logger.exception(
            "Category check batch will retry",
            extra={"scan_run_id": str(scan_run_id)},
        )
        if message_id:
            failures.append(message_id)
        return
    logger.info(
        "Category check batch finished",
        extra={
            "scan_run_id": str(scan_run_id),
            "activity_count": len(raw_ids),
            "acked": acked,
            "receive_count": receive_count,
        },
    )
    if not acked and message_id:
        failures.append(message_id)


def _receive_count(record: dict[str, Any]) -> int:
    raw = (record.get("attributes") or {}).get("ApproximateReceiveCount", "1")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1
