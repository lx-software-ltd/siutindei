"""Live import jobs commit running before work and failed after errors."""

from __future__ import annotations

import json

from app.api.admin_imports import _handle_import_process


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
        lambda session, job_id, error_type: order.append(f"fail:{job_id}:{error_type}"),
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
