"""Full-access partner keys list and delete activity categories."""

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


def test_full_access_cannot_post_activity_categories() -> None:
    event = _partner_event("POST", "/v1/partner/activity-categories", "crud", "")
    response = _handle_partner_routes(event, "POST", "activity-categories", None)
    assert response["statusCode"] == 404


def _tree_names(nodes: list[dict]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        names.add(node["name"])
        names.update(_tree_names(node.get("children") or []))
    return names
