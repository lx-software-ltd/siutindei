"""Public listing-event ingest handler."""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.repositories.listing_event import (
    ListingEventRepository,
    parse_listing_event_input,
)
from app.exceptions import ValidationError
from app.utils import json_response, validate_content_type
from app.utils.logging import configure_logging, get_logger, set_request_context

configure_logging()
logger = get_logger(__name__)

_MAX_EVENTS = 10


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Handle POST /v1/listing-events."""
    request_id = event.get("requestContext", {}).get("requestId", "")
    set_request_context(req_id=request_id)

    try:
        validate_content_type(event)
        inputs = _parse_events(event)
        engine = get_engine()
        with Session(engine) as session:
            repo = ListingEventRepository(session)
            inserted = repo.insert_events(inputs)
            session.commit()
        logger.info("listing_events_ingested", extra={"inserted": inserted})
        return json_response(204, {}, event=event)
    except ValidationError as exc:
        return json_response(
            exc.status_code,
            exc.to_dict(),
            event=event,
        )
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        logger.info("listing_events_rejected", extra={"reason": str(exc)})
        return json_response(
            400,
            {"error": "Invalid listing event payload"},
            event=event,
        )
    except Exception:
        logger.exception("listing_events_ingest_failed")
        return json_response(500, {"error": "Internal error"}, event=event)


def _parse_events(event: Mapping[str, Any]) -> list:
    """Parse and validate the ingest body."""
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if not raw:
        raise ValidationError("Request body is required")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be an object")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise ValidationError("events must be a non-empty array")
    if len(events) > _MAX_EVENTS:
        raise ValidationError(f"events must contain at most {_MAX_EVENTS}")

    parsed = []
    for item in events:
        try:
            parsed.append(parse_listing_event_input(item))
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc

    return parsed
