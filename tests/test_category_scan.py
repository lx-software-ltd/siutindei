"""Category checks for activities in pending-review organizations."""

from __future__ import annotations

import json
from uuid import uuid4

from psycopg.types.range import Range
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin import lambda_handler
from app.api.admin_category_reviews import _query, _serialize
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.services.category_suggestions.capture import ensure_pending_category
from app.services.category_suggestions.decisions import apply_decision
from app.services.category_suggestions.reviews import apply_review_decision
from app.exceptions import ValidationError
from app.services.category_suggestions.scan import (
    CategoryScanBusy,
    select_candidate_ids,
    start_scan,
)
from app.services.category_suggestions.scan_apply import store_scan_batch
from app.services.category_suggestions.settings import get_settings
from app.services.org_review import load_snapshots
from app.services.org_review_sql import BLOCKER_ISSUE_CODES, issue_clause


def _run(session: Session, **overrides: object) -> CategoryScanRun:
    values = {
        "status": "queued",
        "batch_size": 10,
        "batches_total": 1,
        "total_activities": 1,
    }
    values.update(overrides)
    run = CategoryScanRun(**values)
    session.add(run)
    session.flush()
    return run


def _result(activity: Activity, **overrides: object) -> dict:
    payload = {
        "activity_id": str(activity.id),
        "verdict": "confirm",
        "confidence": 0.95,
        "rationale": "Fits",
    }
    payload.update(overrides)
    return payload


def test_auto_assigns_reassignment_above_threshold(
    db_session, sample_activity, sample_activity_category
) -> None:
    other = ActivityCategory(name="Ceramics Studio", display_order=2)
    db_session.add(other)
    db_session.flush()
    run = _run(db_session)
    stored = store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(other.id),
                    rationale="Hands-on clay",
                )
            ]
        },
        {"cost_usd": 0.01},
        message_id="batch-1",
    )
    assert stored is True
    db_session.refresh(sample_activity)
    db_session.refresh(run)
    assert str(sample_activity.category_id) == str(other.id)
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.status == "auto_applied"
    assert str(review.previous_category_id) == str(sample_activity_category.id)
    assert run.status == "done"
    assert run.auto_applied == 1
    assert float(run.cost_usd) == 0.01
    again = store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {"results": []},
        {},
        message_id="batch-1",
    )
    assert again is False


def test_low_confidence_stays_pending(db_session, sample_activity) -> None:
    other = ActivityCategory(name="Music Room", display_order=3)
    db_session.add(other)
    db_session.flush()
    original = sample_activity.category_id
    run = _run(db_session)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(other.id),
                    confidence=0.4,
                )
            ]
        },
        {},
    )
    db_session.refresh(sample_activity)
    assert sample_activity.category_id == original
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.status == "pending"
    assert str(review.proposed_category_id) == str(other.id)


def test_confirm_and_pending_placeholder(
    db_session, sample_activity, sample_organization
) -> None:
    run = _run(db_session, batches_total=1, total_activities=1)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {"results": [_result(sample_activity)]},
        {},
    )
    assert (
        db_session.scalars(select(ActivityCategoryReview)).one().status == "confirmed"
    )

    ensure_pending_category(db_session)
    pending_activity = Activity(
        org_id=sample_organization.id,
        category_id=PENDING_CATEGORY_ID,
        name="Unsorted club",
        age_range=Range(4, 8, bounds="[]"),
    )
    db_session.add(pending_activity)
    db_session.flush()
    second = _run(db_session)
    store_scan_batch(
        db_session,
        second.id,
        [str(pending_activity.id)],
        {"results": [_result(pending_activity, verdict="confirm")]},
        {},
    )
    review = db_session.scalars(
        select(ActivityCategoryReview).where(
            ActivityCategoryReview.activity_id == pending_activity.id
        )
    ).one()
    assert review.status == "pending"
    assert str(pending_activity.category_id) == str(PENDING_CATEGORY_ID)


