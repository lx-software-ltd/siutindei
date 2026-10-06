"""Follow-up guards for recheck proposals, bulk review, and search."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import UUID
from uuid import uuid4

from psycopg.types.range import Range
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import LEGACY_CATEGORY_IDS, WIZARD_GROUP_IDS
from app.db.queries import _category_descendant_ids_subquery
from app.db.queries import category_match_mode
from app.services.category_suggestions import reviews as review_service
from app.services.category_suggestions.prompt import build_scan_prompt
from app.services.category_suggestions.scan import select_candidate_ids, start_scan
from app.services.category_suggestions.scan_apply import store_scan_batch
from tests.test_category_scan import _result, _run


def test_recheck_propose_does_not_assign_a_legacy_root(
    db_session, sample_activity
) -> None:
    legacy_id = next(iter(LEGACY_CATEGORY_IDS))
    legacy = db_session.get(ActivityCategory, legacy_id)
    if legacy is None:
        legacy = ActivityCategory(
            id=legacy_id,
            name=f"Legacy {legacy_id.hex[:8]}",
            display_order=0,
        )
        db_session.add(legacy)
        db_session.flush()
    before = sample_activity.category_id
    run = _run(db_session, ignore_current_category=True)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="propose",
                    confidence=0.99,
                    propose={"name_en": legacy.name, "name_zh": "舊"},
                )
            ]
        },
        {},
    )
    db_session.refresh(run)
    db_session.refresh(sample_activity)
    assert int(run.failed) == 1
    assert sample_activity.category_id == before
    assert list(db_session.scalars(select(ActivityCategoryReview)).all()) == []


def test_recheck_propose_does_not_assign_a_parent_group(
    db_session, sample_activity
) -> None:
    parent = ActivityCategory(name=f"Parent {uuid4().hex[:8]}", display_order=8)
    db_session.add(parent)
    db_session.flush()
    db_session.add(
        ActivityCategory(
            name=f"Leaf {uuid4().hex[:8]}",
            display_order=1,
            parent_id=parent.id,
        )
    )
    db_session.flush()
    before = sample_activity.category_id
    run = _run(db_session, ignore_current_category=True)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="propose",
                    confidence=0.99,
                    propose={"name_en": parent.name},
                )
            ]
        },
        {},
    )
    db_session.refresh(run)
    db_session.refresh(sample_activity)
    assert int(run.failed) == 1
    assert sample_activity.category_id == before


def test_recheck_omits_an_unknown_description_and_keeps_official(
    db_session, sample_activity, sample_organization
) -> None:
    sample_activity.description = "Generated catalogue copy"
    sample_organization.description_source = None
    db_session.flush()
    _system, user = build_scan_prompt(
        db_session,
        [sample_activity],
        ignore_current_category=True,
    )
    item = json.loads(user)["activities"][0]
    assert item["description"] == ""
    assert item["description_is_template"] is True

    sample_organization.description_source = "official"
    db_session.flush()
    _system, user = build_scan_prompt(
        db_session,
        [sample_activity],
        ignore_current_category=True,
    )
    item = json.loads(user)["activities"][0]
    assert item["description"] == "Generated catalogue copy"
    assert item["description_is_template"] is False


def test_recheck_includes_a_recently_checked_activity(
    db_session, sample_activity, sample_organization
) -> None:
    settled = _run(db_session, status="done", batches_total=0)
    db_session.add(
        ActivityCategoryReview(
            scan_run_id=settled.id,
            activity_id=sample_activity.id,
            org_id=sample_organization.id,
            verdict="confirm",
            status="confirmed",
        )
    )
    db_session.flush()
    assert select_candidate_ids(db_session, org_id=sample_organization.id) == []
    _started, batches = start_scan(
        db_session,
        {
            "org_id": str(sample_organization.id),
            "ignore_current_category": True,
            "rescan": False,
        },
        requested_by="admin",
    )
    assert batches == [[str(sample_activity.id)]]


def test_bulk_apply_advances_past_a_skipped_review(
    db_session,
    sample_activity,
    sample_organization,
    sample_activity_category,
    monkeypatch,
) -> None:
    monkeypatch.setattr(review_service, "BULK_PAGE_SIZE", 1)
    other = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Second class",
        age_range=Range(6, 10, bounds="[]"),
    )
    db_session.add(other)
    db_session.flush()
    run = _run(db_session)
    newer = datetime.now(timezone.utc)
    older = newer - timedelta(minutes=5)
    db_session.add(
        ActivityCategoryReview(
            scan_run_id=run.id,
            activity_id=sample_activity.id,
            org_id=sample_organization.id,
            verdict="propose",
            status="pending",
            created_at=newer,
        )
    )
    applicable = ActivityCategoryReview(
        scan_run_id=run.id,
        activity_id=other.id,
        org_id=sample_organization.id,
        verdict="reassign",
        status="pending",
        proposed_category_id=sample_activity_category.id,
        created_at=older,
    )
    db_session.add(applicable)
    db_session.flush()
    first = review_service.decide_matching_reviews(
        db_session,
        {"action": "apply"},
        decided_by="admin",
        cursor=None,
    )
    assert first["skipped"] == 1
    assert first["decided"] == 0
    assert first["next_review"] is not None
    cursor = (first["next_review"].created_at, first["next_review"].id)
    second = review_service.decide_matching_reviews(
        db_session,
        {"action": "apply"},
        decided_by="admin",
        cursor=cursor,
    )
    assert second["decided"] == 1
    assert second["next_review"] is None
    db_session.refresh(other)
    assert other.category_id == sample_activity_category.id


def test_empty_wizard_group_search_includes_legacy_roots(
    db_session, sample_activity
) -> None:
    sport_id = UUID("99999999-9999-9999-9999-999999999999")
    if db_session.get(ActivityCategory, sport_id) is None:
        db_session.add(ActivityCategory(id=sport_id, name="Sport", display_order=1))
        db_session.flush()
    group_id = _first_empty_wizard_group(db_session)
    if db_session.get(ActivityCategory, group_id) is None:
        db_session.add(
            ActivityCategory(
                id=group_id,
                name=f"Wizard {group_id.hex[:8]}",
                display_order=10,
            )
        )
        db_session.flush()
    found = set(db_session.scalars(_category_descendant_ids_subquery([group_id])).all())
    assert sport_id in found
    assert category_match_mode(db_session, [group_id]) == "legacy_fallback"
    leaf = ActivityCategory(
        name=f"Sorted {uuid4().hex[:8]}",
        display_order=1,
        parent_id=group_id,
    )
    db_session.add(leaf)
    db_session.flush()
    sample_activity.category_id = leaf.id
    db_session.flush()
    assert category_match_mode(db_session, [group_id]) == "exact"
    found = set(db_session.scalars(_category_descendant_ids_subquery([group_id])).all())
    assert sport_id not in found


def _first_empty_wizard_group(session: Session) -> UUID:
    for group_id in sorted(WIZARD_GROUP_IDS, key=str):
        if category_match_mode(session, [group_id]) == "legacy_fallback":
            return group_id
    raise AssertionError("expected an empty wizard group")
