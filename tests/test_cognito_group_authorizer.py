"""Path-gate tests for the shared Cognito group authorizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

HANDLER_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "lambda"
    / "authorizers"
    / "cognito_group"
    / "handler.py"
)


def _load_handler():
    spec = importlib.util.spec_from_file_location(
        "cognito_group_authorizer",
        HANDLER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load_handler()


def _arn(method: str, *path: str) -> str:
    suffix = "/".join((method, *path))
    return f"arn:aws:execute-api:ap-southeast-1:123:api/prod/{suffix}"


@pytest.mark.parametrize(
    ("method_arn", "allowed"),
    [
        (_arn("POST", "v1", "admin", "imports"), True),
        (_arn("POST", "v1", "admin", "imports", "presign"), True),
        (_arn("GET", "v1", "admin", "imports"), False),
        (
            _arn(
                "GET",
                "v1",
                "admin",
                "imports",
                "00000000-0000-0000-0000-000000000011",
            ),
            True,
        ),
        (_arn("GET", "v1", "admin", "imports", "export"), False),
        (_arn("POST", "v1", "admin", "imports", "export"), False),
        (_arn("GET", "v1", "admin", "organizations"), True),
        (
            _arn(
                "PATCH",
                "v1",
                "admin",
                "organizations",
                "00000000-0000-0000-0000-000000000001",
            ),
            True,
        ),
        (
            _arn(
                "ANY",
                "v1",
                "admin",
                "organizations",
                "00000000-0000-0000-0000-000000000001",
            ),
            True,
        ),
        (_arn("GET", "v1", "admin", "users"), False),
        ("arn:aws:execute-api:ap-southeast-1:123:api", False),
    ],
)
def test_importer_path_allowed(method_arn: str, allowed: bool) -> None:
    assert handler._importer_path_allowed(method_arn) is allowed


def test_importer_allowed_on_import_post(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_GROUPS", "admin")
    monkeypatch.setenv("IMPORTER_GROUP", "importer")
    monkeypatch.setattr(
        handler,
        "decode_and_verify_token",
        lambda _token: SimpleNamespace(
            sub="importer-user",
            email="imp@example.com",
            groups=["importer"],
        ),
    )
    event = {
        "headers": {"Authorization": "Bearer token"},
        "methodArn": _arn("POST", "v1", "admin", "imports"),
    }
    response = handler.lambda_handler(event, None)
    statement = response["policyDocument"]["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert _arn("POST", "v1", "admin", "imports") in statement["Resource"]
    assert _arn("POST", "v1", "admin", "imports", "presign") in statement[
        "Resource"
    ]
    assert _arn("GET", "v1", "admin", "imports", "*") in statement["Resource"]
    assert _arn("GET", "v1", "admin", "organizations") in statement["Resource"]
    assert _arn("PATCH", "v1", "admin", "organizations", "*") in statement[
        "Resource"
    ]
    assert not any(str(item).endswith("/prod/*") for item in statement["Resource"])


def test_admin_allow_policy_is_still_broadened(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_GROUPS", "admin")
    monkeypatch.setenv("IMPORTER_GROUP", "importer")
    monkeypatch.setattr(
        handler,
        "decode_and_verify_token",
        lambda _token: SimpleNamespace(
            sub="admin-user",
            email="admin@example.com",
            groups=["admin"],
        ),
    )
    event = {
        "headers": {"Authorization": "Bearer token"},
        "methodArn": _arn("GET", "v1", "admin", "organizations"),
    }
    response = handler.lambda_handler(event, None)
    statement = response["policyDocument"]["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert statement["Resource"].endswith("/*")


def test_importer_denied_on_other_admin_route(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_GROUPS", "admin")
    monkeypatch.setenv("IMPORTER_GROUP", "importer")
    monkeypatch.setattr(
        handler,
        "decode_and_verify_token",
        lambda _token: SimpleNamespace(
            sub="importer-user",
            email="imp@example.com",
            groups=["importer"],
        ),
    )
    event = {
        "headers": {"Authorization": "Bearer token"},
        "methodArn": _arn("GET", "v1", "admin", "users"),
    }
    response = handler.lambda_handler(event, None)
    assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"
