"""Full-access partner keys read and manage activity categories."""

from __future__ import annotations

import json
import threading
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.api.partner_activity_categories import handle_partner_activity_categories
from app.api.partner_auth import get_partner_context
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    PENDING_CATEGORY_NAME,
    SCHOOLS_CATEGORY_ID,
)
from app.db.repositories.activity_category import _reraise_duplicate_name
from app.exceptions import AuthorizationError, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
            {"name": renamed},
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
        _delete_rows(test_engine, created)


def test_handler_rejects_a_read_key_before_opening_the_database() -> None:
    event = _partner_event("POST", "/v1/partner/activity-categories", "read", "")
    event["body"] = json.dumps({"name": "Read Only Kayak"})
    partner = get_partner_context(event)
    assert partner is not None
    try:
        handle_partner_activity_categories(event, "POST", partner, None)
    except AuthorizationError as exc:
        assert exc.status_code == 403
        assert "write access" in exc.message
        return
    raise AssertionError("read key was allowed to create")


def test_duplicate_name_constraint_is_a_validation_error() -> None:
    import pytest

    with pytest.raises(ValidationError):
        _reraise_duplicate_name(
            IntegrityError(
                "INSERT",
                {},
                Exception("uq_activity_category_parent_name"),
            )
        )
    _reraise_duplicate_name(IntegrityError("INSERT", {}, Exception("other")))


def test_category_writes_cover_the_rejected_shapes(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    created: list[str] = []
    pending_existed = True
    try:
        bad_parent = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": f"Bad parent {token}", "parent_id": 12},
        )
        assert bad_parent["statusCode"] == 400
        assert "Invalid UUID" in json.loads(bad_parent["body"])["error"]

        wizard = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": f"Wizard {token}", "show_in_wizard": True},
        )
        assert wizard["statusCode"] == 400
        assert "admin console" in json.loads(wizard["body"])["error"]

        hidden = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": f"Hidden {token}", "hidden_from_public": True},
        )
        assert hidden["statusCode"] == 400
        assert "hidden_from_public" in json.loads(hidden["body"])["error"]

        schools = str(SCHOOLS_CATEGORY_ID)
        renamed_root = _write(
            "PUT",
            f"/v1/partner/activity-categories/{schools}",
            schools,
            {"name": f"Renamed root {token}"},
        )
        assert renamed_root["statusCode"] == 400
        assert "Fixed root" in json.loads(renamed_root["body"])["error"]
        deleted_root = _handle_partner_routes(
            _partner_event(
                "DELETE",
                f"/v1/partner/activity-categories/{schools}",
                "crud",
                "",
            ),
            "DELETE",
            "activity-categories",
            schools,
        )
        assert deleted_root["statusCode"] == 400
        detail = _handle_partner_routes(
            _partner_event(
                "GET",
                f"/v1/partner/activity-categories/{schools}",
                "read",
                "",
            ),
            "GET",
            "activity-categories",
            schools,
        )
        root_body = json.loads(detail["body"])
        assert root_body["hidden_from_public"] is True
        assert root_body["system_role"] == "schools"

        with Session(test_engine) as session:
            pending_existed = (
                session.get(ActivityCategory, PENDING_CATEGORY_ID) is not None
            )
            if not pending_existed:
                session.add(
                    ActivityCategory(
                        id=PENDING_CATEGORY_ID,
                        name=PENDING_CATEGORY_NAME,
                        show_in_wizard=False,
                    )
                )
                session.commit()

        extra_id = str(uuid4())
        posted_with_id = _write(
            "POST",
            f"/v1/partner/activity-categories/{extra_id}",
            extra_id,
            {"name": f"Ignored {token}"},
        )
        assert posted_with_id["statusCode"] == 404

        missing_id = str(uuid4())
        missing = _write(
            "PUT",
            f"/v1/partner/activity-categories/{missing_id}",
            missing_id,
            {"name": f"Missing {token}"},
        )
        assert missing["statusCode"] == 404

        pending = _write(
            "PUT",
            f"/v1/partner/activity-categories/{PENDING_CATEGORY_ID}",
            str(PENDING_CATEGORY_ID),
            {"name": f"Renamed pending {token}"},
        )
        assert pending["statusCode"] == 400
        assert "renamed" in json.loads(pending["body"])["error"]

        parent = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": f"Parent {token}"},
        )
        assert parent["statusCode"] == 201
        parent_id = json.loads(parent["body"])["id"]
        created.append(parent_id)
        child = _write(
            "POST",
            "/v1/partner/activity-categories",
            None,
            {"name": f"Child {token}", "parent_id": parent_id},
        )
        assert child["statusCode"] == 201
        child_id = json.loads(child["body"])["id"]
        created.append(child_id)

        cycle = _write(
            "PUT",
            f"/v1/partner/activity-categories/{parent_id}",
            parent_id,
            {"parent_id": child_id},
        )
        assert cycle["statusCode"] == 400
        assert "descendant" in json.loads(cycle["body"])["error"]

        patched = _write(
            "PATCH",
            f"/v1/partner/activity-categories/{child_id}",
            child_id,
            {"name": f"Child renamed {token}"},
        )
        assert patched["statusCode"] == 200
        assert json.loads(patched["body"])["name"] == f"Child renamed {token}"

        wizard_update = _write(
            "PATCH",
            f"/v1/partner/activity-categories/{child_id}",
            child_id,
            {"show_in_wizard": False},
        )
        assert wizard_update["statusCode"] == 400
    finally:
        _delete_rows(test_engine, created)
        if not pending_existed:
            _delete_rows(test_engine, [str(PENDING_CATEGORY_ID)])


def test_concurrent_creates_reject_the_second_name(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    names = [f"Race {token}", f"race {token}"]
    barrier = threading.Barrier(2, timeout=10)
    results: list[dict] = []

    def create(name: str) -> None:
        barrier.wait()
        results.append(
            _write(
                "POST",
                "/v1/partner/activity-categories",
                None,
                {"name": name},
            )
        )

    threads = [threading.Thread(target=create, args=(name,)) for name in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    created = [
        json.loads(result["body"])["id"]
        for result in results
        if result["statusCode"] == 201
    ]
    try:
        codes = sorted(result["statusCode"] for result in results)
        assert codes == [201, 400]
        assert any(
            "already exists" in json.loads(result["body"])["error"]
            for result in results
            if result["statusCode"] == 400
        )
    finally:
        _delete_rows(test_engine, created)


def _delete_rows(engine: object, category_ids: list[str]) -> None:
    with Session(engine) as session:
        for category_id in reversed(category_ids):
            row = session.get(ActivityCategory, category_id)
            if row is not None:
                session.delete(row)
        session.commit()


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
