"""Repositories for listing funnel events and daily rollup."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models.listing_event import (
    LISTING_EVENT_SOURCES,
    LISTING_EVENT_TYPES,
    NIL_LOCATION_ID,
    ListingEvent,
    ListingEventsDaily,
)
from app.db.repositories.base import BaseRepository


@dataclass(frozen=True)
class ListingEventInput:
    """Validated ingest row before persistence."""

    event_type: str
    source: str
    location_id: UUID
    activity_id: UUID | None
    client_event_id: str


class ListingEventRepository(BaseRepository[ListingEvent]):
    """Insert and query raw listing events."""

    def __init__(self, session: Session):
        super().__init__(session, ListingEvent)

    def insert_events(
        self,
        events: Sequence[ListingEventInput],
        *,
        occurred_at: datetime | None = None,
    ) -> int:
        """Insert new events, skipping duplicate client_event_id values.

        Returns the number of rows inserted.
        """
        if not events:
            return 0

        now = occurred_at or datetime.now(timezone.utc)
        occurred_on = now.date()
        client_ids = [event.client_event_id for event in events]
        existing = {
            row[0]
            for row in self._session.execute(
                select(ListingEvent.client_event_id).where(
                    ListingEvent.client_event_id.in_(client_ids)
                )
            ).all()
        }

        inserted = 0
        seen_in_batch: set[str] = set()
        for event in events:
            if (
                event.client_event_id in existing
                or event.client_event_id in seen_in_batch
            ):
                continue
            self._session.add(
                ListingEvent(
                    id=uuid4(),
                    occurred_on=occurred_on,
                    occurred_at=now,
                    event_type=event.event_type,
                    location_id=event.location_id,
                    activity_id=event.activity_id,
                    source=event.source,
                    client_event_id=event.client_event_id,
                    created_at=now,
                )
            )
            seen_in_batch.add(event.client_event_id)
            inserted += 1

        if inserted:
            self._session.flush()
        return inserted


class ListingEventsDailyRepository(BaseRepository[ListingEventsDaily]):
    """Replace one UTC day's listing_events_daily rows from raw events."""

    def __init__(self, session: Session):
        super().__init__(session, ListingEventsDaily)

    def rollup_day(self, day: date) -> int:
        """Rebuild listing_events_daily for ``day`` from listing_events.

        ``bookings_confirmed`` stays 0 until a booking product exists.
        Returns the number of daily rows written.
        """
        self._session.execute(
            delete(ListingEventsDaily).where(ListingEventsDaily.day == day)
        )

        rows = self._session.execute(
            select(
                ListingEvent.location_id,
                ListingEvent.event_type,
                func.count().label("total"),
            )
            .where(ListingEvent.occurred_on == day)
            .group_by(ListingEvent.location_id, ListingEvent.event_type)
        ).all()

        totals: dict[UUID, dict[str, int]] = defaultdict(
            lambda: {
                "searches": 0,
                "listing_views": 0,
                "cta_taps": 0,
                "leads_relayed": 0,
            }
        )
        type_to_column = {
            "search": "searches",
            "listing_view": "listing_views",
            "cta_tap": "cta_taps",
            "lead_relayed": "leads_relayed",
        }
        for location_id, event_type, total in rows:
            column = type_to_column.get(event_type)
            if column is None:
                continue
            totals[location_id][column] = int(total)

        written = 0
        for location_id, counts in totals.items():
            self._session.add(
                ListingEventsDaily(
                    day=day,
                    location_id=location_id,
                    searches=counts["searches"],
                    listing_views=counts["listing_views"],
                    cta_taps=counts["cta_taps"],
                    leads_relayed=counts["leads_relayed"],
                    bookings_confirmed=0,
                )
            )
            written += 1

        if written:
            self._session.flush()
        return written


def parse_listing_event_input(raw: object) -> ListingEventInput:
    """Validate one ingest object. Raises ValueError on bad input."""
    if not isinstance(raw, dict):
        raise ValueError("Each event must be an object")

    event_type = str(raw.get("event_type") or "").strip()
    if event_type not in LISTING_EVENT_TYPES:
        raise ValueError("Invalid event_type")

    source = str(raw.get("source") or "").strip()
    if source not in LISTING_EVENT_SOURCES:
        raise ValueError("Invalid source")

    location_raw = raw.get("location_id")
    if location_raw in (None, ""):
        location_id = NIL_LOCATION_ID
    else:
        location_id = UUID(str(location_raw))

    activity_raw = raw.get("activity_id")
    activity_id = None
    if activity_raw not in (None, ""):
        activity_id = UUID(str(activity_raw))

    client_event_id = str(raw.get("client_event_id") or "").strip()
    if not client_event_id:
        client_event_id = str(uuid4())
    if len(client_event_id) > 128:
        raise ValueError("client_event_id is too long")

    return ListingEventInput(
        event_type=event_type,
        source=source,
        location_id=location_id,
        activity_id=activity_id,
        client_event_id=client_event_id,
    )
