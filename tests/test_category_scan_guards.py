"""Guards for category-check budget, retries, and review decisions."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.types.range import Range
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.exceptions import ValidationError
from app.services.category_suggestions.prompt import build_scan_prompt
from app.services.category_suggestions.reviews import apply_review_decision
from app.services.category_suggestions.scan import (
    CategoryScanBusy,
    count_candidates,
    process_scan_batch,
    select_candidate_ids,
    start_scan,
    summary_counts,
)
from app.services.category_suggestions.scan_apply import store_scan_batch
from app.services.category_suggestions.settings import (
    apply_settings_update,
    get_settings,
)
from app.services.openrouter_client import OpenRouterError
from tests.test_category_scan import _result, _run

_WORKER = None


def _worker():
    global _WORKER
    if _WORKER is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "backend/lambda/category_suggestions/handler.py"
        )
        spec = importlib.util.spec_from_file_location(
            "category_suggestion_sqs_handler",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        _WORKER = module
    return _WORKER


def _scan_event(message_id: str, receive: str) -> dict:
    body = {
        "scan_run_id": str(uuid4()),
        "activity_ids": [str(uuid4())],
    }
    return {
        "Records": [
            {
                "messageId": message_id,
                "body": json.dumps(body),
                "attributes": {"ApproximateReceiveCount": receive},
            }
        ]
    }


class _Seed:
    """Committed rows a worker session can see. Removed on exit."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.org_id = uuid4()
        self.category_id = uuid4()
        self.activity_id = uuid4()
        self.run_id = uuid4()

    def __enter__(self) -> _Seed:
        with Session(self.engine) as session:
            session.add(
                ActivityCategory(
                    id=self.category_id,
                    name=f"Guard {self.category_id.hex[:8]}",
                    display_order=0,
                )
            )
            session.add(
                Organization(
                    id=self.org_id,
                    name=f"Guard org {self.org_id.hex[:8]}",
                    manager_id="00000000-0000-0000-0000-000000000019",
                    review_status="pending_review",
                )
            )
            session.add(
                Activity(
                    id=self.activity_id,
                    org_id=self.org_id,
                    category_id=self.category_id,
                    name="Guard class",
                    age_range=Range(5, 12, bounds="[]"),
                )
            )
            session.flush()
            session.add(
                CategoryScanRun(
                    id=self.run_id,
                    status="queued",
                    org_id=self.org_id,
                    batch_size=10,
                    batches_total=1,
                    total_activities=1,
                )
            )
            session.commit()
        return self

    def spend(self, amount: str) -> None:
        with Session(self.engine) as session:
            session.add(
                CategoryScanRun(
                    status="done",
                    org_id=self.org_id,
                    batch_size=10,
                    batches_total=0,
                    cost_usd=Decimal(amount),
                )
            )
            session.commit()

    def __exit__(self, *_args) -> None:
        with Session(self.engine) as session:
            session.execute(
                delete(ActivityCategoryReview).where(
                    ActivityCategoryReview.org_id == self.org_id
                )
            )
            session.execute(
                delete(CategoryScanRun).where(CategoryScanRun.org_id == self.org_id)
            )
            activity = session.get(Activity, self.activity_id)
            if activity is not None:
                session.delete(activity)
            org = session.get(Organization, self.org_id)
            if org is not None:
                session.delete(org)
            category = session.get(ActivityCategory, self.category_id)
            if category is not None:
                session.delete(category)
            session.commit()


def _completion(activity_id) -> str:
    content = json.dumps(
        {
            "results": [
                {
                    "activity_id": str(activity_id),
                    "verdict": "confirm",
                    "confidence": 0.95,
                    "rationale": "Fits",
                }
            ]
        }
    )
    return json.dumps(
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"cost": 0.02},
        }
    )


def test_reassign_to_the_current_category_confirms(
    db_session, sample_activity, sample_activity_category
) -> None:
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
                    category_id=str(sample_activity.category_id),
                    confidence=0.99,
                )
            ]
        },
        {},
    )
    db_session.refresh(sample_activity)
    db_session.refresh(run)
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.verdict == "confirm"
    assert review.status == "confirmed"
    assert run.confirmed == 1
    assert run.auto_applied == 0
    assert str(sample_activity.category_id) == str(sample_activity_category.id)


