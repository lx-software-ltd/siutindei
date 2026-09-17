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
