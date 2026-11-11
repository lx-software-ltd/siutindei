"""Public search: contact, feedback, venue names, new filters, sort, and total."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api.schemas import dump_search_response
from app.api.search import fetch_search_response, parse_filters
from app.api.search_page import parse_cursor
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    FeedbackLabel,
    GeographicArea,
    Location,
    Organization,
    OrganizationFeedback,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters
from app.db.search_conditions import hong_kong_day
from app.exceptions import CursorError, ValidationError
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.search.get_engine", lambda: engine)


def _seed(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {token}", level="neighbourhood", active=True)
        category = ActivityCategory(name=f"Category {token}", display_order=0)
        org = Organization(
            name=f"Harbour Club {token}",
            manager_id=_MANAGER,
            description="Club",
            review_status="approved",
            parent_verified=True,
            website="https://example.com/club",
            email="hello@example.com",
            phone_country_code="HK",
            phone_number="21234567",
            instagram="@exampleclub",
        )
        other = Organization(
            name=f"Kowloon Club {token}",
            manager_id=_MANAGER,
            description="Other",
            review_status="approved",
        )
        label = FeedbackLabel(
            name=f"Friendly {token}", name_translations={"zh": "友善"}
        )
        session.add_all([area, category, org, other, label])
        session.flush()

        def venue(owner: Organization, name: str | None) -> Location:
            row = Location(
                org_id=owner.id,
                area_id=area.id,
                name=name,
                address=f"1 Example Road {token}",
                lat=Decimal("22.280000"),
                lng=Decimal("114.150000"),
            )
            session.add(row)
            session.flush()
            return row

        def listing(
            owner: Organization,
            loc: Location,
            label_text: str,
            *,
            pricing_type: PricingType,
            amount: str,
            sessions: int | None = None,
            free_trial: bool = False,
            day: int = 1,
            start: int = 120,
        ) -> Activity:
            act = Activity(
                org_id=owner.id,
                category_id=category.id,
                name=f"{label_text} {token}",
                description=label_text,
                age_range=Range(3, 8, bounds="[]"),
            )
            session.add(act)
            session.flush()
            session.add(
                ActivityPricing(
                    activity_id=act.id,
                    location_id=loc.id,
                    pricing_type=pricing_type,
                    amount=Decimal(amount),
                    sessions_count=sessions,
                    free_trial_class_offered=free_trial,
                )
            )
            schedule = ActivitySchedule(
                activity_id=act.id,
                location_id=loc.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
            session.add(schedule)
            session.flush()
            session.add(
                ActivityScheduleEntry(
                    schedule_id=schedule.id,
                    day_of_week_utc=day,
                    start_minutes_utc=start,
                    end_minutes_utc=(start + 60) % 1440,
                )
            )
            return act

        studio = venue(org, "Main studio")
        term = listing(
            org,
            studio,
            "Term class",
            pricing_type=PricingType.PER_SESSIONS,
            amount="2400",
            sessions=8,
            free_trial=True,
        )
        # Friday 23:00 UTC is Saturday 07:00 in Hong Kong.
        early = listing(
            org,
            studio,
            "Early class",
            pricing_type=PricingType.PER_CLASS,
            amount="150",
            day=5,
            start=1380,
        )
        monthly = listing(
            org,
            venue(org, None),
            "Monthly class",
            pricing_type=PricingType.PER_MONTH,
            amount="900",
        )
        other_class = listing(
            other,
            venue(other, None),
            "Other class",
            pricing_type=PricingType.FREE,
            amount="0",
        )
        session.flush()
        session.add_all(
            [
                OrganizationFeedback(
                    organization_id=org.id,
                    submitter_id="sub-1",
                    submitter_email="parent@example.com",
                    stars=5,
                    label_ids=[label.id],
                    description="Lovely teachers.",
                ),
                OrganizationFeedback(
                    organization_id=org.id,
                    stars=4,
                    description="  ",
                ),
            ]
        )
        session.commit()
        return {
            "area_id": str(area.id),
            "category_id": str(category.id),
            "org_id": str(org.id),
            "other_id": str(other.id),
            "label_id": str(label.id),
            "term_id": str(term.id),
            "early_id": str(early.id),
            "monthly_id": str(monthly.id),
            "other_class_id": str(other_class.id),
        }


def _delete(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        for key in ("org_id", "other_id"):
            row = session.get(Organization, seeded[key])
            if row is not None:
                session.delete(row)
        for model, key in (
            (GeographicArea, "area_id"),
            (ActivityCategory, "category_id"),
            (FeedbackLabel, "label_id"),
        ):
            row = session.get(model, seeded[key])
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def seeded(monkeypatch, test_engine):
    _patch_engine(monkeypatch, test_engine)
    data = _seed(test_engine)
    yield data
    _delete(test_engine, data)


def _scope(seeded: dict[str, str], **kwargs) -> ActivitySearchFilters:
    kwargs.setdefault("limit", 20)
    return ActivitySearchFilters(area_id=UUID(seeded["area_id"]), **kwargs)


def _ids(response) -> list[str]:
    return [item.activity.id for item in response.items]


def test_detail_lookup_returns_contact_feedback_and_venue_name(seeded) -> None:
    response = fetch_search_response(
        ActivitySearchFilters(activity_id=UUID(seeded["term_id"]), limit=50)
    )
    item = response.items[0]
    org = item.organization
    assert org.parent_verified is True
    assert org.updated_at is not None
    assert org.contact is not None
    assert org.contact.website == "https://example.com/club"
    assert org.contact.phone_number == "21234567"
    assert org.contact.instagram == "@exampleclub"
    assert org.rating is not None
    assert org.rating.count == 2
    assert org.rating.average_stars == Decimal("4.5")
    assert sorted(review.stars for review in org.reviews) == [4, 5]
    friendly = next(review for review in org.reviews if review.stars == 5)
    assert friendly.description == "Lovely teachers."
    assert friendly.labels[0].name_translations["zh"] == "友善"
    blank = next(review for review in org.reviews if review.stars == 4)
    assert blank.description is None
    assert item.location.name == "Main studio"

    payload = dump_search_response(response, "full")
    encoded = json.dumps(payload, default=str)
    assert "parent@example.com" not in encoded
    assert "sub-1" not in encoded


def test_list_search_carries_rating_but_not_reviews(seeded) -> None:
    response = fetch_search_response(_scope(seeded))
    by_id = {item.activity.id: item for item in response.items}
    assert by_id[seeded["term_id"]].organization.rating is not None
    assert by_id[seeded["term_id"]].organization.reviews == []
    assert by_id[seeded["other_class_id"]].organization.rating is None

    card = dump_search_response(
        fetch_search_response(_scope(seeded, view="card")), "card"
    )
    for row in card["items"]:
        assert "contact" not in row["organization"]
        assert "reviews" not in row["organization"]
        assert "updated_at" not in row["organization"]
    verified = [
        row for row in card["items"] if row["activity"]["id"] == seeded["term_id"]
    ]
    assert verified[0]["organization"]["parent_verified"] is True
    unverified = [
        row
        for row in card["items"]
        if row["activity"]["id"] == seeded["other_class_id"]
    ]
    assert "parent_verified" not in unverified[0]["organization"]


def test_organization_free_trial_and_class_price_filters(seeded) -> None:
    by_org = fetch_search_response(_scope(seeded, org_ids=(UUID(seeded["org_id"]),)))
    assert set(_ids(by_org)) == {
        seeded["term_id"],
        seeded["early_id"],
        seeded["monthly_id"],
    }

    trial = fetch_search_response(_scope(seeded, free_trial=True))
    assert _ids(trial) == [seeded["term_id"]]

    cheap = fetch_search_response(_scope(seeded, class_price_max=Decimal(200)))
    assert set(_ids(cheap)) == {seeded["early_id"], seeded["other_class_id"]}

    up_to_term = fetch_search_response(_scope(seeded, class_price_max=Decimal(300)))
    assert seeded["term_id"] in _ids(up_to_term)
    assert seeded["monthly_id"] not in _ids(up_to_term)


def test_hong_kong_day_filter_reads_local_day(seeded) -> None:
    assert hong_kong_day(5, 1380) == 6
    saturday = fetch_search_response(_scope(seeded, days_of_week_hkt=(6,)))
    assert _ids(saturday) == [seeded["early_id"]]
    monday = fetch_search_response(_scope(seeded, days_of_week_hkt=(1,)))
    assert seeded["early_id"] not in _ids(monday)
    assert seeded["term_id"] in _ids(monday)
    weekend = fetch_search_response(_scope(seeded, days_of_week_hkt=(0, 6)))
    assert _ids(weekend) == [seeded["early_id"]]


def test_price_sort_pages_with_a_cursor(seeded) -> None:
    first = fetch_search_response(_scope(seeded, sort="price", limit=2))
    assert _ids(first) == [seeded["other_class_id"], seeded["early_id"]]
    assert first.next_cursor is not None
    cursor = parse_cursor(first.next_cursor)
    assert cursor is not None and cursor.sort == "price"
    second = fetch_search_response(_scope(seeded, sort="price", limit=2, cursor=cursor))
    assert _ids(second) == [seeded["term_id"], seeded["monthly_id"]]
    assert second.next_cursor is None


def test_total_counts_activities_on_the_first_page_only(seeded) -> None:
    first = fetch_search_response(_scope(seeded, include_total=True, limit=1))
    assert first.total == 4
    assert first.next_cursor is not None
    later = fetch_search_response(
        _scope(
            seeded,
            include_total=True,
            limit=1,
            cursor=parse_cursor(first.next_cursor),
        )
    )
    assert later.total is None
    assert fetch_search_response(_scope(seeded)).total is None


def _event(params: dict[str, list[str]]) -> dict:
    return {
        "queryStringParameters": {key: values[-1] for key, values in params.items()},
        "multiValueQueryStringParameters": params,
    }


def test_parse_filters_reads_new_parameters() -> None:
    org_id = str(uuid4())
    filters = parse_filters(
        _event(
            {
                "organization_id": [org_id],
                "day_of_week_hkt": ["6", "0", "6"],
                "free_trial": ["true"],
                "class_price_max": ["200"],
                "sort": ["price"],
                "include_total": ["1"],
            }
        )
    )
    assert filters.org_ids == (UUID(org_id),)
    assert filters.days_of_week_hkt == (0, 6)
    assert filters.free_trial is True
    assert filters.class_price_max == Decimal(200)
    assert filters.sort == "price"
    assert filters.include_total is True


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"day_of_week_hkt": ["7"]}, "day_of_week_hkt"),
        ({"free_trial": ["maybe"]}, "free_trial"),
        ({"class_price_max": ["-1"]}, "class_price_max"),
        ({"sort": ["distance"]}, "sort"),
        ({"include_total": ["perhaps"]}, "include_total"),
    ],
)
def test_parse_filters_rejects_bad_values(params, field) -> None:
    with pytest.raises(ValidationError) as caught:
        parse_filters(_event(params))
    assert caught.value.field == field


def test_cursor_from_another_sort_is_rejected() -> None:
    from app.api.search_page import encode_complete_cursor

    time_cursor = encode_complete_cursor(1, 120, uuid4())
    with pytest.raises(CursorError):
        parse_filters(_event({"sort": ["price"], "cursor": [time_cursor]}))