def test_open_review_is_skipped_even_when_rescanning(
    db_session, sample_activity, sample_organization
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
    org_id = sample_organization.id
    assert select_candidate_ids(db_session, org_id=org_id, rescan=True) == []
    assert count_candidates(db_session, org_id=org_id, rescan=True) == 0


def test_candidate_count_is_not_capped_at_the_scan_limit(
    db_session, sample_activity, sample_organization, sample_activity_category
) -> None:
    db_session.add(
        Activity(
            org_id=sample_organization.id,
            category_id=sample_activity_category.id,
            name="Second guard class",
            age_range=Range(6, 9, bounds="[]"),
        )
    )
    db_session.flush()
    org_id = sample_organization.id
    assert count_candidates(db_session, org_id=org_id) == 2
    assert len(select_candidate_ids(db_session, org_id=org_id, limit=1)) == 1
    counts = summary_counts(db_session, org_id=org_id)
    assert counts["scan_candidate_total"] == 2
    assert counts["scan_limit"] == 500


def test_summary_fails_a_stale_run(db_session, sample_activity) -> None:
    stale_at = datetime.now(timezone.utc) - timedelta(seconds=661)
    run = _run(db_session, status="running", updated_at=stale_at)
    counts = summary_counts(db_session, org_id=sample_activity.org_id)
    db_session.refresh(run)
    assert run.status == "failed"
    assert run.error == "No batch completed before the scan went stale"
    assert counts["active_scan_run"] is None


def test_summary_keeps_a_live_run(db_session, sample_activity) -> None:
    run = _run(db_session, status="queued")
    counts = summary_counts(db_session, org_id=sample_activity.org_id)
    assert counts["active_scan_run"]["id"] == str(run.id)
    assert counts["active_scan_run"]["status"] == "queued"


def test_start_scan_rejects_a_used_monthly_budget(db_session, sample_activity) -> None:
    settings = get_settings(db_session)
    settings.monthly_cost_limit_usd = Decimal("1.00")
    _run(
        db_session,
        status="done",
        batches_total=0,
        total_activities=0,
        cost_usd=Decimal("1.00"),
    )
    with pytest.raises(ValidationError) as caught:
        start_scan(
            db_session,
            {"org_id": str(sample_activity.org_id)},
            requested_by="admin",
        )
    assert caught.value.field == "monthly_cost_limit_usd"


def test_cost_limit_rejects_zero_and_stores_a_valid_amount(db_session) -> None:
    with pytest.raises(ValidationError) as caught:
        apply_settings_update(
            db_session,
            {"monthly_cost_limit_usd": 0},
            updated_by="admin",
        )
    assert caught.value.field == "monthly_cost_limit_usd"
    row = apply_settings_update(
        db_session,
        {"monthly_cost_limit_usd": 40},
        updated_by="admin",
    )
    assert float(row.monthly_cost_limit_usd) == 40.0


def test_one_active_run_index(db_session) -> None:
    _run(db_session, status="queued")
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(CategoryScanRun(status="running", batch_size=10))
            db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(CategoryScanRun)) == 1


def test_start_scan_maps_integrity_error_to_busy(test_engine) -> None:
    with _Seed(test_engine) as seeded:
        with Session(test_engine) as session:
            real_scalar = session.scalar

            def hide_active(statement, *args, **kwargs):
                sql = str(statement)
                if "category_scan_runs.id" in sql and "LIMIT" in sql.upper():
                    return None
                return real_scalar(statement, *args, **kwargs)

            session.scalar = hide_active  # type: ignore[method-assign]
            with pytest.raises(CategoryScanBusy) as caught:
                start_scan(
                    session,
                    {"org_id": str(seeded.org_id)},
                    requested_by="admin",
                )
            assert isinstance(caught.value.__cause__, IntegrityError)


def test_scan_prompt_includes_inclusive_ages(db_session, sample_activity) -> None:
    _system, user = build_scan_prompt(db_session, [sample_activity])
    item = json.loads(user)["activities"][0]
    assert item["age_min"] == 5
    assert item["age_max"] == 12
    assert "rationale" in _system


def test_apply_dismiss_and_revert_guards(
    db_session, sample_activity, sample_organization, sample_activity_category
) -> None:
    other = ActivityCategory(name="Explicit Target", display_order=8)
    db_session.add(other)
    db_session.flush()
    run = _run(db_session, status="done", batches_total=0)
    propose = ActivityCategoryReview(
        scan_run_id=run.id,
        activity_id=sample_activity.id,
        org_id=sample_organization.id,
        current_category_id=sample_activity_category.id,
        verdict="propose",
        status="pending",
    )
    db_session.add(propose)
    db_session.flush()
    apply_review_decision(
        db_session,
        propose,
        {"action": "apply", "category_id": str(other.id)},
        decided_by="admin",
    )
    db_session.refresh(sample_activity)
    assert propose.status == "applied"
    assert str(sample_activity.category_id) == str(other.id)

    sample_activity.category_id = sample_activity_category.id
    sibling = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Dismiss class",
        age_range=Range(4, 7, bounds="[]"),
    )
    db_session.add(sibling)
    db_session.flush()
    dismiss = ActivityCategoryReview(
        scan_run_id=run.id,
        activity_id=sibling.id,
        org_id=sample_organization.id,
        verdict="propose",
        status="pending",
    )
    db_session.add(dismiss)
    db_session.flush()
    apply_review_decision(
        db_session, dismiss, {"action": "dismiss"}, decided_by="admin"
    )
    assert dismiss.status == "dismissed"
    with pytest.raises(ValidationError, match="Only an applied"):
        apply_review_decision(
            db_session, dismiss, {"action": "revert"}, decided_by="admin"
        )


