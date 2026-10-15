"""Translation sweeps, model proposals, and apply."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.models import (
    Activity,
    Organization,
    TranslationFixProposal,
    TranslationScanRun,
)
from app.exceptions import ValidationError
from app.services.translation_fix_model import store_model_items
from app.services.translation_fix_query import load_settings
from app.services.translation_fix_scan import start_translation_scan
from app.services.translation_fixes import decide_proposal
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"
_WORKER = None


def _worker():
    global _WORKER
    if _WORKER is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "backend/lambda/category_suggestions/handler.py"
        )
        spec = importlib.util.spec_from_file_location(
            "category_suggestion_sqs_handler_translations",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        _WORKER = module
    return _WORKER


def _org(
    db_session,
    name: str,
    *,
    review_status: str = "pending_review",
    description: str | None = None,
    name_translations: dict | None = None,
    description_translations: dict | None = None,
) -> Organization:
    org = Organization(
        name=name,
        manager_id=_MANAGER,
        review_status=review_status,
        description=description,
        name_translations=name_translations or {},
        description_translations=description_translations or {},
    )
    db_session.add(org)
    db_session.flush()
    return org


def _activity(db_session, org, category, name: str) -> Activity:
    activity = Activity(
        org_id=org.id,
        category_id=category.id,
        name=name,
        description="Saturday class",
        age_range=Range(5, 12, bounds="[]"),
        name_translations={},
        description_translations={"zh": "星期六班", "zh-HK": "星期六班"},
    )
    db_session.add(activity)
    db_session.flush()
    return activity


def test_pending_sweep_queues_a_missing_language_and_skips_approved(
    db_session,
) -> None:
    pending = _org(db_session, "Harbour Club")
    _org(db_session, "Approved Club", review_status="approved")
    result, batches = start_translation_scan(
        db_session,
        review_scope="pending_review",
        budget_seconds=None,
    )
    assert result["queued_for_model"] == 1
    assert result["status"] == "queued"
    assert batches[0]["entity_ids"] == [str(pending.id)]
    assert batches[0]["entity_type"] == "organization"


def test_complete_text_is_not_queued(db_session) -> None:
    _org(
        db_session,
        "Harbour Club",
        description="Lessons",
        name_translations={"zh": "海港会", "zh-HK": "海港會"},
        description_translations={"zh": "課程", "zh-HK": "課程"},
    )
    result, batches = start_translation_scan(
        db_session,
        review_scope="all",
        budget_seconds=None,
    )
    assert result["queued_for_model"] == 0
    assert batches == []
    assert result["status"] == "done"


def test_sweep_all_includes_an_approved_organization(db_session) -> None:
    approved = _org(db_session, "Approved Club", review_status="approved")
    result, batches = start_translation_scan(
        db_session,
        review_scope="all",
        budget_seconds=None,
    )
    queued = [item for batch in batches for item in batch["entity_ids"]]
    assert str(approved.id) in queued
    assert result["queued_for_model"] == 1


def test_dismissed_source_is_not_queued_again(db_session) -> None:
    from app.services.translation_gaps import source_hash

    org = _org(
        db_session,
        "Harbour Club",
        description="Lessons",
        description_translations={"zh": "課程", "zh-HK": "課程"},
    )
    db_session.add(
        TranslationFixProposal(
            entity_type="organization",
            entity_id=org.id,
            org_id=org.id,
            field="name",
            source_text={"en": "Harbour Club"},
            proposed_text={"zh": "海港会", "zh-HK": "海港會"},
            missing_languages=["zh", "zh-HK"],
            status="dismissed",
            input_hash=source_hash(
                entity_type="organization",
                entity_id=org.id,
                field="name",
                source={"en": "Harbour Club"},
            ),
        )
    )
    db_session.flush()
    result, batches = start_translation_scan(
        db_session,
        review_scope="pending_review",
        entity_type="organization",
        budget_seconds=None,
    )
    assert batches == []
    assert result["skipped"] >= 1


def test_filled_gap_clears_a_pending_proposal(db_session) -> None:
    org = _org(
        db_session,
        "Harbour Club",
        description="Lessons",
        name_translations={"zh": "海港会", "zh-HK": "海港會"},
        description_translations={"zh": "課程", "zh-HK": "課程"},
    )
    db_session.add(
        TranslationFixProposal(
            entity_type="organization",
            entity_id=org.id,
            org_id=org.id,
            field="name",
            source_text={"en": "Harbour Club"},
            proposed_text={"zh": "海港会"},
            missing_languages=["zh", "zh-HK"],
            status="pending",
        )
    )
    db_session.flush()
    result, _batches = start_translation_scan(
        db_session,
        review_scope="all",
        budget_seconds=None,
    )
    assert result["cleared"] >= 1
    remaining = db_session.scalar(
        select(TranslationFixProposal).where(
            TranslationFixProposal.entity_id == org.id,
            TranslationFixProposal.status == "pending",
        )
    )
    assert remaining is None


def test_model_stores_only_missing_languages(db_session) -> None:
    org = _org(db_session, "Harbour Club", description="Lessons")
    run = TranslationScanRun(status="running", review_scope="pending_review")
    db_session.add(run)
    db_session.flush()
    store_model_items(
        db_session,
        run.id,
        "organization",
        [str(org.id)],
        {
            "items": [
                {
                    "entity_id": str(org.id),
                    "field": "name",
                    "translations": {
                        "en": "Should stay",
                        "zh": "海港会",
                        "zh-HK": "海港會",
                    },
                    "confidence": 0.91,
                    "rationale": "From the English name",
                },
                {
                    "entity_id": str(org.id),
                    "field": "description",
                    "translations": {"zh": "課程", "zh-HK": "課程"},
                },
            ]
        },
    )
    rows = list(
        db_session.scalars(
            select(TranslationFixProposal).where(
                TranslationFixProposal.org_id == org.id
            )
        ).all()
    )
    by_field = {row.field: row for row in rows}
    assert "en" not in by_field["name"].proposed_text
    assert by_field["name"].proposed_text["zh-HK"] == "海港會"
    assert by_field["description"].missing_languages == ["zh", "zh-HK"]


def test_apply_fills_missing_languages_and_keeps_english(
    db_session, sample_activity_category
) -> None:
    org = _org(db_session, "Harbour Club")
    activity = _activity(db_session, org, sample_activity_category, "Swim")
    run = TranslationScanRun(status="done", review_scope="all")
    db_session.add(run)
    db_session.flush()
    store_model_items(
        db_session,
        run.id,
        "activity",
        [str(activity.id)],
        {
            "items": [
                {
                    "entity_id": str(activity.id),
                    "field": "name",
                    "translations": {"zh": "游泳", "zh-HK": "游泳"},
                }
            ]
        },
    )
    proposal = db_session.scalars(
        select(TranslationFixProposal).where(
            TranslationFixProposal.entity_id == activity.id
        )
    ).one()
    decide_proposal(
        db_session,
        proposal.id,
        "apply",
        "admin",
        translations={"zh": "游泳班", "zh-HK": "游泳班", "en": "Replaced"},
    )
    db_session.refresh(activity)
    assert activity.name == "Swim"
    assert activity.name_translations["zh"] == "游泳班"
    assert activity.name_translations["zh-HK"] == "游泳班"
    assert activity.description_translations["zh"] == "星期六班"


def test_apply_rejects_a_changed_source(db_session) -> None:
    org = _org(db_session, "Harbour Club")
    run = TranslationScanRun(status="done", review_scope="all")
    db_session.add(run)
    db_session.flush()
    store_model_items(
        db_session,
        run.id,
        "organization",
        [str(org.id)],
        {
            "items": [
                {
                    "entity_id": str(org.id),
                    "field": "name",
                    "translations": {"zh": "海港会", "zh-HK": "海港會"},
                }
            ]
        },
    )
    proposal = db_session.scalars(select(TranslationFixProposal)).one()
    org.name = "Harbour Club Limited"
    db_session.flush()
    with pytest.raises(ValidationError):
        decide_proposal(db_session, proposal.id, "apply", "admin")


def test_over_budget_blocks_a_sweep(db_session) -> None:
    settings = load_settings(db_session)
    settings.monthly_cost_limit_usd = Decimal(1)
    db_session.add(
        TranslationScanRun(
            status="done",
            review_scope="all",
            cost_usd=Decimal(1),
        )
    )
    _org(db_session, "Harbour Club")
    db_session.flush()
    with pytest.raises(ValidationError):
        start_translation_scan(db_session, review_scope="all", budget_seconds=None)


def test_translation_message_is_handled_before_a_location_sweep(monkeypatch) -> None:
    worker = _worker()
    called: dict[str, object] = {}

    def fake_translation(
        scan_run_id, entity_type, entity_ids, *, message_id, receive_count
    ):
        called["translation"] = (entity_type, entity_ids, message_id, receive_count)
        return True

    def fail_location(*_args, **_kwargs):
        raise AssertionError("translation payload should not call the location model")

    monkeypatch.setattr(worker, "process_translation_batch", fake_translation)
    monkeypatch.setattr(worker, "process_location_batch", fail_location)
    entity_id = str(uuid4())
    result = worker.lambda_handler(
        {
            "Records": [
                {
                    "messageId": "m-tr",
                    "body": json.dumps(
                        {
                            "translation_scan_run_id": str(uuid4()),
                            "location_scan_run_id": str(uuid4()),
                            "entity_type": "organization",
                            "entity_ids": [entity_id],
                        }
                    ),
                    "attributes": {"ApproximateReceiveCount": "1"},
                }
            ]
        },
        None,
    )
    assert called["translation"] == ("organization", [entity_id], "m-tr", 1)
    assert result == {"batchItemFailures": []}
