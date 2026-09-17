"""Route-gate tests for the importer Cognito group."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.api.admin import lambda_handler


def _event(
    path: str,
    *,
    method: str = "POST",
    groups: str = "importer",
) -> dict:
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {
                "groups": groups,
                "userSub": "importer-user",
            },
        },
        "body": json.dumps(
            {
                "file_name": "a.json",
                "content_type": "application/json",
            }
        ),
    }


def _ok_response() -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"ok": True}),
    }


@patch("app.api.admin._handle_admin_imports", return_value=_ok_response())
def test_importer_can_presign(mock_imports) -> None:
    response = lambda_handler(
        _event("/v1/admin/imports/presign"),
        None,
    )
    assert response["statusCode"] == 200
    mock_imports.assert_called_once()


@patch("app.api.admin._handle_admin_imports", return_value=_ok_response())
def test_importer_can_process_import(mock_imports) -> None:
    response = lambda_handler(
        _event("/v1/admin/imports"),
        None,
    )
    assert response["statusCode"] == 200
    mock_imports.assert_called_once()


@patch("app.api.admin._handle_admin_imports")
def test_importer_cannot_export(mock_imports) -> None:
    response = lambda_handler(
        _event("/v1/admin/imports/export", method="GET"),
        None,
    )
    assert response["statusCode"] == 403
    mock_imports.assert_not_called()


@patch("app.api.admin._handle_crud")
def test_importer_cannot_list_organizations(mock_crud) -> None:
    response = lambda_handler(
        _event("/v1/admin/organizations", method="GET"),
        None,
    )
    assert response["statusCode"] == 403
    mock_crud.assert_not_called()


@patch("app.api.admin._handle_admin_imports", return_value=_ok_response())
def test_admin_can_still_import(mock_imports) -> None:
    response = lambda_handler(
        _event("/v1/admin/imports", groups="admin"),
        None,
    )
    assert response["statusCode"] == 200
    mock_imports.assert_called_once()


def _process_event(*, groups: str, dry_run: bool) -> dict:
    return {
        "httpMethod": "POST",
        "path": "/v1/admin/imports",
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {
                "groups": groups,
                "userSub": "caller-sub",
            },
        },
        "body": json.dumps(
            {
                "object_key": "admin/imports/file.json",
                "dry_run": dry_run,
            }
        ),
    }


def test_importer_process_is_create_only_and_skips_audit(
    monkeypatch,
) -> None:
    captured: dict = {}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def rollback(self):
            captured["rolled_back"] = True

    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _Session(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports._load_import_payload",
        lambda key: {"organizations": []},
    )

    def fake_process(
        session,
        payload,
        warnings,
        dry_run=False,
        allow_org_updates=True,
    ):
        captured["allow_org_updates"] = allow_org_updates
        captured["dry_run"] = dry_run
        return {"warnings": 0}, []

    monkeypatch.setattr(
        "app.api.admin_imports.process_import_payload",
        fake_process,
    )
    audit_calls: list[bool] = []
    monkeypatch.setattr(
        "app.api.admin_imports._set_session_audit_context",
        lambda session, event: audit_calls.append(True),
    )

    from app.api.admin_imports import _handle_import_process

    response = _handle_import_process(
        _process_event(groups="importer", dry_run=True)
    )
    assert response["statusCode"] == 200
    assert captured["allow_org_updates"] is False
    assert captured["dry_run"] is True
    assert captured.get("rolled_back") is True
    assert audit_calls == []


def test_admin_process_allows_updates_and_sets_audit(
    monkeypatch,
) -> None:
    captured: dict = {}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def rollback(self):
            captured["rolled_back"] = True

    monkeypatch.setattr(
        "app.api.admin_imports.Session",
        lambda *args, **kwargs: _Session(),
    )
    monkeypatch.setattr("app.api.admin_imports.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_imports._load_import_payload",
        lambda key: {"organizations": []},
    )

    def fake_process(
        session,
        payload,
        warnings,
        dry_run=False,
        allow_org_updates=False,
    ):
        captured["allow_org_updates"] = allow_org_updates
        captured["dry_run"] = dry_run
        return {"warnings": 0}, []

    monkeypatch.setattr(
        "app.api.admin_imports.process_import_payload",
        fake_process,
    )
    audit_calls: list[bool] = []
    monkeypatch.setattr(
        "app.api.admin_imports._set_session_audit_context",
        lambda session, event: audit_calls.append(True),
    )

    from app.api.admin_imports import _handle_import_process

    response = _handle_import_process(
        _process_event(groups="admin", dry_run=False)
    )
    assert response["statusCode"] == 200
    assert captured["allow_org_updates"] is True
    assert captured["dry_run"] is False
    assert "rolled_back" not in captured
    assert audit_calls == [True]
