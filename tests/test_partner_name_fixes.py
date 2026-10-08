"""Full-access partner keys list every org and pending name proposals."""

from __future__ import annotations

import json
from uuid import uuid4

from psycopg.types.range import Range
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.admin import _handle_partner_routes, lambda_handler
from app.db.models import Activity, ActivityCategory, NameFixProposal, Organization
from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_crud.get_engine", lambda: engine)
    monkeypatch.setattr("app.api.partner_name_fixes.get_engine", lambda: engine)


def _org(org_id, name: str, review_status: str) -> Organization:
    return Organization(
        id=org_id,
        name=name,
        manager_id=_MANAGER,
        review_status=review_status,
    )


def _proposal(entity_type: str, entity_id, current: str, proposed: str):
    return NameFixProposal(
        entity_type=entity_type,
        entity_id=entity_id,
        current_value=current,
        proposed_value=proposed,
        rules=["title_case"],
    )


def test_full_access_lists_pending_and_approved_orgs_with_fixes(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    pending_id = uuid4()
    approved_id = uuid4()
    category_id = uuid4()
    activity_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Partner Sport"))
        session.add(_org(pending_id, "HARBOUR CLUB", "pending_review"))
        session.add(_org(approved_id, "Clean Org Name", "approved"))
        session.add(
            Activity(
                id=activity_id,
                org_id=approved_id,
                category_id=category_id,
                name="SWIM CLASS",
                age_range=Range(5, 12, bounds="[]"),
            )
        )
        session.add(_proposal("organization", pending_id, "HARBOUR CLUB", "Harbour Club"))
        session.add(_proposal("activity", activity_id, "SWIM CLASS", "Swim Class"))
        session.commit()
    try:
        event = _partner_event("GET", "/v1/partner/organizations", "read", "")
        response = _handle_partner_routes(event, "GET", "organizations", None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        by_id = {item["id"]: item for item in body["items"]}
        assert str(pending_id) in by_id
        assert str(approved_id) in by_id
        assert by_id[str(pending_id)]["review_status"] == "pending_review"
        assert by_id[str(approved_id)]["review_status"] == "approved"
        pending_fixes = by_id[str(pending_id)]["pending_name_fixes"]
        assert pending_fixes[0]["entity_type"] == "organization"
        assert pending_fixes[0]["proposed_value"] == "Harbour Club"
        assert pending_fixes[0]["rules"] == ["title_case"]
        approved_fixes = by_id[str(approved_id)]["pending_name_fixes"]
        assert approved_fixes[0]["entity_type"] == "activity"
        assert approved_fixes[0]["proposed_value"] == "Swim Class"
    finally:
        _cleanup(
            test_engine,
            pending_id,
            approved_id,
            activity_id,
            category_id,
        )


def test_full_access_name_fixes_list_includes_record_and_rules(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    org_id = uuid4()
    with Session(test_engine) as session:
        session.add(_org(org_id, "YWCA HARBOUR", "approved"))
        session.add(_proposal("organization", org_id, "YWCA HARBOUR", "YWCA Harbour"))
        session.commit()
    try:
        event = _partner_event("GET", "/v1/partner/name-fixes", "read", "")
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        items = json.loads(response["body"])["items"]
        match = next(item for item in items if item["entity_id"] == str(org_id))
        assert match["entity_type"] == "organization"
        assert match["current_value"] == "YWCA HARBOUR"
        assert match["proposed_value"] == "YWCA Harbour"
        assert match["rules"] == ["title_case"]
        assert match["review_status"] == "approved"
    finally:
        _cleanup(test_engine, org_id)


def test_org_scoped_key_sees_only_its_name_fixes(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    owned_id = uuid4()
    other_id = uuid4()
    with Session(test_engine) as session:
        session.add(_org(owned_id, "Owned Club", "pending_review"))
        session.add(_org(other_id, "Other Club", "pending_review"))
        session.add(_proposal("organization", owned_id, "Owned Club", "Owned Club"))
        session.add(_proposal("organization", other_id, "Other Club", "Other Club"))
        session.commit()
    try:
        event = _partner_event(
            "GET", "/v1/partner/name-fixes", "read", str(owned_id)
        )
        response = _handle_partner_routes(event, "GET", "name-fixes", None)
        assert response["statusCode"] == 200
        items = json.loads(response["body"])["items"]
        assert {item["entity_id"] for item in items} == {str(owned_id)}
    finally:
        _cleanup(test_engine, owned_id, other_id)


def test_partner_cannot_write_name_fixes() -> None:
    event = _partner_event("POST", "/v1/partner/name-fixes", "crud", "")
    response = _handle_partner_routes(event, "POST", "name-fixes", None)
    assert response["statusCode"] == 404


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(
            delete(NameFixProposal).where(NameFixProposal.entity_id.in_(ids))
        )
        for model in (Activity, Organization, ActivityCategory):
            for row_id in ids:
                row = session.get(model, row_id)
                if row is not None:
                    session.delete(row)
        session.commit()
