"""Full-access partner keys list category reviews and activity embeds."""

from __future__ import annotations

import json
from uuid import uuid4

from psycopg.types.range import Range
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.admin import _handle_partner_routes, lambda_handler
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import CategorySuggestion
from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_crud.get_engine", lambda: engine)
    monkeypatch.setattr(
        "app.api.partner_category_reviews.get_engine", lambda: engine
    )


def _org(org_id, name: str, review_status: str) -> Organization:
    return Organization(
        id=org_id,
        name=name,
        manager_id=_MANAGER,
        review_status=review_status,
    )


def _activity(activity_id, org_id, category_id, name: str) -> Activity:
    return Activity(
        id=activity_id,
        org_id=org_id,
        category_id=category_id,
        name=name,
        age_range=Range(5, 12, bounds="[]"),
    )


def _review(*, run_id, activity_id, org_id, **overrides):
    values = {
        "scan_run_id": run_id,
        "activity_id": activity_id,
        "org_id": org_id,
        "verdict": "confirm",
        "status": "confirmed",
        "confidence": 0.95,
    }
    values.update(overrides)
    return ActivityCategoryReview(**values)


def test_full_access_lists_confirmed_and_suggested_reviews(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    pending_org = uuid4()
    approved_org = uuid4()
    category_id = uuid4()
    confirmed_id = uuid4()
    proposed_id = uuid4()
    suggestion_id = uuid4()
    run_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Partner Sport"))
        session.add(_org(pending_org, "Pending Club", "pending_review"))
        session.add(_org(approved_org, "Approved Club", "approved"))
        session.add(_activity(confirmed_id, approved_org, category_id, "Swim"))
        session.add(_activity(proposed_id, pending_org, category_id, "Clay"))
        session.add(
            CategoryScanRun(
                id=run_id,
                status="done",
                batch_size=10,
                batches_total=1,
                total_activities=2,
            )
        )
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint=f"scan-{suggestion_id.hex[:8]}",
                requested_name="Pottery",
                source="scan",
                status="pending",
                enrichment_status="done",
                suggested_name="Pottery",
            )
        )
        session.add(
            _review(
                run_id=run_id,
                activity_id=confirmed_id,
                org_id=approved_org,
                current_category_id=category_id,
            )
        )
        session.add(
            _review(
                run_id=run_id,
                activity_id=proposed_id,
                org_id=pending_org,
                verdict="propose",
                status="pending",
                suggestion_id=suggestion_id,
                current_category_id=category_id,
            )
        )
        session.commit()
    try:
        event = _partner_event(
            "GET", "/v1/partner/category-reviews", "read", ""
        )
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        items = json.loads(response["body"])["items"]
        by_activity = {item["activity_id"]: item for item in items}
        confirmed = by_activity[str(confirmed_id)]
        assert confirmed["status"] == "confirmed"
        assert confirmed["verdict"] == "confirm"
        assert confirmed["current_category_name"] == "Partner Sport"
        assert confirmed["org_name"] == "Approved Club"
        assert "decided_by" not in confirmed
        proposed = by_activity[str(proposed_id)]
        assert proposed["status"] == "pending"
        assert proposed["verdict"] == "propose"
        assert proposed["proposed_category_name"] == "Pottery"
        assert proposed["suggestion_id"] == str(suggestion_id)
    finally:
        _cleanup(
            test_engine,
            pending_org,
            approved_org,
            category_id,
            confirmed_id,
            proposed_id,
            suggestion_id,
            run_id,
        )


def test_org_scoped_key_sees_only_its_category_reviews(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    owned_id = uuid4()
    other_id = uuid4()
    category_id = uuid4()
    owned_activity = uuid4()
    other_activity = uuid4()
    run_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Scoped Sport"))
        session.add(_org(owned_id, "Owned Club", "pending_review"))
        session.add(_org(other_id, "Other Club", "pending_review"))
        session.add(_activity(owned_activity, owned_id, category_id, "Owned"))
        session.add(_activity(other_activity, other_id, category_id, "Other"))
        session.add(
            CategoryScanRun(
                id=run_id,
                status="done",
                batch_size=10,
                batches_total=1,
                total_activities=2,
            )
        )
        session.add(
            _review(
                run_id=run_id,
                activity_id=owned_activity,
                org_id=owned_id,
                current_category_id=category_id,
            )
        )
        session.add(
            _review(
                run_id=run_id,
                activity_id=other_activity,
                org_id=other_id,
                current_category_id=category_id,
            )
        )
        session.commit()
    try:
        event = _partner_event(
            "GET", "/v1/partner/category-reviews", "read", str(owned_id)
        )
        response = _handle_partner_routes(
            event, "GET", "category-reviews", None
        )
        assert response["statusCode"] == 200
        items = json.loads(response["body"])["items"]
        assert {item["org_id"] for item in items} == {str(owned_id)}
    finally:
        _cleanup(
            test_engine,
            owned_id,
            other_id,
            category_id,
            owned_activity,
            other_activity,
            run_id,
        )


def test_activity_detail_embeds_latest_review(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    org_id = uuid4()
    category_id = uuid4()
    checked_id = uuid4()
    unchecked_id = uuid4()
    run_id = uuid4()
    with Session(test_engine) as session:
        session.add(ActivityCategory(id=category_id, name="Embed Sport"))
        session.add(_org(org_id, "Embed Club", "approved"))
        session.add(_activity(checked_id, org_id, category_id, "Checked"))
        session.add(_activity(unchecked_id, org_id, category_id, "Unchecked"))
        session.add(
            CategoryScanRun(
                id=run_id,
                status="done",
                batch_size=10,
                batches_total=1,
                total_activities=1,
            )
        )
        session.add(
            _review(
                run_id=run_id,
                activity_id=checked_id,
                org_id=org_id,
                current_category_id=category_id,
                verdict="reassign",
                status="pending",
                proposed_category_id=category_id,
            )
        )
        session.commit()
    try:
        checked = _handle_partner_routes(
            _partner_event(
                "GET", f"/v1/partner/activities/{checked_id}", "read", ""
            ),
            "GET",
            "activities",
            str(checked_id),
        )
        assert checked["statusCode"] == 200
        checked_body = json.loads(checked["body"])
        assert checked_body["category_id"] == str(category_id)
        review = checked_body["category_review"]
        assert review["status"] == "pending"
        assert review["verdict"] == "reassign"
        assert review["proposed_category_id"] == str(category_id)

        unchecked = _handle_partner_routes(
            _partner_event(
                "GET", f"/v1/partner/activities/{unchecked_id}", "read", ""
            ),
            "GET",
            "activities",
            str(unchecked_id),
        )
        assert unchecked["statusCode"] == 200
        assert json.loads(unchecked["body"])["category_review"] is None
    finally:
        _cleanup(
            test_engine,
            org_id,
            category_id,
            checked_id,
            unchecked_id,
            run_id,
        )


def test_partner_cannot_write_category_reviews() -> None:
    event = _partner_event("POST", "/v1/partner/category-reviews", "crud", "")
    response = _handle_partner_routes(event, "POST", "category-reviews", None)
    assert response["statusCode"] == 404


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(
            delete(ActivityCategoryReview).where(
                ActivityCategoryReview.activity_id.in_(ids)
            )
        )
        session.execute(
            delete(CategorySuggestion).where(CategorySuggestion.id.in_(ids))
        )
        session.execute(delete(CategoryScanRun).where(CategoryScanRun.id.in_(ids)))
        for model in (Activity, Organization, ActivityCategory):
            for row_id in ids:
                row = session.get(model, row_id)
                if row is not None:
                    session.delete(row)
        session.commit()
