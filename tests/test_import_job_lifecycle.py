"""Live import jobs commit running before work and failed after errors."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.api.admin_imports import (
    _handle_import_process,
    _handle_list_import_jobs,
)
from app.api.admin_imports_jobs import (
    caller_import_source,
    fail_import_job,
    job_source,
    source_for_import_run,
    summary_source,
)


def _event(*, groups: str = "admin", dry_run: bool = False) -> dict:
    return {
        "httpMethod": "POST",
        "path": "/v1/admin/imports",
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "caller-sub",
                    "cognito:groups": groups,
                }
            }
        },
        "body": json.dumps(
            {
                "object_key": "admin/imports/file.json",
                "dry_run": dry_run,
            }
        ),
    }


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def rollback(self):
        return None

    def commit(self):
        return None


def test_live_import_failure_marks_job(monkeypatch) -> None:
    order: list[str] = []

    class _Job:
        id = "00000000-0000-0000-0000-000000000010"

    class _TrackingSession(_Session):
        def commit(self):
            order.append("commit")

        def rollback(self):
            order.append("rollback")

    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _TrackingSession(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports.find_import_job_by_key",
        lambda session, key: None,
    )
    monkeypatch.setattr(
        "app.api.admin_imports._load_import_payload",
        lambda key: {"organizations": []},
    )
    monkeypatch.setattr(
        "app.api.admin_imports.begin_import_job",
        lambda session, object_key, **kwargs: order.append("begin") or _Job(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports._set_session_audit_context",
        lambda session, event: None,
    )

    def boom(*args, **kwargs):
        order.append("process")
        raise RuntimeError("boom")

    monkeypatch.setattr("app.api.admin_imports.process_import_payload", boom)
    monkeypatch.setattr(
        "app.api.admin_imports.fail_import_job",
        lambda session, job_id, error_type, **_kwargs: order.append(
            f"fail:{job_id}:{error_type}"
        ),
    )

    try:
        _handle_import_process(_event())
        raise AssertionError("expected the import error")
    except RuntimeError:
        pass
    assert order == [
        "begin",
        "commit",
        "process",
        "rollback",
        "fail:00000000-0000-0000-0000-000000000010:RuntimeError",
        "commit",
    ]


def test_failed_job_can_be_retried(monkeypatch) -> None:
    class _Failed:
        dry_run = False
        status = "failed"

    class _Live:
        id = "00000000-0000-0000-0000-000000000012"

    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _Session(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports.find_import_job_by_key",
        lambda session, key: _Failed(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports._load_import_payload",
        lambda key: {"organizations": []},
    )
    monkeypatch.setattr(
        "app.api.admin_imports.begin_import_job",
        lambda session, object_key, **kwargs: calls.append("begin") or _Live(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports.finish_import_job",
        lambda *args, **kwargs: calls.append("finish") or _Live(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports.process_import_payload",
        lambda *args, **kwargs: calls.append("process") or ({}, []),
    )
    monkeypatch.setattr(
        "app.api.admin_imports._set_session_audit_context",
        lambda session, event: None,
    )

    response = _handle_import_process(_event())
    assert response["statusCode"] == 200
    assert calls == ["begin", "process", "finish"]


def _history_job(
    object_key: str,
    job_id: str,
    *,
    created_at: datetime | str | None = None,
    summary: dict | None = None,
) -> SimpleNamespace:
    when = created_at if created_at is not None else datetime.now(UTC)
    return SimpleNamespace(
        id=job_id,
        object_key=object_key,
        dry_run=False,
        status="completed",
        summary={"allow_updates": True} if summary is None else summary,
        results=[],
        file_warnings=[],
        created_at=when,
        updated_at=when,
    )


def _stub_history_list(monkeypatch, jobs: list[object]) -> None:
    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _Session(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports.list_import_jobs",
        lambda session, limit, cursor: jobs,
    )


def _list_event() -> dict:
    return {
        "httpMethod": "GET",
        "path": "/v1/admin/imports",
    }


def test_history_list_links_each_file_to_s3(monkeypatch) -> None:
    signed: list[dict] = []

    class _S3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            signed.append(
                {
                    "operation": operation,
                    "params": Params,
                    "expires": ExpiresIn,
                }
            )
            key = Params["Key"]
            return f"https://s3.example/{key}"

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    _stub_history_list(
        monkeypatch,
        [
            _history_job(
                ("admin/imports/0123456789abcdef0123456789abcdef-catalog.json"),
                "00000000-0000-0000-0000-000000000021",
            )
        ],
    )
    monkeypatch.setattr(
        "app.api.admin_imports_objects.get_s3_client",
        lambda: _S3(),
    )

    response = _handle_list_import_jobs(_list_event())
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["items"][0]["download_url"] == (
        "https://s3.example/admin/imports/0123456789abcdef0123456789abcdef-catalog.json"
    )
    assert signed == [
        {
            "operation": "get_object",
            "params": {
                "Bucket": "import-bucket",
                "Key": ("admin/imports/0123456789abcdef0123456789abcdef-catalog.json"),
                "ResponseContentDisposition": 'inline; filename="catalog.json"',
                "ResponseContentType": "application/json",
            },
            "expires": 3600,
        }
    ]


def test_history_list_skips_download_url_after_object_expiry(monkeypatch) -> None:
    def _boom():
        raise AssertionError("expired objects are not signed")

    _stub_history_list(
        monkeypatch,
        [
            _history_job(
                "admin/imports/old.json",
                "00000000-0000-0000-0000-000000000023",
                created_at=datetime.now(UTC) - timedelta(days=8),
            )
        ],
    )
    monkeypatch.setattr("app.api.admin_imports_objects.get_s3_client", _boom)

    response = _handle_list_import_jobs(_list_event())
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "download_url" not in body["items"][0]
    assert body["items"][0]["object_key"] == "admin/imports/old.json"


def test_history_list_survives_signing_failure(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("s3 unavailable")

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    _stub_history_list(
        monkeypatch,
        [
            _history_job(
                "admin/imports/catalog.json",
                "00000000-0000-0000-0000-000000000024",
            )
        ],
    )
    monkeypatch.setattr("app.api.admin_imports_objects.get_s3_client", _boom)

    response = _handle_list_import_jobs(_list_event())
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "download_url" not in body["items"][0]
    assert body["items"][0]["object_key"] == "admin/imports/catalog.json"


def test_history_list_skips_download_url_for_foreign_key(monkeypatch) -> None:
    def _boom():
        raise AssertionError("foreign keys are not signed")

    _stub_history_list(
        monkeypatch,
        [
            _history_job(
                "other/secret.json",
                "00000000-0000-0000-0000-000000000022",
            )
        ],
    )
    monkeypatch.setattr("app.api.admin_imports_objects.get_s3_client", _boom)

    response = _handle_list_import_jobs(_list_event())
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "download_url" not in body["items"][0]
    assert body["items"][0]["object_key"] == "other/secret.json"


def test_caller_import_source_maps_admin_and_board() -> None:
    assert caller_import_source(is_admin=True, is_importer=False) == "ui"
    assert caller_import_source(is_admin=True, is_importer=True) == "ui"
    assert caller_import_source(is_admin=False, is_importer=True) == "board"
    assert caller_import_source(is_admin=False, is_importer=False) == "ui"


def test_source_for_import_run_keeps_stored_source_on_retry() -> None:
    assert source_for_import_run("ui", {"source": "board"}, retry=True) == "board"
    assert source_for_import_run("ui", {}, retry=True) == "ui"
    assert source_for_import_run("board", {"source": "ui"}, retry=False) == "board"
    assert summary_source({"source": "elsewhere"}) is None
    assert summary_source(None) is None


def test_failed_import_keeps_source() -> None:
    class _Session:
        def __init__(self, job: SimpleNamespace) -> None:
            self.job = job

        def get(self, model: object, job_id: object) -> SimpleNamespace:
            return self.job

        def flush(self) -> None:
            return None

    job = SimpleNamespace(
        status="running",
        summary={"source": "board"},
        file_warnings=[],
        updated_at=None,
    )
    fail_import_job(_Session(job), "job-id", "RuntimeError")
    assert job.status == "failed"
    assert job.summary == {"error": "RuntimeError", "source": "board"}


def test_job_source_reads_known_summary_values() -> None:
    stored = SimpleNamespace(summary={"source": "board", "allow_updates": False})
    assert job_source(stored) == "board"
    legacy = SimpleNamespace(summary={"allow_updates": True})
    assert job_source(legacy) is None


def test_history_list_returns_source(monkeypatch) -> None:
    _stub_history_list(
        monkeypatch,
        [
            _history_job(
                "admin/imports/board.json",
                "00000000-0000-0000-0000-000000000031",
                summary={"allow_updates": True, "source": "board"},
            ),
            _history_job(
                "admin/imports/legacy.json",
                "00000000-0000-0000-0000-000000000032",
                summary={"allow_updates": True},
            ),
        ],
    )

    response = _handle_list_import_jobs(_list_event())
    body = json.loads(response["body"])
    assert body["items"][0]["source"] == "board"
    assert body["items"][1]["source"] is None


def _stub_import_run(monkeypatch, captured: dict) -> None:
    class _Job:
        id = "00000000-0000-0000-0000-000000000041"

    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _Session(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports.find_import_job_by_key",
        lambda session, key: None,
    )
    monkeypatch.setattr(
        "app.api.admin_imports._load_import_payload",
        lambda key: {"organizations": []},
    )
    monkeypatch.setattr(
        "app.api.admin_imports.begin_import_job",
        lambda session, object_key, **kwargs: captured.update(begin=kwargs) or _Job(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports.finish_import_job",
        lambda *args, **kwargs: captured.update(finish=kwargs) or _Job(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports.store_import_job",
        lambda *args, **kwargs: captured.update(store=kwargs) or _Job(),
    )
    monkeypatch.setattr(
        "app.api.admin_imports.process_import_payload",
        lambda *args, **kwargs: ({}, []),
    )
    monkeypatch.setattr(
        "app.api.admin_imports._set_session_audit_context",
        lambda session, event: None,
    )


def test_admin_import_records_ui_source(monkeypatch) -> None:
    captured: dict = {}
    _stub_import_run(monkeypatch, captured)

    response = _handle_import_process(_event())
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert captured["begin"]["source"] == "ui"
    assert captured["finish"]["summary"]["source"] == "ui"
    assert body["source"] == "ui"


def test_board_import_records_board_source(monkeypatch) -> None:
    captured: dict = {}
    _stub_import_run(monkeypatch, captured)

    response = _handle_import_process(_event(groups="importer"))
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert captured["begin"]["source"] == "board"
    assert captured["finish"]["summary"]["source"] == "board"
    assert body["source"] == "board"


def test_dry_run_records_caller_source(monkeypatch) -> None:
    captured: dict = {}
    _stub_import_run(monkeypatch, captured)

    response = _handle_import_process(_event(groups="importer", dry_run=True))
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "begin" not in captured
    assert captured["store"]["summary"]["source"] == "board"
    assert body["source"] == "board"
