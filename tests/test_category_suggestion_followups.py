"""Follow-up coverage for category suggestion review findings."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.admin import lambda_handler
from app.api.admin_category_suggestions import _month_cost
from app.api.admin_category_suggestions import _summary
from app.api.admin_imports_upsert import upsert_activity
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import CategorySuggestion
from app.exceptions import ValidationError
from app.services.category_suggestions.decisions import apply_decision
from app.services.category_suggestions.resolve import begin_capture_batch
from app.services.category_suggestions.resolve import finish_capture_batch
from app.services.category_suggestions.resolve import import_enrichment_ids
from app.services.category_suggestions.resolve import note_suggestion
from app.services.category_suggestions.resolve import resolve_category_name
from app.services.openrouter_client import OpenRouterError
from tests.test_category_suggestions import _activity_payload
from tests.test_category_suggestions import _enable_capture


def test_ambiguous_exact_name_is_captured_when_enabled(db_session) -> None:
    root_a = ActivityCategory(name="Root A", display_order=1)
    root_b = ActivityCategory(name="Root B", display_order=2)
    db_session.add_all([root_a, root_b])
    db_session.flush()
    db_session.add_all(
        [
            ActivityCategory(name="Shared", parent_id=root_a.id, display_order=1),
            ActivityCategory(name="Shared", parent_id=root_b.id, display_order=1),
        ]
    )
    db_session.flush()
    with pytest.raises(ValidationError):
        resolve_category_name(db_session, "Shared")
    _enable_capture(db_session)
    captured = resolve_category_name(db_session, "Shared")
    assert captured.capture is True


def test_finish_drops_ids_that_are_not_in_the_transaction(db_session) -> None:
    begin_capture_batch(db_session)
    note_suggestion(uuid4(), enqueue=True)
    summary: dict = {}
    finish_capture_batch(summary, db_session)
    assert summary["captured_categories"] == 0
    assert import_enrichment_ids(dry_run=False) == []


def test_reject_without_target_stays_visible_as_stranded(
    db_session,
    sample_organization,
) -> None:
    _enable_capture(db_session)
    activity, _status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(name="Pot B", category_name="No Home"),
        warnings=[],
    )
    finish_capture_batch({}, db_session)
    suggestion = db_session.query(CategorySuggestion).one()
    apply_decision(
        db_session,
        suggestion,
        {"action": "reject"},
        decided_by="admin-user",
    )
    db_session.refresh(activity)
    assert activity.category_id is not None
    summary = _summary(db_session)
    assert summary["stranded_activity_total"] == 1


def test_month_cost_ignores_earlier_enrichments() -> None:
    month_start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    usage = {
        "cost_usd": 5,
        "events": [
            {"at": "2026-08-01T00:00:00+00:00", "cost_usd": 4},
            {"at": "2026-09-02T00:00:00+00:00", "cost_usd": 1},
        ],
    }
    enriched_at = datetime(2026, 9, 2, tzinfo=timezone.utc)
    assert _month_cost(usage, enriched_at, month_start) == 1


def test_enqueue_sends_only_rows_that_exist(monkeypatch, test_engine) -> None:
    from app.services.category_suggestions.events import enqueue_enrichment

    sent: list[dict] = []

    class _Sqs:
        def send_message(self, **kwargs: object) -> None:
            sent.append(kwargs)

    monkeypatch.setattr(
        "app.services.category_suggestions.events.get_engine",
        lambda: test_engine,
    )
    monkeypatch.setattr(
        "app.services.category_suggestions.events.get_client",
        lambda _service: _Sqs(),
    )
    monkeypatch.setenv(
        "CATEGORY_SUGGESTION_QUEUE_URL",
        "https://sqs.example/category-suggestions",
    )
    suggestion_id = uuid4()
    with Session(test_engine) as session:
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint="enqueue-me",
                requested_name="Enqueue",
                status="pending",
            )
        )
        session.commit()
    enqueue_enrichment([str(suggestion_id), str(uuid4())])
    assert len(sent) == 1
    assert str(suggestion_id) in str(sent[0]["MessageBody"])
    with Session(test_engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        assert row.enrichment_status == "queued"
        session.delete(row)
        session.commit()


def test_worker_uses_one_openrouter_attempt(monkeypatch, test_engine) -> None:
    from app.services.category_suggestions.enrich import process_suggestion

    seen: dict[str, object] = {}
    suggestion_id = uuid4()
    monkeypatch.setattr(
        "app.services.category_suggestions.enrich.get_engine",
        lambda: test_engine,
    )

    def _chat(**kwargs: object) -> str:
        seen.update(kwargs)
        return json.dumps(
            {
                "model": "qwen/qwen3-30b-a3b",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "propose": {"name_en": "Ceramics"},
                                    "confidence": 0.5,
                                    "rationale": "class",
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.1},
            }
        )

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        _chat,
    )
    with Session(test_engine) as session:
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint="one-attempt",
                requested_name="One Attempt",
                status="pending",
            )
        )
        session.commit()
    assert process_suggestion(suggestion_id, receive_count=1) is True
    assert seen["max_attempts"] == 1
    assert seen["model"] == "qwen/qwen3-30b-a3b"
    with Session(test_engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        session.delete(row)
        session.commit()


def test_recent_running_attempt_is_not_treated_as_stale(
    monkeypatch,
    test_engine,
) -> None:
    from app.services.category_suggestions.enrich import process_suggestion

    suggestion_id = uuid4()
    monkeypatch.setattr(
        "app.services.category_suggestions.enrich.get_engine",
        lambda: test_engine,
    )
    called = {"n": 0}

    def _chat(**_kwargs: object) -> str:
        called["n"] += 1
        return "{}"

    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        _chat,
    )
    with Session(test_engine) as session:
        session.add(
            CategorySuggestion(
                id=suggestion_id,
                fingerprint="still-running",
                requested_name="Still Running",
                status="pending",
                enrichment_status="running",
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    assert process_suggestion(suggestion_id, receive_count=1) is False
    assert called["n"] == 0
    with Session(test_engine) as session:
        row = session.get(CategorySuggestion, suggestion_id)
        assert row is not None
        session.delete(row)
        session.commit()


def _admin_event(method: str, path: str, **extra: object) -> dict:
    event: dict = {
        "httpMethod": method,
        "path": path,
        "requestContext": {"authorizer": {"groups": "admin", "userSub": "admin-user"}},
    }
    event.update(extra)
    return event


def test_list_cursor_and_literal_percent(monkeypatch, test_engine) -> None:
    monkeypatch.setattr(
        "app.api.admin_category_suggestions.get_engine",
        lambda: test_engine,
    )
    high_id = uuid4()
    low_id = uuid4()
    with Session(test_engine) as session:
        session.add_all(
            [
                CategorySuggestion(
                    id=high_id,
                    fingerprint="percent-clay",
                    requested_name="100% clay",
                    status="pending",
                    activity_count=2_000_000_000,
                ),
                CategorySuggestion(
                    id=low_id,
                    fingerprint="other-name",
                    requested_name="other",
                    status="pending",
                    activity_count=1_999_999_999,
                ),
            ]
        )
        session.commit()
    first = lambda_handler(
        _admin_event(
            "GET",
            "/v1/admin/category-suggestions",
            queryStringParameters={"limit": "1"},
        ),
        None,
    )
    assert first["statusCode"] == 200
    page = json.loads(first["body"])
    assert page["items"][0]["requested_name"] == "100% clay"
    assert page["next_cursor"]
    second = lambda_handler(
        _admin_event(
            "GET",
            "/v1/admin/category-suggestions",
            queryStringParameters={"limit": "1", "cursor": page["next_cursor"]},
        ),
        None,
    )
    assert json.loads(second["body"])["items"][0]["requested_name"] == "other"
    filtered = lambda_handler(
        _admin_event(
            "GET",
            "/v1/admin/category-suggestions",
            queryStringParameters={"q": "%"},
        ),
        None,
    )
    names = [item["requested_name"] for item in json.loads(filtered["body"])["items"]]
    assert "100% clay" in names
    assert "other" not in names
    with Session(test_engine) as session:
        for suggestion_id in (high_id, low_id):
            row = session.get(CategorySuggestion, suggestion_id)
            if row is not None:
                session.delete(row)
        session.commit()


def test_settings_model_test_returns_502(monkeypatch, test_engine) -> None:
    monkeypatch.setattr(
        "app.api.admin_category_suggestion_settings.get_engine",
        lambda: test_engine,
    )

    def _down(**_kwargs: object) -> str:
        raise OpenRouterError("down", status=503)

    monkeypatch.setattr(
        "app.api.admin_category_suggestion_settings.openrouter_chat_completion",
        _down,
    )
    response = lambda_handler(
        _admin_event(
            "POST",
            "/v1/admin/category-suggestions/settings/test",
            body="{}",
            headers={"Content-Type": "application/json"},
        ),
        None,
    )
    assert response["statusCode"] == 502