def test_proposal_groups_and_named_match_becomes_reassign(
    db_session, sample_activity, sample_organization, sample_activity_category
) -> None:
    sibling = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity.category_id,
        name="Second clay club",
        age_range=Range(6, 10, bounds="[]"),
    )
    db_session.add(sibling)
    db_session.flush()
    run = _run(db_session, batches_total=1, total_activities=2)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id), str(sibling.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="propose",
                    propose={"name_en": "Wheel throwing", "name_zh": "拉坯"},
                ),
                _result(
                    sibling,
                    verdict="propose",
                    propose={"name_en": "Wheel throwing", "name_zh": "拉坯"},
                ),
            ]
        },
        {},
    )
    suggestion = db_session.scalars(select(CategorySuggestion)).one()
    assert suggestion.source == "scan"
    assert suggestion.requested_name == "Wheel throwing"
    assert suggestion.activity_count == 2
    assert (
        db_session.scalar(select(func.count()).select_from(CategorySuggestionActivity))
        == 2
    )

    other = ActivityCategory(name="Outdoor Games", display_order=4)
    db_session.add(other)
    db_session.flush()
    sample_activity.category_id = other.id
    db_session.flush()
    matched = _run(db_session)
    store_scan_batch(
        db_session,
        matched.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="propose",
                    propose={"name_en": sample_activity_category.name},
                    confidence=0.99,
                )
            ]
        },
        {},
    )
    db_session.refresh(sample_activity)
    assert str(sample_activity.category_id) == str(sample_activity_category.id)


def test_dismissed_and_approved_org_are_not_auto_applied(
    db_session, sample_activity, sample_organization, sample_activity_category
) -> None:
    other = ActivityCategory(name="Dance Hall", display_order=5)
    db_session.add(other)
    db_session.flush()
    earlier = _run(db_session, status="done", batches_total=2)
    db_session.add(
        ActivityCategoryReview(
            scan_run_id=earlier.id,
            activity_id=sample_activity.id,
            org_id=sample_organization.id,
            verdict="reassign",
            status="dismissed",
        )
    )
    db_session.flush()
    run = _run(db_session)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(other.id),
                    confidence=0.99,
                )
            ]
        },
        {},
    )
    db_session.refresh(sample_activity)
    assert str(sample_activity.category_id) == str(sample_activity_category.id)
    latest = db_session.scalars(
        select(ActivityCategoryReview).where(
            ActivityCategoryReview.scan_run_id == run.id
        )
    ).one()
    assert latest.status == "pending"

    sample_organization.review_status = "approved"
    fresh = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Approved org class",
        age_range=Range(5, 9, bounds="[]"),
    )
    db_session.add(fresh)
    db_session.flush()
    approved_run = _run(db_session)
    store_scan_batch(
        db_session,
        approved_run.id,
        [str(fresh.id)],
        {
            "results": [
                _result(
                    fresh,
                    verdict="reassign",
                    category_id=str(other.id),
                    confidence=0.99,
                )
            ]
        },
        {},
    )
    db_session.refresh(fresh)
    assert str(fresh.category_id) == str(sample_activity_category.id)


def test_candidates_skip_recent_decisions_and_approved_orgs(
    db_session, sample_activity, sample_organization
) -> None:
    org_id = sample_organization.id
    assert select_candidate_ids(db_session, org_id=org_id) == [sample_activity.id]
    run = _run(db_session, status="done", batches_total=0)
    db_session.add(
        ActivityCategoryReview(
            scan_run_id=run.id,
            activity_id=sample_activity.id,
            org_id=org_id,
            verdict="confirm",
            status="confirmed",
        )
    )
    db_session.flush()
    assert select_candidate_ids(db_session, org_id=org_id) == []
    assert select_candidate_ids(db_session, org_id=org_id, rescan=True) == [
        sample_activity.id
    ]
    sample_organization.review_status = "approved"
    db_session.flush()
    assert select_candidate_ids(db_session, org_id=org_id, rescan=True) == []
    assert select_candidate_ids(
        db_session, org_id=org_id, rescan=True, review_scope="all"
    ) == [sample_activity.id]


def test_sweep_pending_skips_approved_orgs(
    db_session, sample_activity, sample_organization
) -> None:
    sample_organization.review_status = "approved"
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"org_id": str(sample_organization.id), "review_scope": "pending_review"},
        requested_by="admin",
    )
    assert run.status == "done"
    assert batches == []
    assert run.total_activities == 0


def test_sweep_all_includes_approved_orgs(
    db_session, sample_activity, sample_organization
) -> None:
    sample_organization.review_status = "approved"
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"org_id": str(sample_organization.id), "review_scope": "all"},
        requested_by="admin",
    )
    assert run.status == "queued"
    assert batches == [[str(sample_activity.id)]]


def test_scan_rejects_unknown_review_scope(db_session) -> None:
    try:
        start_scan(db_session, {"review_scope": "nope"}, requested_by="admin")
        raise AssertionError("unknown review_scope should fail")
    except ValidationError as exc:
        assert exc.field == "review_scope"


def test_start_scan_queues_one_batch_and_rejects_a_second(
    db_session, sample_activity
) -> None:
    run, batches = start_scan(
        db_session,
        {"org_id": str(sample_activity.org_id)},
        requested_by="admin-user",
    )
    assert run.status == "queued"
    assert batches == [[str(sample_activity.id)]]
    try:
        start_scan(db_session, {}, requested_by="admin-user")
        raise AssertionError("second scan should be busy")
    except CategoryScanBusy:
        pass


