"""Full-access partner keys read and manage activity categories."""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.admin import _handle_partner_routes
from app.db.models import ActivityCategory
from tests.test_partner_routes import _partner_event


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr(
        "app.api.partner_activity_categories.get_engine", lambda: engine
    )


def test_org_scoped_key_cannot_use_activity_categories() -> None:
    org_id = str(uuid4())
    event = _partner_event("GET", "/v1/partner/activity-categories", "read", org_id)
    response = _handle_partner_routes(event, "GET", "activity-categories", None)
    assert response["statusCode"] == 403
    assert "limited to one organization" in json.loads(response["body"])["error"]

    delete = _partner_event(
        "DELETE",
        f"/v1/partner/activity-categories/{uuid4()}",
        "crud",
        org_id,
    )
    response = _handle_partner_routes(
        delete, "DELETE", "activity-categories", delete["path"].rsplit("/", 1)[-1]
    )
    assert response["statusCode"] == 403

    create = _partner_event("POST", "/v1/partner/activity-categories", "crud", org_id)
    create["body"] = json.dumps({"name": "Scoped Kayak"})
    response = _handle_partner_routes(create, "POST", "activity-categories", None)
    assert response["statusCode"] == 403


def test_full_access_lists_and_deletes_an_empty_category(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    category_id = uuid4()
    with Session(test_engine) as session:
        session.add(
            ActivityCategory(
                id=category_id,
                name="Orphan Swimming",
                show_in_wizard=False,
            )
        )
        session.commit()
    try:
        listed = _handle_partner_routes(
            _partner_event("GET", "/v1/partner/activity-categories", "read", ""),
            "GET",
            "activity-categories",
            None,
        )
        assert listed["statusCode"] == 200
        names = _tree_names(json.loads(listed["body"])["items"])
        assert "Orphan Swimming" in names

        detail = _handle_partner_routes(
            _partner_event(
                "GET",
                f"/v1/partner/activity-categories/{category_id}",
                "read",
                "",
            ),
            "GET",
            "activity-categories",
            str(category_id),
        )
        assert detail["statusCode"] == 200
        assert json.loads(detail["body"])["name"] == "Orphan Swimming"

        deleted = _handle_partner_routes(
            _partner_event(
                "DELETE",
                f"/v1/partner/activity-categories/{category_id}",
                "crud",
                "",
            ),
            "DELETE",
            "activity-categories",
            str(category_id),
        )
        assert deleted["statusCode"] == 204
        missing = _handle_partner_routes(
            _partner_event(
                "GET",
                f"/v1/partner/activity-categories/{category_id}",
                "read",
                "",
            ),
            "GET",
            "activity-categories",
            str(category_id),
        )
        assert missing["statusCode"] == 404
    finally:
        with Session(test_engine) as session:
            row = session.get(ActivityCategory, category_id)
            if row is not None:
                session.delete(row)
                session.commit()


def test_read_key_cannot_create_a_category() -> None:
    create = _partner_event("POST", "/v1/partner/activity-categories", "read", "")
    create["body"] = json.dumps({"name": "Read Only Kayak"})
    response = _handle_partner_routes(create, "POST", "activity-categories", None)
    assert response["statusCode"] == 403
    assert "write access" in json.loads(response["body"])["error"]


def test_full_access_creates_updates_and_reads(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    parent_name = f"Water {token}"
    child_name = f"Kayak {token}"
    renamed = f"Canoe {token}"
    created: list[str] = []
    try:
        parent = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": parent_name, "display_order": 4},
        )
        assert parent["statusCode"] == 201
        parent_body = json.loads(parent["body"])
        assert parent_body["name"] == parent_name
        assert parent_body["parent_id"] is None
        assert parent_body["show_in_wizard"] is False
        assert parent_body["display_order"] == 4
        created.append(parent_body["id"])

        missing = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"display_order": 1},
        )
        assert missing["statusCode"] == 400

        duplicate = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": parent_name.lower()},
        )
        assert duplicate["statusCode"] == 400

        child = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": child_name, "parent_id": parent_body["id"]},
        )
        assert child["statusCode"] == 201
        child_body = json.loads(child["body"])
        assert child_body["parent_id"] == parent_body["id"]
        created.append(child_body["id"])

        updated = _write(
            "PUT",
            f"/v1/partner/activity-categories/{child_body['id']}",
            child_body["id"],
            {"name": renamed, "show_in_wizard": False},
        )
        assert updated["statusCode"] == 200
        assert json.loads(updated["body"])["name"] == renamed

        detail = _handle_partner_routes(
            _partner_event(
                "GET",
                f"/v1/partner/activity-categories/{child_body['id']}",
                "read",
                "",
            ),
            "GET",
            "activity-categories",
            child_body["id"],
        )
        assert detail["statusCode"] == 200
        assert json.loads(detail["body"])["name"] == renamed

        listed = _handle_partner_routes(
            _partner_event("GET", "/v1/partner/activity-categories", "read", ""),
            "GET",
            "activity-categories",
            None,
        )
        assert listed["statusCode"] == 200
        assert renamed in _tree_names(json.loads(listed["body"])["items"])
    finally:
        for category_id in reversed(created):
            _handle_partner_routes(
                _partner_event(
                    "DELETE",
                    f"/v1/partner/activity-categories/{category_id}",
                    "crud",
                    "",
                ),
                "DELETE",
                "activity-categories",
                category_id,
            )


def _write(
    method: str,
    path: str,
    resource_id: str | None,
    body: dict,
) -> dict:
    event = _partner_event(method, path, "crud", "")
    event["body"] = json.dumps(body)
    return _handle_partner_routes(event, method, "activity-categories", resource_id)


def _tree_names(nodes: list[dict]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        names.add(node["name"])
        names.update(_tree_names(node.get("children") or []))
    return names
