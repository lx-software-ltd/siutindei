"""Full-access crud partner keys can approve one organization."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.api.partner_auth import get_partner_context
from app.api.partner_org_approve import handle_partner_org_approve
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    AuditLog,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.exceptions import AuthorizationError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import Range
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


def _insert_ready(
    engine,
    name: str,
    *,
    review_status: str = "pending_review",
    review_reason: str | None = None,
) -> tuple[str, str, str]:
    """Organization with the details an approval requires."""
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {name}", level="district", active=True)
        category = ActivityCategory(name=f"Category {name}", display_order=0)
        org = Organization(
            name=name,
            manager_id=_MANAGER,
            description="A complete club description",
            review_status=review_status,
            review_reason=review_reason,
        )
        session.add_all([area, category, org])
        session.flush()
        location = Location(
            org_id=org.id,
            area_id=area.id,
            address="1 Test Street",
            lat=Decimal("22.100000"),
            lng=Decimal("114.100000"),
        )
        session.add(location)
        session.flush()
        activity = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Class {name}",
            description="A class",
            age_range=Range(5, 12, bounds="[]"),
        )
        session.add(activity)
        session.flush()
        session.add(
            ActivityPricing(
                activity_id=activity.id,
                location_id=location.id,
                pricing_type=PricingType.PER_CLASS,
                amount=Decimal("10.00"),
            )
        )
        session.add(
            ActivitySchedule(
                activity_id=activity.id,
                location_id=location.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
        )
        session.commit()
        return str(org.id), str(area.id), str(category.id)


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


def _delete_ready(engine, org_id: str, area_id: str, category_id: str) -> None:
    _delete(engine, org_id)
    with Session(engine) as session:
        area = session.get(GeographicArea, area_id)
        category = session.get(ActivityCategory, category_id)
        if area is not None:
            session.delete(area)
        if category is not None:
            session.delete(category)
        session.commit()


def _actors(engine, org_id: str) -> list:
    with Session(engine) as session:
        return list(
            session.scalars(
                select(AuditLog.user_id)
                .where(
                    AuditLog.table_name == "organizations",
                    AuditLog.record_id == org_id,
                    AuditLog.action == "UPDATE",
                )
                .order_by(AuditLog.timestamp)
            ).all()
        )


def _post(
    org_id: str,
    body: dict,
    *,
    scope: str = "crud",
    org_scope: str = "",
    event: dict | None = None,
) -> dict:
    path = f"/v1/partner/organizations/{org_id}/approve"
    request = event or _partner_event("POST", path, scope, org_scope)
    request["path"] = path
    request["httpMethod"] = "POST"
    request["body"] = json.dumps(body)
    return _handle_partner_routes(request, "POST", "organizations", org_id)


def test_org_scoped_and_read_keys_cannot_approve() -> None:
    org_id = str(uuid4())
    scoped = _post(org_id, {}, org_scope=str(uuid4()))
    assert scoped["statusCode"] == 403
    assert "limited to one organization" in json.loads(scoped["body"])["error"]

    read = _post(org_id, {}, scope="read")
    assert read["statusCode"] == 403
    assert "write access" in json.loads(read["body"])["error"]


def test_handler_rejects_a_read_key_before_opening_the_database() -> None:
    event = _partner_event(
        "POST",
        f"/v1/partner/organizations/{uuid4()}/approve",
        "read",
        "",
    )
    partner = get_partner_context(event)
    assert partner is not None
    try:
        handle_partner_org_approve(event, "POST", str(uuid4()), partner)
    except AuthorizationError as exc:
        assert exc.status_code == 403
        assert "write access" in exc.message
        return
    raise AssertionError("read key was allowed to approve")


def test_full_access_approves_an_organization(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id, area_id, category_id = _insert_ready(
        test_engine,
        f"North Club {token}",
        review_status="rejected",
        review_reason="duplicate",
    )
    try:
        event = _partner_event(
            "POST",
            f"/v1/partner/organizations/{org_id}/approve",
            "crud",
            "",
        )
        event["requestContext"]["authorizer"]["userSub"] = "forwarded-actor"
        approved = _post(
            org_id,
            {
                "action": "approve",
                "notes": "Ready to list",
                "status": "operational",
            },
            event=event,
        )
        assert approved["statusCode"] == 200
        body = json.loads(approved["body"])
        assert body["review_status"] == "approved"
        assert body["review_reason"] is None
        assert body["review_notes"] == "Ready to list"
        assert body["status"] == "operational"
        assert body["status_source"] == "owner"
        assert body["reviewed_by"] == "forwarded-actor"
        assert body["reviewed_at"]
        assert _actors(test_engine, org_id) == ["forwarded-actor"]

        again = _post(org_id, {"action": "approve"}, event=event)
        assert again["statusCode"] == 200
        again_body = json.loads(again["body"])
        assert again_body["review_status"] == "approved"
        assert again_body["review_reason"] is None
        assert _actors(test_engine, org_id) == [
            "forwarded-actor",
            "forwarded-actor",
        ]
    finally:
        _delete_ready(test_engine, org_id, area_id, category_id)


def test_approve_can_hide_the_listing(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id, area_id, category_id = _insert_ready(
        test_engine,
        f"Hidden Club {token}",
    )
    try:
        hidden = _post(org_id, {"status": "hidden"})
        assert hidden["statusCode"] == 200
        body = json.loads(hidden["body"])
        assert body["review_status"] == "approved"
        assert body["status"] == "hidden"
        assert body["status_source"] == "owner"
    finally:
        _delete_ready(test_engine, org_id, area_id, category_id)


def test_approve_refuses_blockers_other_actions_and_unknown_organizations(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    org_id = _insert(test_engine, f"South Club {token}")
    try:
        blocked = _post(org_id, {})
        assert blocked["statusCode"] == 400
        blocked_body = json.loads(blocked["body"])
        assert "must be fixed" in blocked_body["error"]
        assert blocked_body["issues"]

        reject = _post(org_id, {"action": "reject"})
        assert reject["statusCode"] == 400
        assert "Only approve" in json.loads(reject["body"])["error"]

        forced = _post(org_id, {"force": True})
        assert forced["statusCode"] == 400
        assert "force" in json.loads(forced["body"])["error"]

        reason = _post(org_id, {"reason": "other"})
        assert reason["statusCode"] == 400
        assert (
            "reason is only set when rejecting" in json.loads(reason["body"])["error"]
        )

        with Session(test_engine) as session:
            row = session.get(Organization, org_id)
            assert row is not None
            assert row.review_status == "pending_review"
            assert row.review_reason is None

        unknown = str(uuid4())
        missing = _post(unknown, {"status": "gone"})
        assert missing["statusCode"] == 400
        assert "Invalid status" in json.loads(missing["body"])["error"]
        notes = _post(unknown, {"notes": 5})
        assert notes["statusCode"] == 400
        assert "notes must be a string" in json.loads(notes["body"])["error"]
        absent = _post(unknown, {})
        assert absent["statusCode"] == 404

        own_key = _post(org_id, {}, org_scope=org_id)
        assert own_key["statusCode"] == 403
        assert "limited to one organization" in json.loads(own_key["body"])["error"]

        extra_path = f"/v1/partner/organizations/{org_id}/approve/anything"
        extra_event = _partner_event("POST", extra_path, "crud", "")
        extra_event["body"] = json.dumps({})
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

        path = f"/v1/partner/organizations/{org_id}/approve"
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
    org_id, area_id, category_id = _insert_ready(
        test_engine,
        f"East Club {token}",
    )
    try:
        event = _partner_event(
            "POST",
            f"/v1/partner/organizations/{org_id}/approve",
            "crud",
            "",
        )
        key_id = event["requestContext"]["authorizer"]["apiKeyId"]
        del event["requestContext"]["authorizer"]["userSub"]
        approved = _post(org_id, {}, event=event)
        assert approved["statusCode"] == 200
        assert json.loads(approved["body"])["reviewed_by"] == f"api-key:{key_id}"
        assert _actors(test_engine, org_id) == [f"api-key:{key_id}"]
    finally:
        _delete_ready(test_engine, org_id, area_id, category_id)
