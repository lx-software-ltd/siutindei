"""Partner keys can read venue proposals; full-access crud keys can decide them."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityLocation,
    GeographicArea,
    Location,
    LocationFixProposal,
    Organization,
)
from psycopg.types.range import Range
from sqlalchemy import delete
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_crud.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.partner_name_fixes.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.partner_category_reviews.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.partner_location_fixes.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.admin_location_fixes.get_engine", lambda: engine)


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(
            delete(LocationFixProposal).where(LocationFixProposal.org_id.in_(ids))
        )
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


def test_full_access_orgs_and_activities_include_venue_proposals(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    org_id = uuid4()
    category_id = uuid4()
    activity_id = uuid4()
    area_id = uuid4()
    location_id = uuid4()
    proposal_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Partner Sport"))
        session.add(
            Organization(
                id=org_id,
                name="Harbour Club",
                manager_id=_MANAGER,
                review_status="pending_review",
            )
        )
        session.add(
            GeographicArea(id=area_id, name="灣仔", level="district", active=True)
        )
        session.add(
            Location(
                id=location_id,
                org_id=org_id,
                area_id=area_id,
                address="1 Harbour Road",
                lat=Decimal("22.280000"),
                lng=Decimal("114.150000"),
            )
        )
        session.add(
            Activity(
                id=activity_id,
                org_id=org_id,
                category_id=category_id,
                name="Swim Class",
                age_range=Range(5, 12, bounds="[]"),
            )
        )
        session.add(ActivityLocation(activity_id=activity_id, location_id=location_id))
        session.flush()
        session.add(
            LocationFixProposal(
                id=proposal_id,
                entity_type="activity",
                entity_id=activity_id,
                org_id=org_id,
                kind="link_existing",
                source="rule:name_area",
                target_location_id=location_id,
                status="pending",
            )
        )
        session.commit()
    try:
        org_event = _partner_event("GET", "/v1/partner/organizations", "read", "")
        org_response = _handle_partner_routes(org_event, "GET", "organizations", None)
        assert org_response["statusCode"] == 200
        orgs = {item["id"]: item for item in json.loads(org_response["body"])["items"]}
        fixes = orgs[str(org_id)]["pending_location_fixes"]
        assert fixes[0]["id"] == str(proposal_id)
        assert fixes[0]["kind"] == "link_existing"
        assert fixes[0]["source"] == "rule:name_area"

        activity_event = _partner_event("GET", "/v1/partner/activities", "read", "")
        activity_response = _handle_partner_routes(
            activity_event, "GET", "activities", None
        )
        assert activity_response["statusCode"] == 200
        activities = {
            item["id"]: item for item in json.loads(activity_response["body"])["items"]
        }
        activity = activities[str(activity_id)]
        assert activity["location_ids"] == [str(location_id)]
        assert activity["pending_location_fix"]["id"] == str(proposal_id)
    finally:
        _cleanup(
            test_engine,
            org_id,
            category_id,
            activity_id,
            area_id,
            location_id,
            proposal_id,
        )


def test_full_access_crud_can_dismiss_and_scoped_key_cannot(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    org_id = uuid4()
    proposal_id = uuid4()
    with Session(test_engine) as session:
        session.add(
            Organization(
                id=org_id,
                name="Harbour Club",
                manager_id=_MANAGER,
                review_status="approved",
            )
        )
        session.flush()
        session.add(
            LocationFixProposal(
                id=proposal_id,
                entity_type="organization",
                entity_id=org_id,
                org_id=org_id,
                kind="unresolved",
                source="model",
                status="pending",
            )
        )
        session.commit()
    try:
        denied = _partner_event(
            "POST",
            f"/v1/partner/location-fixes/{proposal_id}",
            "crud",
            str(org_id),
        )
        denied["body"] = json.dumps({"action": "dismiss"})
        denied_response = _handle_partner_routes(
            denied, "POST", "location-fixes", str(proposal_id)
        )
        assert denied_response["statusCode"] == 403

        allowed = _partner_event(
            "POST",
            f"/v1/partner/location-fixes/{proposal_id}",
            "crud",
            "",
        )
        allowed["body"] = json.dumps({"action": "dismiss"})
        allowed_response = _handle_partner_routes(
            allowed, "POST", "location-fixes", str(proposal_id)
        )
        assert allowed_response["statusCode"] == 200
        assert json.loads(allowed_response["body"])["status"] == "dismissed"
    finally:
        _cleanup(test_engine, org_id, proposal_id)
