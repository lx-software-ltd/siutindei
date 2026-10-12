"""Live import jobs commit running before work and failed after errors."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.api.admin_imports import (
    _handle_import_process,
    _handle_list_import_jobs,
)


def _event() -> dict:
    return {
        "httpMethod": "POST",
        "path": "/v1/admin/imports",
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "caller-sub",
                    "cognito:groups": "admin",
                }
            }
        },
        "body": json.dumps(
            {
                "object_key": "admin/imports/file.json",
                "dry_run": False,
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
        lambda session, object_key: order.append("begin") or _Job(),
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
        lambda session, object_key: calls.append("begin") or _Live(),
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


def _history_job(object_key: str, job_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        object_key=object_key,
        dry_run=False,
        status="completed",
        summary={"allow_updates": True},
        results=[],
        file_warnings=[],
        created_at="2024-02-01T00:00:00Z",
        updated_at="2024-02-01T00:00:00Z",
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
                "admin/imports/abc-catalog.json",
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
        "https://s3.example/admin/imports/abc-catalog.json"
    )
    assert signed == [
        {
            "operation": "get_object",
            "params": {
                "Bucket": "import-bucket",
                "Key": "admin/imports/abc-catalog.json",
                "ResponseContentDisposition": (
                    'attachment; filename="abc-catalog.json"'
                ),
                "ResponseContentType": "application/json",
            },
            "expires": 900,
        }
    ]


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
