"""Busy delivery, retry, recorded replies, and read-only run routes."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.api.admin_data_quality import handle_data_quality
from app.api.admin_imports_jobs import reuse_stored_import_job
from app.db.models import (
    CategoryScanRun,
    DataQualityRun,
    ImportSettings,
    LocationScanRun,
    ModelAnswer,
    NameFixProposal,
    Organization,
)
from app.services.data_quality.answers import ModelReply, recorded_completion
from app.services.data_quality.checks import refresh_check, run_check
from app.services.data_quality.runs import (
    create_manual_run,
    process_run,
    retry_run,
)
from app.services.location_fix_scan import LocationScanBusy, start_location_scan
from app.services.org_delete_match import ORGANIZATION_DELETED
from app.services.org_review_names import pending_name_fix_ids
from sqlalchemy import select


def _event(path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    event = {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {"groups": "admin", "userSub": "admin-user"},
        },
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


class _OpenSession:
    def __init__(self, session) -> None:
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *_args) -> bool:
        return False


def _org(session) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Harbour Club",
        manager_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        review_status="pending_review",
    )
    session.add(org)
    session.flush()
    return org


def _run(session, checks: list[str]) -> DataQualityRun:
    _org(session)
    run = create_manual_run(
        session,
        {"checks": checks, "scope": {"kind": "all"}},
        requested_by="admin-user",
    )
    session.flush()
    return run


def _use_test_session(monkeypatch, session) -> None:
    monkeypatch.setattr("app.api.admin_data_quality.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_data_quality.Session",
        lambda _engine: _OpenSession(session),
    )


def test_pending_name_lookup_filters_entity_type(db_session) -> None:
    shared = uuid4()
    db_session.add(
        NameFixProposal(
            entity_type="activity",
            entity_id=shared,
            current_value="Swim Class",
            proposed_value="Swim",
            rules=["case"],
            status="pending",
        )
    )
    db_session.flush()
    assert pending_name_fix_ids(db_session, [shared], []) == set()
    assert pending_name_fix_ids(db_session, [], [shared]) == {str(shared)}


def test_skip_deleted_off_does_not_reuse_a_skipped_job(db_session) -> None:
    row = db_session.get(ImportSettings, 1)
    if row is None:
        row = ImportSettings(id=1)
        db_session.add(row)
    row.skip_deleted_organizations = False
    db_session.flush()
    job = SimpleNamespace(
        dry_run=False,
        status="completed",
        summary={"allow_updates": True},
        results=[
            {
                "type": "organizations",
                "key": "Harbour Club",
                "status": "skipped",
                "errors": [{"message": ORGANIZATION_DELETED, "field": "name"}],
            }
        ],
    )
    assert reuse_stored_import_job(db_session, job, False, True) is False


def test_busy_check_retries_then_continues(db_session, monkeypatch) -> None:
    run = _run(db_session, ["names", "duplicates"])

    def fake(_session, _run, check):
        if check.get("name") == "names":
            return {"status": "busy", "detail": {}, "batches": []}
        return {"status": "done", "detail": {}, "batches": []}

    monkeypatch.setattr("app.services.data_quality.runs.run_check", fake)
    assert process_run(db_session, run.id, "message-1", receive_count=1) is False
    assert run.status == "queued"
    by_name = {item["name"]: item["status"] for item in run.checks}
    assert by_name == {"names": "busy", "duplicates": "queued"}
    assert process_run(db_session, run.id, "message-1", receive_count=3) is True
    by_name = {item["name"]: item["status"] for item in run.checks}
    assert by_name == {"names": "busy", "duplicates": "done"}
    assert run.status == "busy"
    assert run.refresh is False


def test_worker_enqueues_location_and_category_batches(db_session, monkeypatch) -> None:
    run = _run(db_session, ["locations", "categories"])
    locations: list[tuple] = []
    categories: list[tuple] = []

    def fake(_session, _run, check):
        name = check["name"]
        return {
            "status": "running",
            "detail": {"scan_run_id": f"scan-{name}"},
            "batches": [{"entity_ids": ["a"]}] if name == "locations" else [["a"]],
            "batch_kind": "location" if name == "locations" else "category",
        }

    monkeypatch.setenv("CATEGORY_SUGGESTION_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr("app.services.data_quality.runs.run_check", fake)
    monkeypatch.setattr(
        "app.services.category_suggestions.events.enqueue_location_batches",
        lambda scan_id, batches: locations.append((scan_id, batches)),
    )
    monkeypatch.setattr(
        "app.services.category_suggestions.events.enqueue_scan_batches",
        lambda scan_id, batches: categories.append((scan_id, batches)),
    )
    assert process_run(db_session, run.id, "message-1") is True
    assert locations == [("scan-locations", [{"entity_ids": ["a"]}])]
    assert categories == [("scan-categories", [["a"]])]


def test_failed_enqueue_asks_for_another_delivery(db_session, monkeypatch) -> None:
    run = _run(db_session, ["locations"])

    def fake(_session, _run, _check):
        return {
            "status": "running",
            "detail": {"scan_run_id": "scan-1", "pending_batches": [["a"]]},
            "batches": [["a"]],
            "batch_kind": "location",
        }

    monkeypatch.setenv("CATEGORY_SUGGESTION_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr("app.services.data_quality.runs.run_check", fake)

    def boom(_scan_id, _batches):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "app.services.category_suggestions.events.enqueue_location_batches",
        boom,
    )
    assert process_run(db_session, run.id, "message-1") is False
    assert run.status == "running"
    assert "message-1" not in list(run.processed_message_ids or [])


def test_open_child_resends_batches_that_never_left(db_session) -> None:
    run = _run(db_session, ["locations"])
    child = LocationScanRun(
        status="queued",
        review_scope="all",
        data_quality_run_id=run.id,
        batches_done=0,
        batches_total=2,
    )
    db_session.add(child)
    db_session.flush()
    pending = [{"entity_ids": ["a"]}, {"entity_ids": ["b"]}]
    check = {
        "name": "locations",
        "status": "running",
        "detail": {"pending_batches": pending, "scan_run_id": str(child.id)},
    }
    resumed = run_check(db_session, run, check)
    assert resumed["batches"] == pending
    assert resumed["batch_kind"] == "location"
    child.batches_done = 1
    resumed = run_check(db_session, run, check)
    assert resumed["batches"] == [pending[1]]
    child.status = "failed"
    child.error = "boom"
    assert run_check(db_session, run, check)["status"] == "failed"


def test_truncated_category_check_is_partial(db_session) -> None:
    run = _run(db_session, ["categories"])
    db_session.add(CategoryScanRun(status="done", data_quality_run_id=run.id))
    db_session.flush()
    check = {
        "name": "categories",
        "status": "running",
        "detail": {"truncated": True},
    }
    refresh_check(db_session, run, check)
    assert check["status"] == "partial"


def test_retry_requeues_every_check_and_refreshes(db_session) -> None:
    run = _run(db_session, ["duplicates"])
    assert process_run(db_session, run.id, "message-1") is True
    assert run.status == "done"
    child = LocationScanRun(
        status="failed",
        review_scope="all",
        data_quality_run_id=run.id,
        error="boom",
    )
    db_session.add(child)
    db_session.flush()
    assert retry_run(db_session, run, refresh=True) is True
    assert run.status == "queued"
    assert run.attempt == 2
    assert run.refresh is True
    assert run.checks == [{"name": "duplicates", "status": "queued"}]
    assert child.data_quality_run_id is None
    assert retry_run(db_session, run) is False


def test_retry_route_skips_a_second_message_while_open(db_session, monkeypatch) -> None:
    run = _run(db_session, ["duplicates"])
    run.status = "running"
    db_session.flush()
    sent: list[str] = []
    _use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(
        "app.api.admin_data_quality.enqueue_staged_run",
        lambda run_id: sent.append(run_id),
    )
    response = handle_data_quality(
        _event(
            f"/v1/admin/data-quality/runs/{run.id}",
            method="POST",
            body={"action": "retry", "refresh": True},
        ),
        "POST",
        "runs",
        str(run.id),
    )
    assert response["statusCode"] == 200
    assert sent == []
    assert run.status == "running"
    run.status = "done"
    response = handle_data_quality(
        _event(
            f"/v1/admin/data-quality/runs/{run.id}",
            method="POST",
            body={"action": "retry", "refresh": True},
        ),
        "POST",
        "runs",
        str(run.id),
    )
    assert response["statusCode"] == 200
    assert sent == [str(run.id)]
    assert run.refresh is True
    assert run.attempt == 2


def test_reading_a_run_does_not_write(db_session, monkeypatch) -> None:
    run = _run(db_session, ["categories"])
    run.status = "running"
    run.checks = [
        {
            "name": "categories",
            "status": "running",
            "detail": {"truncated": True, "groups": [1, 2]},
        }
    ]
    db_session.add(CategoryScanRun(status="done", data_quality_run_id=run.id))
    db_session.flush()
    commits: list[int] = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))
    _use_test_session(monkeypatch, db_session)
    listed = handle_data_quality(
        _event("/v1/admin/data-quality/runs"),
        "GET",
        "runs",
        None,
    )
    body = json.loads(listed["body"])
    assert body["items"][0]["checks"] == [{"name": "categories", "status": "running"}]
    status_event = _event(f"/v1/admin/data-quality/runs/{run.id}")
    status_event["queryStringParameters"] = {"view": "status"}
    status = handle_data_quality(status_event, "GET", "runs", str(run.id))
    assert json.loads(status["body"])["checks"] == [
        {"name": "categories", "status": "running"}
    ]
    full = handle_data_quality(
        _event(f"/v1/admin/data-quality/runs/{run.id}"),
        "GET",
        "runs",
        str(run.id),
    )
    assert json.loads(full["body"])["checks"][0]["detail"]["groups"] == [1, 2]
    assert commits == []
    assert run.status == "running"
    assert run.checks[0]["detail"]["truncated"] is True


def test_recorded_reply_is_reused_without_usage(db_session, monkeypatch) -> None:
    calls: list[int] = []
    body = json.dumps(
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "cost": 0.2},
            "model": "m",
        }
    )

    def invoke() -> str:
        calls.append(1)
        return body

    def read(key: str) -> str | None:
        row = db_session.get(ModelAnswer, key)
        if row is None or not isinstance(row.response, dict):
            return None
        stored = row.response.get("body")
        return stored if isinstance(stored, str) else None

    monkeypatch.setattr("app.services.data_quality.answers._read_body", read)
    kwargs = {
        "record": True,
        "refresh": False,
        "prompt_version": "verify-1",
        "model": "m",
        "system_prompt": "sys",
        "user_content": "user",
        "invoke": invoke,
    }
    first = recorded_completion(**kwargs)
    assert first.usage["cost_usd"] == 0.2
    first.keep(db_session)
    db_session.flush()
    second = recorded_completion(**kwargs)
    assert calls == [1]
    assert second.usage == {}
    assert second.store is False
    assert json.loads(second.body)["usage"] == {}
    replacement = ModelReply(
        "other",
        {"cost_usd": 1},
        store=True,
        refresh=False,
        key=first.key,
        model="m",
        prompt_version="verify-1",
    )
    replacement.keep(db_session)
    stored = db_session.get(ModelAnswer, first.key)
    assert stored is not None
    assert stored.response["body"] == body
    refreshed = ModelReply(
        "fresh",
        {"cost_usd": 1},
        store=True,
        refresh=True,
        key=first.key,
        model="m",
        prompt_version="verify-1",
    )
    refreshed.keep(db_session)
    assert db_session.get(ModelAnswer, first.key).response["body"] == "fresh"


def test_unparsed_reply_is_not_stored(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.data_quality.answers._read_body", lambda _key: None
    )
    reply = recorded_completion(
        record=True,
        refresh=False,
        prompt_version="locations-1",
        model="m",
        system_prompt="sys",
        user_content="place",
        invoke=lambda: "not-json",
    )
    assert db_session.scalars(select(ModelAnswer)).all() == []
    assert reply.key


def test_scan_start_race_keeps_flushed_rows(db_session, monkeypatch) -> None:
    bind = db_session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        pytest.skip("partial unique index is postgres-only")
    org = _org(db_session)
    db_session.add(LocationScanRun(status="queued", review_scope="all"))
    db_session.flush()
    real = db_session.scalar

    def hide(statement, *args, **kwargs):
        if "location_scan_runs.id" in str(statement):
            return None
        return real(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "scalar", hide)
    with pytest.raises(LocationScanBusy):
        start_location_scan(db_session, review_scope="all", budget_seconds=None)
    assert db_session.get(Organization, org.id) is not None
