"""Nightly rollup of listing_events into listing_events_daily."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.repositories.listing_event import ListingEventsDailyRepository
from app.utils.logging import configure_logging, get_logger, set_request_context

configure_logging()
logger = get_logger(__name__)


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Roll up one UTC day of listing events.

    EventBridge invokes this without a day field (uses yesterday UTC).
    A manual invoke may pass ``{"day": "YYYY-MM-DD"}`` to backfill.
    """
    request_id = ""
    if isinstance(event, Mapping):
        request_id = str(event.get("requestContext", {}).get("requestId", ""))
    set_request_context(req_id=request_id)

    day = _resolve_day(event)
    engine = get_engine()
    with Session(engine) as session:
        written = ListingEventsDailyRepository(session).rollup_day(day)
        session.commit()

    logger.info(
        "listing_events_rolled_up",
        extra={"day": day.isoformat(), "rows": written},
    )
    return {"day": day.isoformat(), "rows": written}


def _resolve_day(event: Mapping[str, Any] | None) -> date:
    """Return the UTC day to roll up."""
    raw = None
    if isinstance(event, Mapping):
        raw = event.get("day")
    if raw:
        return date.fromisoformat(str(raw))
    return datetime.now(timezone.utc).date() - timedelta(days=1)