def test_confirm_of_pending_category_requires_a_target(
    db_session, sample_activity, sample_organization
) -> None:
    from app.services.category_suggestions.capture import ensure_pending_category

    ensure_pending_category(db_session)
    sample_activity.category_id = PENDING_CATEGORY_ID
    run = _run(db_session, status="done", batches_total=0)
    review = ActivityCategoryReview(
        scan_run_id=run.id,
        activity_id=sample_activity.id,
        org_id=sample_organization.id,
        current_category_id=PENDING_CATEGORY_ID,
        verdict="confirm",
        status="pending",
    )
    db_session.add(review)
    db_session.flush()
    with pytest.raises(ValidationError, match="category_id is required"):
        apply_review_decision(
            db_session, review, {"action": "apply"}, decided_by="admin"
        )


def test_process_scan_batch_confirms_and_ignores_a_repeat(
    monkeypatch, test_engine
) -> None:
    monkeypatch.setattr(
        "app.services.category_suggestions.scan.get_engine",
        lambda: test_engine,
    )
    calls = {"n": 0}
    with _Seed(test_engine) as seeded:

        def complete_seeded(**_kwargs: object) -> str:
            calls["n"] += 1
            return _completion(seeded.activity_id)

        monkeypatch.setattr(
            "app.services.category_suggestions.scan.openrouter_chat_completion",
            complete_seeded,
        )
        assert process_scan_batch(
            seeded.run_id,
            [str(seeded.activity_id)],
            message_id="msg-1",
        )
        assert process_scan_batch(
            seeded.run_id,
            [str(seeded.activity_id)],
            message_id="msg-1",
        )
        assert calls["n"] == 1
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, seeded.run_id)
            review = session.scalars(
                select(ActivityCategoryReview).where(
                    ActivityCategoryReview.scan_run_id == seeded.run_id
                )
            ).one()
            assert run is not None
            assert run.status == "done"
            assert float(run.cost_usd) == 0.02
            assert review.status == "confirmed"


def test_process_scan_batch_retries_then_records_the_third_failure(
    monkeypatch, test_engine
) -> None:
    monkeypatch.setattr(
        "app.services.category_suggestions.scan.get_engine",
        lambda: test_engine,
    )

    def fail(**_kwargs: object) -> str:
        raise OpenRouterError("down")

    monkeypatch.setattr(
        "app.services.category_suggestions.scan.openrouter_chat_completion",
        fail,
    )
    with _Seed(test_engine) as seeded:
        with pytest.raises(OpenRouterError):
            process_scan_batch(
                seeded.run_id,
                [str(seeded.activity_id)],
                message_id="retry-1",
                receive_count=1,
            )
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, seeded.run_id)
            assert run is not None
            assert run.status == "queued"
        with pytest.raises(OpenRouterError):
            process_scan_batch(
                seeded.run_id,
                [str(seeded.activity_id)],
                message_id="retry-3",
                receive_count=3,
            )
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, seeded.run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error == "down"


def test_process_scan_batch_acks_other_errors(monkeypatch, test_engine) -> None:
    monkeypatch.setattr(
        "app.services.category_suggestions.scan.get_engine",
        lambda: test_engine,
    )

    def fail(**_kwargs: object) -> str:
        raise RuntimeError("bad payload")

    monkeypatch.setattr(
        "app.services.category_suggestions.scan.openrouter_chat_completion",
        fail,
    )
    with _Seed(test_engine) as seeded:
        assert (
            process_scan_batch(
                seeded.run_id,
                [str(seeded.activity_id)],
                message_id="bad-1",
            )
            is True
        )
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, seeded.run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error == "bad payload"


