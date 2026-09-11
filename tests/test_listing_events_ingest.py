"""Tests for listing-event ingest and daily rollup."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.listing_events import lambda_handler
from app.db.models.listing_event import (
    NIL_LOCATION_ID,
    ListingEvent,
    ListingEventsDaily,
)
from app.db.repositories.listing_event import (
    ListingEventInput,
    ListingEventRepository,
    ListingEventsDailyRepository,
    parse_listing_event_input,
)
from app.services.listing_events_rollup import _resolve_day


def _event(body: dict) -> dict:
    return {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
        "requestContext": {"requestId": "test"},
    }


def test_parse_defaults_nil_location() -> None:
    parsed = parse_listing_event_input(
        {"event_type": "search", "source": "public_www"}
    )
    assert parsed.location_id == NIL_LOCATION_ID
    assert parsed.activity_id is None
    assert parsed.client_event_id


def test_parse_rejects_unknown_type() -> None:
    try:
        parse_listing_event_input(
            {"event_type": "click", "source": "public_www"}
        )
    except ValueError as exc:
        assert "event_type" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_insert_skips_duplicate_client_event_id(db_session) -> None:
    repo = ListingEventRepository(db_session)
    client_id = str(uuid4())
    first = ListingEventInput(
        event_type="listing_view",
        source="public_www",
        location_id=uuid4(),
        activity_id=uuid4(),
        client_event_id=client_id,
    )
    assert repo.insert_events([first]) == 1
    assert repo.insert_events([first]) == 0
    rows = db_session.execute(select(ListingEvent)).scalars().all()
    assert len(rows) == 1


def test_rollup_rebuilds_one_day(db_session) -> None:
    location_id = uuid4()
    day = date(2026, 9, 10)
    occurred = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    repo = ListingEventRepository(db_session)
    repo.insert_events(
        [
            ListingEventInput(
                event_type="search",
                source="public_www",
                location_id=NIL_LOCATION_ID,
                activity_id=None,
                client_event_id=str(uuid4()),
            ),
            ListingEventInput(
                event_type="listing_view",
                source="public_www",
                location_id=location_id,
                activity_id=uuid4(),
                client_event_id=str(uuid4()),
            ),
            ListingEventInput(
                event_type="listing_view",
                source="public_www",
                location_id=location_id,
                activity_id=uuid4(),
                client_event_id=str(uuid4()),
            ),
            ListingEventInput(
                event_type="cta_tap",
                source="public_www",
                location_id=location_id,
                activity_id=uuid4(),
                client_event_id=str(uuid4()),
            ),
            ListingEventInput(
                event_type="lead_relayed",
                source="public_www",
                location_id=location_id,
                activity_id=uuid4(),
                client_event_id=str(uuid4()),
            ),
        ],
        occurred_at=occurred,
    )

    written = ListingEventsDailyRepository(db_session).rollup_day(day)
    assert written == 2
    daily = {
        row.location_id: row
        for row in db_session.execute(select(ListingEventsDaily)).scalars()
    }
    nil_row = daily[NIL_LOCATION_ID]
    assert nil_row.searches == 1
    assert nil_row.listing_views == 0
    loc_row = daily[location_id]
    assert loc_row.listing_views == 2
    assert loc_row.cta_taps == 1
    assert loc_row.leads_relayed == 1
    assert loc_row.bookings_confirmed == 0

    written_again = ListingEventsDailyRepository(db_session).rollup_day(day)
    assert written_again == 2
    count = db_session.execute(select(ListingEventsDaily)).scalars().all()
    assert len(count) == 2


def test_handler_rejects_empty_events(monkeypatch, test_engine) -> None:
    monkeypatch.setattr(
        "app.api.listing_events.get_engine",
        lambda: test_engine,
    )
    response = lambda_handler(_event({"events": []}), None)
    assert response["statusCode"] == 400


def test_handler_inserts_and_returns_204(monkeypatch, test_engine) -> None:
    monkeypatch.setattr(
        "app.api.listing_events.get_engine",
        lambda: test_engine,
    )
    location_id = str(uuid4())
    response = lambda_handler(
        _event(
            {
                "events": [
                    {
                        "event_type": "listing_view",
                        "source": "public_www",
                        "location_id": location_id,
                        "activity_id": str(uuid4()),
                        "client_event_id": str(uuid4()),
                    }
                ]
            }
        ),
        None,
    )
    assert response["statusCode"] == 204
    with Session(test_engine) as session:
        rows = session.execute(select(ListingEvent)).scalars().all()
        assert any(row.location_id == UUID(location_id) for row in rows)


def test_resolve_day_uses_explicit_and_yesterday() -> None:
    assert _resolve_day({"day": "2026-09-01"}) == date(2026, 9, 1)
    resolved = _resolve_day({})
    assert resolved < datetime.now(timezone.utc).date()
