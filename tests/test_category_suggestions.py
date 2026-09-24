"""Category suggestion capture, enrichment, and admin decisions."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import uuid4

import pytest
from psycopg.types.range import Range
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.admin import lambda_handler
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_upsert import upsert_activity
from app.api.admin_resource_activity_category import (
    _serialize_activity_category,
    _update_activity_category,
    _validate_category_parent,
)
from app.db.models import Activity
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
)
from app.db.queries import ActivitySearchFilters
from app.db.queries import build_search_query
from app.db.repositories.activity_category import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.category_suggestions.capture import (
    capture_pending,
    ensure_pending_category,
)
from app.services.category_suggestions.prompt import redact_contacts
from app.services.category_suggestions.resolve import (
    begin_capture_batch,
    finish_capture_batch,
    import_enrichment_ids,
    normalize_category_key,
    resolve_category_name,
)
from app.services.category_suggestions.settings import (
    apply_settings_update,
    get_settings,
    validate_model_slug,
)
from app.services.org_review import collect_issues
from app.services.org_review_sql import BLOCKER_ISSUE_CODES


@pytest.fixture(autouse=True)
def _reset_capture_batch():
    yield
    from app.services.category_suggestions import resolve as resolve_module

    resolve_module._batch = None
    resolve_module._last_enqueue = []


def _activity_payload(**overrides: object) -> dict:
    payload = {
        "name": "Import Activity",
        "description": "Desc",
        "age_min": 5,
        "age_max": 12,
    }
    payload.update(overrides)
    return payload


def _enable_capture(db_session: Session) -> None:
    row = get_settings(db_session)
    row.on_import_enabled = True
    row.auto_enrich_enabled = True
    db_session.flush()
    begin_capture_batch(db_session)


def test_normalize_category_key_folds_case_and_punctuation() -> None:
    assert normalize_category_key("  Pottery Class! ") == "pottery class"
    assert normalize_category_key("Pottery   Class") == "pottery class"
    assert normalize_category_key("戶外活動") == "戶外活動"


def test_resolve_exact_alias_fuzzy_and_capture(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    exact = resolve_category_name(db_session, sample_activity_category.name)
    assert exact.category_id == sample_activity_category.id

    sample_activity_category.name_translations = {"zh": "測試班"}
    db_session.flush()
    fuzzy = resolve_category_name(db_session, "測試班")
    assert fuzzy.category_id == sample_activity_category.id

    with pytest.raises(ValidationError):
        resolve_category_name(db_session, "Missing Category")

    _enable_capture(db_session)
    captured = resolve_category_name(db_session, "Missing Category")
    assert captured.capture is True

    activity = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Clay",
        description="email me at parent@example.com or 85212345678",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    ensure_pending_category(db_session)
    activity.category_id = PENDING_CATEGORY_ID
    warning = capture_pending(
        db_session,
        activity=activity,
        requested_name="Missing Category",
        org=sample_organization,
        import_job_id=None,
    )
    assert "captured as pending suggestion" in warning
    again = capture_pending(
        db_session,
        activity=activity,
        requested_name="missing category",
        org=sample_organization,
        import_job_id=None,
    )
    assert again
    suggestion = db_session.query(CategorySuggestion).one()
    assert suggestion.activity_count == 1
    suggestion.status = "rejected"
    db_session.flush()
    capture_pending(
        db_session,
        activity=activity,
        requested_name="Missing Category",
        org=sample_organization,
        import_job_id=None,
    )
    db_session.refresh(suggestion)
    assert suggestion.status == "pending"
    assert suggestion.reopened_at is not None
    assert "[redacted-email]" in redact_contacts(activity.description or "")


def test_alias_uses_created_category(
    db_session,
    sample_activity_category,
) -> None:
    db_session.add(
        CategorySuggestion(
            fingerprint=normalize_category_key("Pottery"),
            requested_name="Pottery",
            status="approved",
            created_category_id=sample_activity_category.id,
        )
    )
    db_session.flush()
    resolved = resolve_category_name(db_session, "Pottery")
    assert resolved.category_id == sample_activity_category.id


def test_dry_run_does_not_enqueue(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    _enable_capture(db_session)
    summary, _results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": "Clay House",
                    "description": "Studio",
                    "manager_id": "00000000-0000-0000-0000-000000000099",
                    "locations": [
                        {
                            "name": "Room",
                            "area_name": sample_geographic_area.name,
                        }
                    ],
                    "activities": [
                        _activity_payload(category_name="Wheel throwing"),
                    ],
                }
            ]
        },
        [],
        dry_run=True,
    )
    assert summary["captured_categories"] == 1
    assert import_enrichment_ids(dry_run=True) == []


def test_upsert_capture_sets_pending_category(
    db_session,
    sample_organization,
) -> None:
    _enable_capture(db_session)
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(category_name="Unknown Studio"),
        warnings=[],
    )
    assert status == "created"
    assert activity.category_id == PENDING_CATEGORY_ID
    summary: dict = {}
    finish_capture_batch(summary)
    ids = import_enrichment_ids(dry_run=False)
    assert summary["captured_categories"] == 1
    assert len(ids) == 1


def test_decisions_reassign_and_alias(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    from app.services.category_suggestions.decisions import apply_decision

    _enable_capture(db_session)
    activity, _status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(name="Pot A", category_name="Ceramics Lab"),
        warnings=[],
    )
    finish_capture_batch({})
    suggestion = db_session.query(CategorySuggestion).one()
    mapped = apply_decision(
        db_session,
        suggestion,
        {"action": "map", "category_id": str(sample_activity_category.id)},
        decided_by="admin-user",
    )
    db_session.refresh(activity)
    assert mapped.status == "merged"
    assert activity.category_id == sample_activity_category.id
    assert resolve_category_name(db_session, "Ceramics Lab").category_id == (
        sample_activity_category.id
    )

    suggestion.status = "pending"
    suggestion.merged_into_category_id = None
    activity.category_id = PENDING_CATEGORY_ID
    db_session.flush()
    approved = apply_decision(
        db_session,
        suggestion,
        {"action": "approve", "name": "Ceramics", "parent_id": None},
        decided_by="admin-user",
    )
    db_session.refresh(activity)
    assert approved.status == "approved"
    assert approved.created_category_id is not None
    assert activity.category_id == approved.created_category_id


def test_settings_validation_clears_model_cache(db_session, monkeypatch) -> None:
    called = {"cleared": False}

    def _clear() -> None:
        called["cleared"] = True

    monkeypatch.setattr(
        "app.services.openrouter_client.clear_openrouter_model_cache",
        _clear,
    )
    with pytest.raises(ValidationError):
        validate_model_slug("not a model", "openrouter_model")
    row = apply_settings_update(
        db_session,
        {
            "openrouter_model": "qwen/qwen-turbo",
            "fallback_models": ["qwen/qwen3-30b-a3b"],
            "max_evidence_items": 10,
        },
        updated_by="admin-user",
    )
    assert row.openrouter_model == "qwen/qwen-turbo"
    assert called["cleared"] is True
    with pytest.raises(ValidationError):
        apply_settings_update(
            db_session,
            {"max_evidence_items": 2},
            updated_by="admin-user",
        )


def test_review_blocker_and_search_exclusion(
    db_session,
    sample_organization,
    sample_activity,
) -> None:
    ensure_pending_category(db_session)
    sample_activity.category_id = PENDING_CATEGORY_ID
    db_session.flush()
    issues = collect_issues(
        sample_organization,
        [],
        [sample_activity],
        {},
        {},
    )
    assert any(issue.code == "pending_category" for issue in issues)
    assert "pending_category" in BLOCKER_ISSUE_CODES
    compiled = build_search_query(ActivitySearchFilters())
    params = compiled.compile().params
    assert PENDING_CATEGORY_ID in params.values()


def test_pending_category_cannot_be_edited_or_deleted(db_session) -> None:
    pending = ensure_pending_category(db_session)
    repo = ActivityCategoryRepository(db_session)
    with pytest.raises(ValidationError):
        repo.delete(pending)
    with pytest.raises(ValidationError):
        _update_activity_category(repo, pending, {"name": "Renamed"})
    with pytest.raises(ValidationError):
        _validate_category_parent(repo, None, PENDING_CATEGORY_ID)
    payload = _serialize_activity_category(pending)
    assert payload["is_system"] is True
    other = ActivityCategory(name="Workshop", display_order=1)
    db_session.add(other)
    db_session.flush()
    assert _serialize_activity_category(other)["is_system"] is False


def test_importer_cannot_list_category_suggestions() -> None:
    response = lambda_handler(
        {
            "httpMethod": "GET",
            "path": "/v1/admin/category-suggestions",
            "requestContext": {
                "authorizer": {"groups": "importer", "userSub": "importer-user"}
            },
        },
        None,
    )
    assert response["statusCode"] == 403


def test_manager_cannot_list_category_suggestions() -> None:
    response = lambda_handler(
        {
            "httpMethod": "GET",
            "path": "/v1/admin/category-suggestions",
            "requestContext": {
                "authorizer": {"groups": "manager", "userSub": "manager-user"}
            },
        },
        None,
    )
    assert response["statusCode"] == 403


def _completion(content: str, *, model: str = "qwen/qwen3-30b-a3b") -> str:
    return json.dumps(
        {
            "model": model,
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "cost": 0.01},
        }
    )


def test_worker_success_repair_invalid_refusal_and_stale(
    monkeypatch,
    test_engine,
) -> None:
    from app.services.category_suggestions.enrich import process_suggestion
    from app.services.openrouter_client import OpenRouterError

    engine = test_engine
    monkeypatch.setattr(
        "app.services.category_suggestions.enrich.get_engine",
        lambda: engine,
    )
    suggestion_id = uuid4()
    category_id = uuid4()
    with Session(engine) as session:
        session.add(
            ActivityCategory(id=category_id, name="Indoor fun", display_order=1)
        )
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint="pottery",
                requested_name="Pottery",
                status="pending",
            )
        )
        session.commit()

    valid = json.dumps(
        {
            "maps_to_existing": {"category_id": str(uuid4())},
            "propose": {
                "name_en": "Ceramics",
                "name_zh": "陶藝",
                "parent_id": str(category_id),
                "rationale": "Indoor class",
                "display_order_hint": 4,
            },
            "confidence": 0.8,
            "rationale": "Indoor class",
            "alternatives": [],
        }
    )
    calls = {"n": 0}

    def _chat(**_kwargs: object) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion("not-json {")
        return _completion(valid)

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        _chat,
    )
    monkeypatch.setattr(
        "app.services.openrouter_json_parse.openrouter_chat_completion",
        _chat,
    )
    assert process_suggestion(suggestion_id, receive_count=1) is True
    with Session(engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        assert row.enrichment_status == "done"
        assert row.maps_to_category_id is None
        assert row.suggested_parent_id == category_id
        assert row.suggested_name == "Ceramics"

    def _refuse(**_kwargs: object) -> str:
        raise OpenRouterError("Model refused: no", status=200)

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        _refuse,
    )
    with Session(engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        row.enrichment_status = "none"
        session.commit()
    with pytest.raises(OpenRouterError):
        process_suggestion(suggestion_id, force=True, receive_count=1)
    with Session(engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        assert row.enrichment_status == "queued"

    def _limited(**_kwargs: object) -> str:
        raise OpenRouterError("status 429", status=429)

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        _limited,
    )
    assert process_suggestion(suggestion_id, force=True, receive_count=3) is True
    with Session(engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        assert row.enrichment_status == "failed"
        row.enrichment_status = "running"
        row.updated_at = datetime.now(timezone.utc) - timedelta(seconds=400)
        session.commit()
    assert process_suggestion(suggestion_id, receive_count=1) is True
    with Session(engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        assert row.enrichment_status == "failed"
    with Session(engine) as session:
        session.execute(
            delete(CategorySuggestion).where(CategorySuggestion.id == suggestion_id)
        )
        session.execute(
            delete(ActivityCategory).where(ActivityCategory.id == category_id)
        )
        session.commit()