def test_worker_fails_the_run_when_the_month_budget_is_used(
    monkeypatch, test_engine
) -> None:
    monkeypatch.setattr(
        "app.services.category_suggestions.scan.get_engine",
        lambda: test_engine,
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services.category_suggestions.scan.openrouter_chat_completion",
        lambda **_kwargs: calls.append("called"),
    )
    with _Seed(test_engine) as seeded:
        seeded.spend("60")
        assert (
            process_scan_batch(
                seeded.run_id,
                [str(seeded.activity_id)],
                message_id="budget-1",
            )
            is True
        )
        assert calls == []
        with Session(test_engine) as session:
            run = session.get(CategoryScanRun, seeded.run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error == "Monthly category-check budget is used"


def test_scan_handler_reports_retries_and_acks_finished_work(
    monkeypatch, capsys
) -> None:
    worker = _worker()

    def fail(*_args, **_kwargs):
        raise OpenRouterError("down")

    monkeypatch.setattr(worker, "process_scan_batch", fail)
    retried = worker.lambda_handler(_scan_event("m-1", "1"), None)
    assert retried["batchItemFailures"] == [{"itemIdentifier": "m-1"}]

    monkeypatch.setattr(worker, "process_scan_batch", lambda *_a, **_k: True)
    stored = worker.lambda_handler(_scan_event("m-2", "2"), None)
    assert stored["batchItemFailures"] == []
    assert "Category check batch finished" in capsys.readouterr().out

    missing = worker.lambda_handler(
        {
            "Records": [
                {
                    "messageId": "m-3",
                    "body": json.dumps({"scan_run_id": str(uuid4())}),
                }
            ]
        },
        None,
    )
    assert missing["batchItemFailures"] == []


def test_recheck_prompt_omits_the_current_category(
    db_session, sample_activity, sample_organization
) -> None:
    sample_organization.description_source = "template"
    sample_organization.source = "edb"
    sample_organization.source_url = "https://www.edb.gov.hk/en/page"
    parent = ActivityCategory(name="Recheck Parent", display_order=3)
    db_session.add(parent)
    db_session.flush()
    leaf = ActivityCategory(
        name="Recheck Leaf",
        display_order=1,
        parent_id=parent.id,
    )
    db_session.add(leaf)
    db_session.flush()
    system, user = build_scan_prompt(
        db_session,
        [sample_activity],
        ignore_current_category=True,
    )
    item = json.loads(user)["activities"][0]
    taxonomy = {row["id"] for row in json.loads(user)["taxonomy"]}
    assert "current_category" not in item
    assert item["description"] == ""
    assert item["description_is_template"] is True
    assert item["organization_source"] == "edb"
    assert item["source_url_host"] == "edb.gov.hk"
    assert str(parent.id) not in taxonomy
    assert str(leaf.id) in taxonomy
    assert "Do not reply confirm" in system


def test_recheck_confirm_counts_as_failed(db_session, sample_activity) -> None:
    run = _run(db_session, ignore_current_category=True)
    store_scan_batch(
        db_session,
        run.id,
        [str(sample_activity.id)],
        {"results": [_result(sample_activity, verdict="confirm", confidence=0.99)]},
        {},
    )
    db_session.refresh(run)
    assert int(run.failed) == 1
    assert list(db_session.scalars(select(ActivityCategoryReview)).all()) == []


def test_recheck_rejects_a_parent_and_assigns_a_leaf(
    db_session, sample_activity, sample_activity_category
) -> None:
    leaf = ActivityCategory(
        name="Child Leaf",
        display_order=1,
        parent_id=sample_activity_category.id,
    )
    db_session.add(leaf)
    db_session.flush()
    parent_run = _run(db_session, ignore_current_category=True)
    store_scan_batch(
        db_session,
        parent_run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(sample_activity_category.id),
                    confidence=0.99,
                )
            ]
        },
        {},
    )
    db_session.refresh(parent_run)
    db_session.refresh(sample_activity)
    assert int(parent_run.failed) == 1
    assert sample_activity.category_id == sample_activity_category.id

    leaf_run = _run(db_session, ignore_current_category=True)
    store_scan_batch(
        db_session,
        leaf_run.id,
        [str(sample_activity.id)],
        {
            "results": [
                _result(
                    sample_activity,
                    verdict="reassign",
                    category_id=str(leaf.id),
                    confidence=0.99,
                )
            ]
        },
        {},
        message_id="leaf-batch",
    )
    db_session.refresh(sample_activity)
    review = db_session.scalars(select(ActivityCategoryReview)).one()
    assert review.status == "auto_applied"
    assert sample_activity.category_id == leaf.id


def test_discover_rejects_ignore_current(db_session, sample_organization) -> None:
    with pytest.raises(ValidationError) as caught:
        start_scan(
            db_session,
            {
                "mode": "discover",
                "ignore_current_category": True,
                "org_id": str(sample_organization.id),
            },
            requested_by="admin",
        )
    assert caught.value.field == "ignore_current_category"
