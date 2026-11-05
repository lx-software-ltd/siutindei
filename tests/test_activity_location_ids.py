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
    GeographicArea,
    Location,
    Organization,
)
from app.db.repositories import ActivityRepository
from app.exceptions import ValidationError
from sqlalchemy import delete, select
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
    assert payload["location_ids"] == [str(other.id), str(sample_location.id)]


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
    assert _serialize_activity(sample_activity)["location_ids"] == [
        str(sample_location.id),
        str(other.id),
    ]

    _update_activity(repo, sample_activity, {"name": "Renamed Class"})
    repo.update(sample_activity)
    assert sample_activity.name == "Renamed Class"
    assert _serialize_activity(sample_activity)["location_ids"] == [
        str(sample_location.id),
        str(other.id),
    ]

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
        assert body["location_ids"] == [str(first_id), str(second_id)]

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
