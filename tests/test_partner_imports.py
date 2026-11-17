"""A full-access crud partner key can import a catalog file."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from app.api.partner_routes import handle_partner_routes
from app.db.models import ActivityCategory, GeographicArea, Location, Organization
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-0000000000aa"
_OTHER = "00000000-0000-0000-0000-0000000000bb"
_PLACEHOLDER = "REPLACE_WITH_YOUR_MANAGER_ID"


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.partner_imports.get_engine", lambda: engine)


def _post(
    body: dict,
    *,
    query: str = "",
    scope: str = "crud",
    org_scope: str = "",
) -> dict:
    path = "/v1/partner/imports" + (("?" + query) if query else "")
    event = _partner_event("POST", path, scope, org_scope)
    event["body"] = json.dumps(body)
    if query:
        event["queryStringParameters"] = dict(
            part.split("=", 1) for part in query.split("&")
        )
    return handle_partner_routes(event, "POST", "imports", None)


def _payload(name: str, *, description: str | None = "Visited restaurant") -> dict:
    return {
        "default_manager_id": _PLACEHOLDER,
        "organizations": [
            {
                "name": name,
                "description": description,
                "website": "https://example.test/restaurant",
                "locations": [
                    {
                        "name": "1 Test Street",
                        "address": "1 Test Street",
                        "area_name": "Partner Import Area",
                        "lat": 22.2,
                        "lng": 114.2,
                    }
                ],
                "activities": [
                    {
                        "name": name,
                        "kind": "eat",
                        "description": "Lunch with high chairs",
                        "category_id": None,
                    }
                ],
            }
        ],
    }


def _seed(engine) -> str:
    with Session(engine) as session:
        area = session.scalar(
            select(GeographicArea).where(GeographicArea.name == "Partner Import Area")
        )
        if area is None:
            session.add(
                GeographicArea(
                    name="Partner Import Area",
                    level="neighbourhood",
                    active=True,
                )
            )
        category = ActivityCategory(name=f"Eat {uuid4().hex[:8]}", display_order=0)
        session.add(category)
        session.commit()
        return str(category.id)


def _delete(engine, name: str, category_id: str) -> None:
    with Session(engine) as session:
        org = session.scalar(select(Organization).where(Organization.name == name))
        if org is not None:
            session.delete(org)
        category = session.get(ActivityCategory, category_id)
        if category is not None:
            session.delete(category)
        area = session.scalar(
            select(GeographicArea).where(GeographicArea.name == "Partner Import Area")
        )
        if (
            area is not None
            and session.scalar(
                select(Location.id).where(Location.area_id == area.id).limit(1)
            )
            is None
        ):
            session.delete(area)
        session.commit()


def test_read_and_scoped_keys_are_forbidden() -> None:
    read = _post({"organizations": []}, scope="read")
    assert read["statusCode"] == 403
    assert "write access" in json.loads(read["body"])["error"]

    scoped = _post({"organizations": []}, org_scope=str(uuid4()))
    assert scoped["statusCode"] == 403
    assert "limited to one organization" in json.loads(scoped["body"])["error"]


def test_placeholder_stops_before_the_database(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.delenv("BOARD_CATALOG_MANAGER_ID", raising=False)
    response = _post(
        {"default_manager_id": _PLACEHOLDER, "organizations": [{"name": "No Write"}]}
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "default_manager_id must be a UUID"
    assert body["detail"] == "Field: default_manager_id"


def test_other_manager_is_rejected_before_the_database(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    response = _post(
        {"default_manager_id": _OTHER, "organizations": [{"name": "Wrong Manager"}]}
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "manager_id must be the catalog manager"
    assert body["detail"] == "Field: manager_id"


def test_query_manager_imports_and_can_verify_and_approve(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.delenv("BOARD_CATALOG_MANAGER_ID", raising=False)
    name = f"Partner Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(
            body,
            query=f"manager_id={_MANAGER}&mark_parent_verified=true&approve=true",
        )
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["summary"]["organizations"]["created"] == 1
        assert payload["blocked"] == []
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert str(org.manager_id) == _MANAGER
            assert org.parent_verified is True
            assert org.parent_verified_at is not None
            assert org.review_status == "approved"
            assert org.website == "https://example.test/restaurant"
            assert org.locations[0].lat == Decimal("22.2")
        assert payload["parent_verified"] == [str(org.id)]
        assert payload["approved"] == [str(org.id)]
    finally:
        _delete(test_engine, name, category_id)


def test_file_flag_does_not_verify(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Unverified Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["parent_verified"] = True
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(body)
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["parent_verified"] == []
        assert payload["approved"] == []
        assert any(
            "parent_verified" in warning
            for warning in payload["results"][0]["warnings"]
        )
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.parent_verified is False
            assert org.review_status == "pending_review"
    finally:
        _delete(test_engine, name, category_id)


def test_blocked_approval_keeps_the_import(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Blocked Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name, description=None)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(body, query="approve=true")
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["approved"] == []
        assert payload["blocked"][0]["issues"]
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.review_status == "pending_review"
    finally:
        _delete(test_engine, name, category_id)


def test_second_post_approves_the_matched_organisation(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Second Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        first = _post(body)
        assert json.loads(first["body"])["summary"]["organizations"]["created"] == 1
        second = _post(body, query="mark_parent_verified=true&approve=true")
        assert second["statusCode"] == 200
        payload = json.loads(second["body"])
        assert payload["summary"]["organizations"]["unchanged"] == 1
        assert payload["approved"]
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.parent_verified is True
            assert org.review_status == "approved"
    finally:
        _delete(test_engine, name, category_id)


def test_dry_run_rejects_the_live_flags(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    response = _post(
        {"default_manager_id": _MANAGER, "organizations": [{"name": "Dry"}]},
        query="dry_run=true&approve=true",
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "live import" in body["error"]
    assert body["detail"] == "Field: dry_run"