def test_revert_and_suggestion_decision_move_the_activity(
    db_session, sample_activity, sample_activity_category, sample_organization
) -> None:
    other = ActivityCategory(name="Target Category", display_order=6)
    db_session.add(other)
    db_session.flush()
    get_settings(db_session)
    run = _run(db_session)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(other.id),
                )
            ]
        },
        {},
    )
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    apply_review_decision(db_session, review, {"action": "revert"}, decided_by="admin")
    db_session.refresh(sample_activity)
    assert str(sample_activity.category_id) == str(sample_activity_category.id)
    assert review.status == "reverted"

    suggestion = CategorySuggestion(
        fingerprint="scan-map-target",
        requested_name="Mapped label",
        source="scan",
        status="pending",
        enrichment_status="done",
    )
    mapped_run = _run(db_session, status="done", batches_total=0)
    db_session.add(suggestion)
    db_session.flush()
    waiting = ActivityCategoryReview(
        scan_run_id=mapped_run.id,
        activity_id=sample_activity.id,
        org_id=sample_organization.id,
        verdict="propose",
        status="pending",
        suggestion_id=suggestion.id,
    )
    db_session.add(waiting)
    db_session.flush()
    apply_decision(
        db_session,
        suggestion,
        {"action": "map", "category_id": str(other.id)},
        decided_by="admin",
    )
    db_session.refresh(sample_activity)
    db_session.refresh(waiting)
    assert str(sample_activity.category_id) == str(other.id)
    assert waiting.status == "applied"


def test_pending_review_is_an_org_review_warning(
    db_session, sample_organization, sample_activity
) -> None:
    run = _run(db_session, status="done", batches_total=0)
    db_session.add(
        ActivityCategoryReview(
            scan_run_id=run.id,
            activity_id=sample_activity.id,
            org_id=sample_organization.id,
            verdict="reassign",
            status="pending",
        )
    )
    db_session.flush()
    listed = db_session.execute(
        _query(
            status="pending",
            verdict=None,
            org_id=None,
            scan_run_id=None,
            proposed_category_id=None,
            query_text="",
            cursor=None,
        )
    ).one()
    payload = _serialize(db_session, *listed)
    assert payload["activity_name"] == sample_activity.name
    assert payload["verdict"] == "reassign"
    snapshot = load_snapshots(db_session, [sample_organization])[0]
    assert "category_check_pending" in {issue.code for issue in snapshot.issues}
    assert "category_check_pending" not in BLOCKER_ISSUE_CODES
    assert issue_clause("category_check_pending") is not None


def test_scan_route_enqueues_after_commit(monkeypatch, test_engine) -> None:
    monkeypatch.setattr("app.api.admin_category_scan.get_engine", lambda: test_engine)
    monkeypatch.setattr(
        "app.api.admin_category_scan._set_session_audit_context",
        lambda *_args, **_kwargs: None,
    )
    sent: list[tuple] = []
    monkeypatch.setattr(
        "app.api.admin_category_scan.enqueue_scan_batches",
        lambda run_id, batches: sent.append((run_id, batches)),
    )
    org_id = uuid4()
    activity_id = uuid4()
    category_id = uuid4()
    with Session(test_engine) as session:
        session.add(
            ActivityCategory(id=category_id, name="Route Sport", display_order=0)
        )
        session.add(
            Organization(
                id=org_id,
                name="Route Org",
                manager_id="00000000-0000-0000-0000-000000000009",
                review_status="pending_review",
            )
        )
        session.add(
            Activity(
                id=activity_id,
                org_id=org_id,
                category_id=category_id,
                name="Route class",
                age_range=Range(5, 12, bounds="[]"),
            )
        )
        session.commit()
    body: dict | None = None
    try:
        response = lambda_handler(
            {
                "httpMethod": "POST",
                "path": "/v1/admin/category-suggestions/scan",
                "body": json.dumps({"org_id": str(org_id)}),
                "headers": {"Content-Type": "application/json"},
                "requestContext": {
                    "authorizer": {"groups": "admin", "userSub": "admin"}
                },
            },
            None,
        )
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["total_activities"] == 1
        assert sent and sent[0][1] == [[str(activity_id)]]
    finally:
        with Session(test_engine) as session:
            if body is not None:
                run = session.get(CategoryScanRun, body["id"])
                if run is not None:
                    session.delete(run)
            for model, row_id in (
                (Activity, activity_id),
                (Organization, org_id),
                (ActivityCategory, category_id),
            ):
                row = session.get(model, row_id)
                if row is not None:
                    session.delete(row)
            session.commit()
