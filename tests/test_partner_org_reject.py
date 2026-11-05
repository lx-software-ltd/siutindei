"""Full-access crud partner keys can reject one organization."""

from __future__ import annotations

import json
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.api.partner_auth import get_partner_context
from app.api.partner_org_reject import handle_partner_org_reject
from app.db.models import AuditLog, Organization
from app.exceptions import AuthorizationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_org_review_actions.get_engine", lambda: engine)


def _insert(engine, name: str) -> str:
    with Session(engine) as session:
        org = Organization(name=name, manager_id=_MANAGER)
        session.add(org)
        session.commit()
        return str(org.id)


def _delete(engine, org_id: str) -> None:
    with Session(engine) as session:
        row = session.get(Organization, org_id)
        if row is not None:
            session.delete(row)
            session.commit()
        session.execute(
            delete(AuditLog).where(
                AuditLog.table_name == "organizations",
                AuditLog.record_id == org_id,
            )
        )
        session.commit()


def _post(
    org_id: str,
    body: dict,
    *,
    scope: str = "crud",
    org_scope: str = "",
    event: dict | None = None,
) -> dict:
    path = f"/v1/partner/organizations/{org_id}/reject"
    request = event or _partner_event("POST", path, scope, org_scope)
    request["path"] = path
    request["httpMethod"] = "POST"
    request["body"] = json.dumps(body)
    return _handle_partner_routes(request, "POST", "organizations", org_id)


def test_org_scoped_and_read_keys_cannot_reject() -> None:
    org_id = str(uuid4())
    scoped = _post(
        org_id,
        {"reason": "other"},
        org_scope=str(uuid4()),
    )
    assert scoped["statusCode"] == 403
    assert "limited to one organization" in json.loads(scoped["body"])["error"]

    read = _post(org_id, {"reason": "other"}, scope="read")
    assert read["statusCode"] == 403
    assert "write access" in json.loads(read["body"])["error"]


def test_handler_rejects_a_read_key_before_opening_the_database() -> None:
    event = _partner_event(
        "POST",
        f"/v1/partner/organizations/{uuid4()}/reject",
        "read",
        "",
    )
    partner = get_partner_context(event)
    assert partner is not None
    try:
        handle_partner_org_reject(event, "POST", str(uuid4()), partner)
    except AuthorizationError as exc:
        assert exc.status_code == 403
        assert "write access" in exc.message
        return
    raise AssertionError("read key was allowed to reject")


def test_full_access_rejects_an_organization(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id = _insert(test_engine, f"North Club {token}")
    try:
        event = _partner_event(
            "POST",
            f"/v1/partner/organizations/{org_id}/reject",
            "crud",
            "",
        )
        event["requestContext"]["authorizer"]["userSub"] = "forwarded-actor"
        rejected = _post(
            org_id,
            {
                "reason": "duplicate",
                "notes": "Same provider",
                "status": "hidden",
            },
            event=event,
        )
        assert rejected["statusCode"] == 200
        body = json.loads(rejected["body"])
        assert body["review_status"] == "rejected"
        assert body["review_reason"] == "duplicate"
        assert body["review_notes"] == "Same provider"
        assert body["status"] == "hidden"
        assert body["status_source"] == "owner"
        assert body["reviewed_by"] == "forwarded-actor"
        assert body["reviewed_at"]

        again = _post(org_id, {"reason": "poor_data"})
        assert again["statusCode"] == 200
        again_body = json.loads(again["body"])
        assert again_body["review_reason"] == "poor_data"
        assert again_body["status"] == "hidden"

        with Session(test_engine) as session:
            actors = session.scalars(
                select(AuditLog.user_id)
                .where(
                    AuditLog.table_name == "organizations",
                    AuditLog.record_id == org_id,
                    AuditLog.action == "UPDATE",
                )
                .order_by(AuditLog.timestamp)
            ).all()
        assert actors == ["forwarded-actor", again_body["reviewed_by"]]
    finally:
        _delete(test_engine, org_id)


def test_reject_refuses_other_actions_and_unknown_organizations(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id = _insert(test_engine, f"South Club {token}")
    try:
        approve = _post(org_id, {"action": "approve", "reason": "other"})
        assert approve["statusCode"] == 400
        assert "Only reject" in json.loads(approve["body"])["error"]

        forced = _post(org_id, {"reason": "other", "force": True})
        assert forced["statusCode"] == 400
        assert "force" in json.loads(forced["body"])["error"]

        missing = _post(org_id, {})
        assert missing["statusCode"] == 400
        assert "reason is required" in json.loads(missing["body"])["error"]

        invalid = _post(org_id, {"reason": 12})
        assert invalid["statusCode"] == 400
        assert "Invalid reason" in json.loads(invalid["body"])["error"]

        with Session(test_engine) as session:
            row = session.get(Organization, org_id)
            assert row is not None
            assert row.review_status == "pending_review"
            assert row.review_reason is None

        unknown = str(uuid4())
        missing = _post(unknown, {"reason": "other", "status": "gone"})
        assert missing["statusCode"] == 400
        assert "Invalid status" in json.loads(missing["body"])["error"]
        notes = _post(unknown, {"reason": "other", "notes": 5})
        assert notes["statusCode"] == 400
        assert "notes must be a string" in json.loads(notes["body"])["error"]
        absent = _post(unknown, {"reason": "other"})
        assert absent["statusCode"] == 404

        own_key = _post(org_id, {"reason": "other"}, org_scope=org_id)
        assert own_key["statusCode"] == 403
        assert "limited to one organization" in json.loads(own_key["body"])["error"]

        extra_path = f"/v1/partner/organizations/{org_id}/reject/anything"
        extra_event = _partner_event("POST", extra_path, "crud", "")
        extra_event["body"] = json.dumps({"reason": "other"})
        extra = _handle_partner_routes(
            extra_event,
            "POST",
            "organizations",
            org_id,
        )
        assert extra["statusCode"] == 404
        with Session(test_engine) as session:
            row = session.get(Organization, org_id)
            assert row is not None
            assert row.review_status == "pending_review"

        path = f"/v1/partner/organizations/{org_id}/reject"
        listed = _handle_partner_routes(
            _partner_event("GET", path, "read", ""),
            "GET",
            "organizations",
            org_id,
        )
        assert listed["statusCode"] == 404
    finally:
        _delete(test_engine, org_id)


def test_omitted_user_sub_records_the_key(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id = _insert(test_engine, f"East Club {token}")
    try:
        event = _partner_event(
            "POST",
            f"/v1/partner/organizations/{org_id}/reject",
            "crud",
            "",
        )
        key_id = event["requestContext"]["authorizer"]["apiKeyId"]
        del event["requestContext"]["authorizer"]["userSub"]
        rejected = _post(org_id, {"reason": "not_relevant"}, event=event)
        assert rejected["statusCode"] == 200
        assert json.loads(rejected["body"])["reviewed_by"] == f"api-key:{key_id}"
    finally:
        _delete(test_engine, org_id)
