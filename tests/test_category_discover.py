"""Discovery groups imported labels that are not already categories."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ActivityCategory
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import (
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.db.repositories.activity_category import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.category_suggestions.decisions import apply_decision
from app.services.category_suggestions.resolve import normalize_category_key
from app.services.category_suggestions.scan import start_scan
from app.services.category_suggestions.scan_discover_batch import (
    process_discover_batch,
    store_discover_batch,
)
from app.services.openrouter_client import OpenRouterError


def test_known_label_is_assigned_without_a_model_call(
    db_session, sample_activity, sample_activity_category
) -> None:
    other = ActivityCategory(name="Holding category", display_order=4)
    db_session.add(other)
    db_session.flush()
    sample_activity.category_id = other.id
    sample_activity.source_category_name = sample_activity_category.name
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    db_session.refresh(sample_activity)
    db_session.refresh(run)
    assert batches == []
    assert run.mode == "discover"
    assert run.status == "done"
    assert str(sample_activity.category_id) == str(sample_activity_category.id)
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.status == "auto_applied"
    assert review.decided_by == f"category-scan:{run.id}"


def test_unknown_label_stays_whole_and_is_queued(db_session, sample_activity) -> None:
    sample_activity.source_category_name = "Art, Music"
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    assert run.labels_total == 1
    assert len(batches) == 1
    suggestion = db_session.scalars(select(CategorySuggestion)).one()
    assert suggestion.requested_name == "Art, Music"
    assert suggestion.source == "scan"
    assert suggestion.fingerprint == normalize_category_key("Art, Music")
    assert batches == [[str(suggestion.id)]]
    links = db_session.scalars(select(CategorySuggestionActivity)).all()
    assert len(links) == 1


def test_rejected_label_reopens_and_is_not_auto_mapped(
    db_session, sample_activity, sample_activity_category
) -> None:
    sample_activity.source_category_name = "Wheel throwing"
    fingerprint = normalize_category_key("Wheel throwing")
    suggestion = CategorySuggestion(
        fingerprint=fingerprint,
        requested_name="Wheel throwing",
        source="import",
        status="rejected",
        enrichment_status="done",
    )
    db_session.add(suggestion)
    db_session.flush()
    _run, batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    db_session.refresh(suggestion)
    assert suggestion.status == "pending"
    assert suggestion.reopened_at is not None
    assert suggestion.source == "import"
    assert batches == [[str(suggestion.id)]]
    other = ActivityCategory(name="Clay studio", display_order=8)
    db_session.add(other)
    db_session.flush()
    store_discover_batch(
        db_session,
        _run.id,
        batches[0],
        {
            "results": [
                {
                    "suggestion_id": str(suggestion.id),
                    "maps_to_existing": {
                        "category_id": str(other.id),
                        "confidence": 0.99,
                    },
                    "confidence": 0.99,
                    "rationale": "Close",
                }
            ]
        },
        {"cost_usd": 0.01},
        "reopen-1",
    )
    db_session.refresh(sample_activity)
    db_session.refresh(suggestion)
    assert str(sample_activity.category_id) == str(sample_activity_category.id)
    assert suggestion.status == "pending"


def test_second_discover_does_not_duplicate_the_link(
    db_session, sample_activity
) -> None:
    sample_activity.source_category_name = "Printmaking"
    db_session.flush()
    run, _batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    run.status = "done"
    db_session.flush()
    start_scan(db_session, {"mode": "discover"}, requested_by="admin")
    count = db_session.scalar(
        select(func.count()).select_from(CategorySuggestionActivity)
    )
    assert count == 1


def test_auto_maps_a_confident_existing_category(
    db_session, sample_activity, sample_activity_category
) -> None:
    sample_activity.source_category_name = "Studio pottery"
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    target = ActivityCategory(name="Pottery studio", display_order=6)
    db_session.add(target)
    db_session.flush()
    store_discover_batch(
        db_session,
        run.id,
        batches[0],
        {
            "results": [
                {
                    "suggestion_id": batches[0][0],
                    "maps_to_existing": {
                        "category_id": str(target.id),
                        "confidence": 0.95,
                    },
                    "confidence": 0.95,
                    "rationale": "Same craft",
                }
            ]
        },
        {"cost_usd": 0.02},
        "map-1",
    )
    db_session.refresh(sample_activity)
    suggestion = db_session.get(CategorySuggestion, batches[0][0])
    assert suggestion is not None
    assert suggestion.status == "merged"
    assert str(sample_activity.category_id) == str(target.id)
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.status == "auto_applied"
    assert str(review.previous_category_id) == str(sample_activity_category.id)


def test_low_confidence_map_stays_pending(db_session, sample_activity) -> None:
    original = sample_activity.category_id
    sample_activity.source_category_name = "Orchestra"
    db_session.flush()
    run, batches = start_scan(
        db_session,
        {"mode": "discover"},
        requested_by="admin",
    )
    target = ActivityCategory(name="Music", display_order=7)
    db_session.add(target)
    db_session.flush()
    store_discover_batch(
        db_session,
        run.id,
        batches[0],
        {
            "results": [
                {
                    "suggestion_id": batches[0][0],
                    "maps_to_existing": {
                        "category_id": str(target.id),
                        "confidence": 0.4,
                    },
                    "confidence": 0.4,
                    "rationale": "Maybe",
                }
            ]
        },
        {},
        "low-1",
    )
    db_session.refresh(sample_activity)
    suggestion = db_session.get(CategorySuggestion, batches[0][0])
    assert str(sample_activity.category_id) == str(original)
    assert suggestion is not None
    assert suggestion.status == "pending"


def test_discover_refuses_when_the_month_budget_is_used(
    db_session, sample_activity
) -> None:
    sample_activity.source_category_name = "Budget label"
    db_session.add(
        CategoryScanRun(
            status="done",
            batch_size=10,
            cost_usd=Decimal("30"),
        )
    )
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        start_scan(db_session, {"mode": "discover"}, requested_by="admin")
    assert exc_info.value.field == "monthly_cost_limit_usd"


def test_worker_retries_then_records_the_third_failure(
    monkeypatch, test_engine
) -> None:
    monkeypatch.setattr(
        "app.services.category_suggestions.scan_discover_batch.get_engine",
        lambda: test_engine,
    )

    def fail(**_kwargs: object) -> str:
        raise OpenRouterError("down")

    monkeypatch.setattr(
        "app.services.category_suggestions.scan_discover_batch.openrouter_chat_completion",
        fail,
    )
    org_id = uuid4()
    category_id = uuid4()
    activity_id = uuid4()
    run_id = uuid4()
    suggestion_id = uuid4()
    from psycopg.types.range import Range
    from app.db.models import Activity, Organization

    with Session(test_engine) as session:
        session.add(
            ActivityCategory(
                id=category_id,
                name=f"Discover {category_id.hex[:8]}",
                display_order=0,
            )
        )
        session.add(
            Organization(
                id=org_id,
                name=f"Discover org {org_id.hex[:8]}",
                manager_id="00000000-0000-0000-0000-000000000019",
                review_status="pending_review",
            )
        )
        session.add(
            Activity(
                id=activity_id,
                org_id=org_id,
                category_id=category_id,
                name="Discover class",
                age_range=Range(5, 12, bounds="[]"),
                source_category_name="Unknown craft",
            )
        )
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint=normalize_category_key("Unknown craft"),
                requested_name="Unknown craft",
                source="scan",
                status="pending",
                enrichment_status="none",
            )
        )
        session.add(
            CategoryScanRun(
                id=run_id,
                status="queued",
                mode="discover",
                batch_size=10,
                batches_total=1,
                labels_total=1,
                total_activities=1,
            )
        )
        session.commit()
    try:
        with pytest.raises(OpenRouterError):
            process_discover_batch(
                run_id,
                [str(suggestion_id)],
                message_id="discover-1",
                receive_count=1,
            )
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, run_id)
            assert run is not None
            assert run.status == "queued"
        with pytest.raises(OpenRouterError):
            process_discover_batch(
                run_id,
                [str(suggestion_id)],
                message_id="discover-3",
                receive_count=3,
            )
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error == "down"
    finally:
        from sqlalchemy import delete

        from app.db.models import Activity, Organization

        with Session(test_engine) as session:
            session.execute(
                delete(ActivityCategoryReview).where(
                    ActivityCategoryReview.scan_run_id == run_id
                )
            )
            session.execute(delete(CategoryScanRun).where(CategoryScanRun.id == run_id))
            session.execute(
                delete(CategorySuggestionActivity).where(
                    CategorySuggestionActivity.suggestion_id == suggestion_id
                )
            )
            session.execute(
                delete(CategorySuggestion).where(CategorySuggestion.id == suggestion_id)
            )
            activity = session.get(Activity, activity_id)
            if activity is not None:
                session.delete(activity)
            org = session.get(Organization, org_id)
            if org is not None:
                session.delete(org)
            category = session.get(ActivityCategory, category_id)
            if category is not None:
                session.delete(category)
            session.commit()


def test_wizard_category_cannot_be_deleted(db_session) -> None:
    category = ActivityCategory(
        name="Wizard ceramics",
        display_order=3,
        show_in_wizard=True,
    )
    db_session.add(category)
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        ActivityCategoryRepository(db_session).delete(category)
    assert exc_info.value.field == "show_in_wizard"


def test_approve_copies_zh_into_zh_hk(db_session) -> None:
    suggestion = CategorySuggestion(
        fingerprint=normalize_category_key("Lantern making"),
        requested_name="Lantern making",
        source="scan",
        status="pending",
        suggested_name="Lantern making",
        name_translations={"zh": "燈籠"},
        enrichment_status="done",
    )
    db_session.add(suggestion)
    db_session.flush()
    apply_decision(
        db_session,
        suggestion,
        {"action": "approve"},
        decided_by="admin",
    )
    created = db_session.get(ActivityCategory, suggestion.created_category_id)
    assert created is not None
    assert created.name_translations["zh"] == "燈籠"
    assert created.name_translations["zh-HK"] == "燈籠"
