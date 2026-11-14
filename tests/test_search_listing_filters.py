"""Public search: kind, age range, and verified filters, and the fields they read."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api import search as search_api
from app.api.schemas import dump_search_response
from app.api.search import fetch_search_response
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"
_PREFIX = "c1111111-1111-1111-1111-11111111"
_SPORTS = f"{_PREFIX}1302"
_PLACES = f"{_PREFIX}1401"
_PLAYGROUND = f"{_PREFIX}1411"
_NURSERIES = f"{_PREFIX}1402"
_KINDERGARTEN = f"{_PREFIX}1422"
_CHECKED_AT = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)


def _seed(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {token}", level="neighbourhood", active=True)
        checked = Organization(
            name=f"Checked Club {token}",
            manager_id=_MANAGER,
            description="Checked",
            review_status="approved",
            parent_verified=True,
            parent_verified_at=_CHECKED_AT,
        )
        unchecked = Organization(
            name=f"Unchecked Club {token}",
            manager_id=_MANAGER,
            description="Unchecked",
            review_status="approved",
        )
        session.add_all([area, checked, unchecked])
        session.flush()

        def listing(
            owner: Organization,
            label: str,
            *,
            kind: str,
            category: str,
            ages: tuple[int, int],
            facts: dict[str, bool] | None = None,
            priced: bool = True,
            day: int = 1,
        ) -> str:
            venue = Location(
                org_id=owner.id,
                area_id=area.id,
                address=f"{label} Example Road {token}",
                lat=Decimal("22.218000"),
                lng=Decimal("114.213000"),
            )
            act = Activity(
                org_id=owner.id,
                category_id=UUID(category),
                name=f"{label} {token}",
                description=label,
                age_range=Range(ages[0], ages[1], bounds="[]"),
                kind=kind,
                facts=facts or {},
            )
            session.add_all([venue, act])
            session.flush()
            if priced:
                session.add(
                    ActivityPricing(
                        activity_id=act.id,
                        location_id=venue.id,
                        pricing_type=PricingType.PER_CLASS,
                        amount=Decimal(150),
                    )
                )
            schedule = ActivitySchedule(
                activity_id=act.id,
                location_id=venue.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
            session.add(schedule)
            session.flush()
            session.add(
                ActivityScheduleEntry(
                    schedule_id=schedule.id,
                    day_of_week_utc=day,
                    start_minutes_utc=120,
                    end_minutes_utc=180,
                )
            )
            return str(act.id)

        ids = {
            "class": listing(
                checked, "Football", kind="class", category=_SPORTS, ages=(6, 8)
            ),
            "camp": listing(
                unchecked,
                "Sailing camp",
                kind="camp",
                category=_SPORTS,
                ages=(12, 15),
                facts={"lunch_included": True},
                day=2,
            ),
            "place": listing(
                unchecked,
                "Harbour playground",
                kind="place",
                category=_PLAYGROUND,
                ages=(0, 18),
                facts={"toilets": True, "shade": False},
                priced=False,
            ),
            "preschool": listing(
                checked,
                "Kindergarten",
                kind="preschool",
                category=_KINDERGARTEN,
                ages=(3, 5),
                day=3,
            ),
        }
        session.commit()
        return {
            **ids,
            "area_id": str(area.id),
            "checked_id": str(checked.id),
            "unchecked_id": str(unchecked.id),
        }


def _delete(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        for key in ("checked_id", "unchecked_id"):
            row = session.get(Organization, seeded[key])
            if row is not None:
                session.delete(row)
        area = session.get(GeographicArea, seeded["area_id"])
        if area is not None:
            session.delete(area)
        session.commit()


@pytest.fixture
def seeded(monkeypatch, test_engine):
    monkeypatch.setattr("app.api.search.get_engine", lambda: test_engine)
    data = _seed(test_engine)
    yield data
    _delete(test_engine, data)


def _search(seeded: dict[str, str], **kwargs):
    kwargs.setdefault("limit", 20)
    return fetch_search_response(
        ActivitySearchFilters(area_id=UUID(seeded["area_id"]), **kwargs)
    )


def _ids(seeded: dict[str, str], **kwargs) -> set[str]:
    names = {value: key for key, value in seeded.items()}
    return {names[item.activity.id] for item in _search(seeded, **kwargs).items}


def test_no_new_parameter_keeps_every_kind(seeded) -> None:
    assert _ids(seeded) == {"class", "camp", "preschool"}
    assert _ids(seeded, include_incomplete=True) == {
        "class",
        "camp",
        "place",
        "preschool",
    }


def test_kind_filter_applies_to_both_phases(seeded) -> None:
    assert _ids(seeded, kinds=("class", "camp")) == {"class", "camp"}
    assert _ids(seeded, kinds=("place",)) == set()
    assert _ids(seeded, kinds=("place",), include_incomplete=True) == {"place"}
    counted = _search(
        seeded, kinds=("class", "place"), include_incomplete=True, include_total=True
    )
    assert counted.total == 2


def test_age_range_overlaps_the_activity_ages(seeded) -> None:
    assert _ids(seeded, age_min=6, age_max=11) == {"class"}
    assert _ids(seeded, age_min=6, age_max=11, include_incomplete=True) == {
        "class",
        "place",
    }
    assert _ids(seeded, age_min=12, include_incomplete=True) == {"camp", "place"}
    assert _ids(seeded, age_max=4, include_incomplete=True) == {"place", "preschool"}
    assert _ids(seeded, age_min=8, age_max=8) == {"class"}


def test_topic_and_fixed_root_search_include_incomplete_rows(seeded) -> None:
    topic = _search(
        seeded,
        category_ids=[UUID(_SPORTS)],
        include_incomplete=True,
        include_total=True,
    )
    assert {item.activity.id for item in topic.items} == {
        seeded["class"],
        seeded["camp"],
    }
    assert topic.total == 2
    assert _ids(seeded, category_ids=[UUID(_PLACES)], include_incomplete=True) == {
        "place"
    }


def test_verified_limits_to_parent_verified_organizations(seeded) -> None:
    assert _ids(seeded, verified_only=True, include_incomplete=True) == {
        "class",
        "preschool",
    }


def test_full_view_returns_kind_facts_category_and_checked_date(seeded) -> None:
    response = _search(seeded, include_incomplete=True)
    by_id = {item.activity.id: item for item in response.items}

    football = by_id[seeded["class"]]
    assert football.activity.kind == "class"
    assert football.activity.facts == {}
    assert football.activity.category_root_id == _SPORTS
    assert football.activity.category_name == "Sports"
    assert football.activity.category_name_translations["zh-HK"] == "運動"
    assert football.organization.parent_verified_at == _CHECKED_AT

    playground = by_id[seeded["place"]]
    assert playground.activity.kind == "place"
    assert playground.activity.facts == {"shade": False, "toilets": True}
    assert playground.activity.category_id == _PLAYGROUND
    assert playground.activity.category_root_id == _PLACES
    assert playground.activity.category_name == "Playground and park"
    assert playground.organization.parent_verified_at is None

    nursery = by_id[seeded["preschool"]]
    assert nursery.activity.category_root_id == _NURSERIES

    camp = by_id[seeded["camp"]]
    assert camp.activity.facts == {"lunch_included": True}


def test_card_view_drops_facts_and_keeps_the_checked_date(seeded) -> None:
    payload = dump_search_response(
        _search(seeded, view="card", include_incomplete=True), "card"
    )
    by_id = {row["activity"]["id"]: row for row in payload["items"]}

    football = by_id[seeded["class"]]
    assert "facts" not in football["activity"]
    assert "kind" not in football["activity"]
    assert by_id[seeded["camp"]]["activity"]["kind"] == "camp"
    assert by_id[seeded["place"]]["activity"]["kind"] == "place"
    assert football["activity"]["category_root_id"] == _SPORTS
    assert football["activity"]["category_name"] == "Sports"
    assert "en" not in football["activity"]["category_name_translations"]
    checked_at = str(football["organization"]["parent_verified_at"])
    assert checked_at.startswith("2026-11-02")

    camp = by_id[seeded["camp"]]
    assert "parent_verified_at" not in camp["organization"]


def test_category_table_loads_once_per_request(seeded, monkeypatch) -> None:
    calls: list[int] = []
    original = search_api.load_search_categories

    def counting(session):
        calls.append(1)
        return original(session)

    monkeypatch.setattr(search_api, "load_search_categories", counting)
    response = _search(seeded, include_incomplete=True)

    assert len(response.items) == 4
    assert len(calls) == 1
