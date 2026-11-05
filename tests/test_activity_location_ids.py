"""Activity create and update accept location_ids."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.admin import _handle_partner_routes
from app.api.admin_resource_activity import (
    _create_activity,
    _serialize_activity,
    _update_activity,
)
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.repositories import ActivityRepository
from app.exceptions import ValidationError
from app.services.org_review import load_snapshots
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _second_location(db_session, sample_organization, area_id):
    location = Location(
        org_id=sample_organization.id,
        area_id=area_id,
        address="456 Other Street",
        lat=Decimal("22.280000"),
        lng=Decimal("114.160000"),
    )
    db_session.add(location)
    db_session.flush()
    return location


def _create_body(sample_organization, sample_activity_category, **extra):
    return {
        "org_id": str(sample_organization.id),
        "category_id": str(sample_activity_category.id),
        "name": extra.pop("name", "Harbour Class"),
        "age_min": 2,
        "age_max": 6,
        **extra,
    }


def test_create_activity_links_venues(
    db_session, sample_organization, sample_activity_category, sample_location
) -> None:
    other = _second_location(db_session, sample_organization, sample_location.area_id)
    repo = ActivityRepository(db_session)
    entity = _create_activity(
        repo,
        _create_body(
            sample_organization,
            sample_activity_category,
            location_ids=[str(other.id), str(sample_location.id), str(other.id)],
        ),
    )
    repo.create(entity)
    payload = _serialize_activity(entity)
    assert payload["location_ids"] == sorted([str(other.id), str(sample_location.id)])


def test_update_replaces_omits_or_clears_venues(
    db_session,
    sample_activity,
    sample_location,
    sample_organization,
    sample_geographic_area,
) -> None:
    other = _second_location(db_session, sample_organization, sample_geographic_area.id)
    repo = ActivityRepository(db_session)
    _update_activity(
        repo,
        sample_activity,
        {"location_ids": [str(sample_location.id), str(other.id)]},
    )
    repo.update(sample_activity)
    linked = sorted([str(sample_location.id), str(other.id)])
    assert _serialize_activity(sample_activity)["location_ids"] == linked

    db_session.expire_all()
    _update_activity(repo, sample_activity, {"location_ids": linked})
    assert not any(isinstance(row, ActivityLocation) for row in db_session.new)
    assert not db_session.deleted

    _update_activity(repo, sample_activity, {"name": "Renamed Class"})
    repo.update(sample_activity)
    assert sample_activity.name == "Renamed Class"
    assert _serialize_activity(sample_activity)["location_ids"] == linked

    _update_activity(repo, sample_activity, {"location_ids": []})
    repo.update(sample_activity)
    assert _serialize_activity(sample_activity)["location_ids"] == []
    assert (
        db_session.scalars(
            select(ActivityLocation).where(
                ActivityLocation.activity_id == sample_activity.id
            )
        ).all()
        == []
    )


def test_location_ids_must_be_same_org_venues(
    db_session,
    sample_activity,
    sample_location,
    sample_geographic_area,
) -> None:
    foreign_org = Organization(
        name="Other Provider",
        manager_id=_MANAGER,
        review_status="pending_review",
    )
    db_session.add(foreign_org)
    db_session.flush()
    foreign = Location(
        org_id=foreign_org.id,
        area_id=sample_geographic_area.id,
        address="789 Foreign Street",
        lat=Decimal("22.270000"),
        lng=Decimal("114.150000"),
    )
    db_session.add(foreign)
    db_session.flush()
    repo = ActivityRepository(db_session)

    with pytest.raises(ValidationError, match="organization") as other_org:
        _update_activity(
            repo,
            sample_activity,
            {"location_ids": [str(foreign.id)]},
        )
    assert other_org.value.field == "location_ids"

    with pytest.raises(ValidationError, match="not found") as missing:
        _update_activity(
            repo,
            sample_activity,
            {"location_ids": [str(uuid4())]},
        )
    assert missing.value.field == "location_ids"

    with pytest.raises(ValidationError, match="list") as not_list:
        _update_activity(
            repo, sample_activity, {"location_ids": str(sample_location.id)}
        )
    assert not_list.value.field == "location_ids"

    with pytest.raises(ValidationError, match="too long") as too_long:
        _update_activity(
            repo,
            sample_activity,
            {"location_ids": [str(uuid4()) for _ in range(101)]},
        )
    assert too_long.value.field == "location_ids"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_crud.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.partner_category_reviews.get_engine", lambda: engine)


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(
            delete(ActivityLocation).where(ActivityLocation.activity_id.in_(ids))
        )
        for model in (
            Location,
            Activity,
            Organization,
            ActivityCategory,
            GeographicArea,
        ):
            for row_id in ids:
                row = session.get(model, row_id)
                if row is not None:
                    session.delete(row)
        session.commit()


def test_partner_create_and_update_return_location_ids(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    org_id = uuid4()
    other_org_id = uuid4()
    category_id = uuid4()
    area_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    foreign_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Partner Venue Class"))
        session.add(
            Organization(
                id=org_id,
                name="Campus Club",
                manager_id=_MANAGER,
                review_status="pending_review",
            )
        )
        session.add(
            Organization(
                id=other_org_id,
                name="Other Campus Club",
                manager_id=_MANAGER,
                review_status="pending_review",
            )
        )
        session.add(
            GeographicArea(id=area_id, name="灣仔", level="district", active=True)
        )
        session.add(
            Location(
                id=first_id,
                org_id=org_id,
                area_id=area_id,
                address="1 Campus Road",
                lat=Decimal("22.282667"),
                lng=Decimal("114.158167"),
            )
        )
        session.add(
            Location(
                id=second_id,
                org_id=org_id,
                area_id=area_id,
                address="2 Campus Road",
                lat=Decimal("22.283667"),
                lng=Decimal("114.159167"),
            )
        )
        session.add(
            Location(
                id=foreign_id,
                org_id=other_org_id,
                area_id=area_id,
                address="9 Other Road",
                lat=Decimal("22.270000"),
                lng=Decimal("114.150000"),
            )
        )
        session.commit()

    activity_id = None
    try:
        create = _partner_event("POST", "/v1/partner/activities", "crud", "")
        create["body"] = json.dumps(
            {
                "org_id": str(org_id),
                "category_id": str(category_id),
                "name": "Foundation Programme",
                "age_min": 2,
                "age_max": 3,
                "location_ids": [str(first_id), str(second_id)],
            }
        )
        created = _handle_partner_routes(create, "POST", "activities", None)
        assert created["statusCode"] == 201
        body = json.loads(created["body"])
        activity_id = body["id"]
        assert body["location_ids"] == sorted([str(first_id), str(second_id)])

        replace = _partner_event(
            "PUT", f"/v1/partner/activities/{activity_id}", "crud", ""
        )
        replace["body"] = json.dumps({"location_ids": [str(second_id)]})
        updated = _handle_partner_routes(replace, "PUT", "activities", activity_id)
        assert updated["statusCode"] == 200
        assert json.loads(updated["body"])["location_ids"] == [str(second_id)]

        keep = _partner_event(
            "PUT", f"/v1/partner/activities/{activity_id}", "crud", ""
        )
        keep["body"] = json.dumps({"name": "Foundation Programme Kept"})
        kept = _handle_partner_routes(keep, "PUT", "activities", activity_id)
        assert kept["statusCode"] == 200
        assert json.loads(kept["body"])["location_ids"] == [str(second_id)]

        foreign = _partner_event(
            "PUT", f"/v1/partner/activities/{activity_id}", "crud", ""
        )
        foreign["body"] = json.dumps({"location_ids": [str(foreign_id)]})
        rejected = _handle_partner_routes(foreign, "PUT", "activities", activity_id)
        assert rejected["statusCode"] == 400

        detail = _handle_partner_routes(
            _partner_event("GET", f"/v1/partner/activities/{activity_id}", "crud", ""),
            "GET",
            "activities",
            activity_id,
        )
        assert detail["statusCode"] == 200
        assert json.loads(detail["body"])["location_ids"] == [str(second_id)]
    finally:
        _cleanup(
            test_engine,
            activity_id,
            first_id,
            second_id,
            foreign_id,
            org_id,
            other_org_id,
            category_id,
            area_id,
        )


def test_removing_a_venue_with_pricing_or_a_schedule_is_rejected(
    db_session,
    sample_activity,
    sample_location,
    sample_organization,
    sample_geographic_area,
    sample_activity_category,
) -> None:
    other = _second_location(db_session, sample_organization, sample_geographic_area.id)
    repo = ActivityRepository(db_session)
    _update_activity(repo, sample_activity, {"location_ids": [str(sample_location.id)]})
    db_session.add(
        ActivityPricing(
            activity_id=sample_activity.id,
            location_id=sample_location.id,
            pricing_type=PricingType.PER_CLASS,
            amount=Decimal("10.00"),
        )
    )
    db_session.flush()
    with pytest.raises(ValidationError, match="pricing or schedules") as priced:
        _update_activity(repo, sample_activity, {"location_ids": []})
    assert priced.value.field == "location_ids"
    assert _serialize_activity(sample_activity)["location_ids"] == [
        str(sample_location.id)
    ]

    scheduled = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Scheduled Class",
        age_range=sample_activity.age_range,
    )
    db_session.add(scheduled)
    db_session.flush()
    _update_activity(repo, scheduled, {"location_ids": [str(other.id)]})
    db_session.add(
        ActivitySchedule(
            activity_id=scheduled.id,
            location_id=other.id,
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
        )
    )
    db_session.flush()
    with pytest.raises(ValidationError, match="pricing or schedules"):
        _update_activity(repo, scheduled, {"location_ids": [str(sample_location.id)]})
    assert _serialize_activity(scheduled)["location_ids"] == [str(other.id)]


def test_loaded_activity_page_does_not_query_per_row(
    db_session,
    sample_organization,
    sample_activity_category,
    sample_geographic_area,
    sample_location,
) -> None:
    repo = ActivityRepository(db_session)
    for index in range(3):
        created = _create_activity(
            repo,
            _create_body(
                sample_organization,
                sample_activity_category,
                name=f"Paged Class {index}",
                location_ids=[str(sample_location.id)],
            ),
        )
        repo.create(created)
    db_session.expire_all()
    rows = list(repo.get_all(limit=50))
    snapshots = load_snapshots(db_session, [sample_organization])
    assert len(rows) >= 3
    assert len(snapshots[0].activities) >= 3
    queries: list[str] = []

    def _count(*args) -> None:
        queries.append(str(args[2]))

    event.listen(db_session.get_bind(), "before_cursor_execute", _count)
    try:
        for row in rows:
            _serialize_activity(row)
        for activity in snapshots[0].activities:
            _serialize_activity(activity)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", _count)
    assert queries == []


def test_manager_and_org_scoped_key_set_own_venues(monkeypatch, test_engine) -> None:
    from app.api.admin_routes import handle_manager_routes

    _patch_engines(monkeypatch, test_engine)
    monkeypatch.setattr("app.api.admin_auth.get_engine", lambda: test_engine)
    manager_id = str(uuid4())
    org_id = uuid4()
    other_org_id = uuid4()
    category_id = uuid4()
    area_id = uuid4()
    location_id = uuid4()
    activity_id = uuid4()
    other_activity_id = uuid4()
    with Session(test_engine) as session:
        session.add(
            ActivityCategory(id=category_id, name=f"Scoped Class {category_id}")
        )
        session.add(
            Organization(
                id=org_id,
                name="Managed Campus",
                manager_id=manager_id,
                review_status="pending_review",
            )
        )
        session.add(
            Organization(
                id=other_org_id,
                name="Other Managed Campus",
                manager_id=str(uuid4()),
                review_status="pending_review",
            )
        )
        session.add(
            GeographicArea(
                id=area_id,
                name=f"Managed Area {area_id}",
                level="district",
                active=True,
            )
        )
        session.add(
            Location(
                id=location_id,
                org_id=org_id,
                area_id=area_id,
                address="1 Managed Road",
                lat=Decimal("22.282667"),
                lng=Decimal("114.158167"),
            )
        )
        for row_id, owner_id, name in (
            (activity_id, org_id, "Managed Programme"),
            (other_activity_id, other_org_id, "Other Programme"),
        ):
            session.add(
                Activity(
                    id=row_id,
                    org_id=owner_id,
                    category_id=category_id,
                    name=name,
                    age_range=_age_range(),
                )
            )
        session.commit()

    def _manager_put(target_id) -> dict:
        event = {
            "httpMethod": "PUT",
            "path": f"/v1/manager/activities/{target_id}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"location_ids": [str(location_id)]}),
            "requestContext": {
                "requestId": "req-manager",
                "authorizer": {"groups": "manager", "userSub": manager_id},
            },
        }
        return handle_manager_routes(event, "PUT", "activities", str(target_id))

    try:
        updated = _manager_put(activity_id)
        assert updated["statusCode"] == 200
        assert json.loads(updated["body"])["location_ids"] == [str(location_id)]
        forbidden = _manager_put(other_activity_id)
        assert forbidden["statusCode"] == 403

        scoped = _partner_event(
            "PUT",
            f"/v1/partner/activities/{activity_id}",
            "crud",
            str(org_id),
        )
        scoped["body"] = json.dumps({"location_ids": [str(location_id)]})
        scoped_response = _handle_partner_routes(
            scoped, "PUT", "activities", str(activity_id)
        )
        assert scoped_response["statusCode"] == 200
        assert json.loads(scoped_response["body"])["location_ids"] == [str(location_id)]
        outsider = _partner_event(
            "PUT",
            f"/v1/partner/activities/{other_activity_id}",
            "crud",
            str(org_id),
        )
        outsider["body"] = json.dumps({"location_ids": [str(location_id)]})
        assert (
            _handle_partner_routes(
                outsider, "PUT", "activities", str(other_activity_id)
            )["statusCode"]
            == 403
        )
    finally:
        _cleanup(
            test_engine,
            activity_id,
            other_activity_id,
            location_id,
            org_id,
            other_org_id,
            category_id,
            area_id,
        )


def _age_range():
    from psycopg.types.range import Range

    return Range(2, 6, bounds="[]")
