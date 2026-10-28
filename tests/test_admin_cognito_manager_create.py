"""Tests for POST /v1/admin/cognito-users."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.api import admin_cognito
from app.api.admin import lambda_handler
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError

SUB = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
EMAIL = "new.manager@example.com"
SECRET = "Aa1!sentinel-secret-value"


def _list_user(
    email: str = EMAIL,
    *,
    status: str = "CONFIRMED",
    sub: str = SUB,
) -> dict[str, Any]:
    return {
        "Username": email,
        "UserStatus": status,
        "Enabled": True,
        "UserCreateDate": "2024-01-01T00:00:00+00:00",
        "UserLastModifiedDate": "2024-01-02T00:00:00+00:00",
        "Attributes": [
            {"Name": "sub", "Value": sub},
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
    }


def _admin_get(user: dict[str, Any], *, status: str = "CONFIRMED") -> dict[str, Any]:
    return {
        "Username": user["Username"],
        "UserStatus": status,
        "Enabled": True,
        "UserCreateDate": user["UserCreateDate"],
        "UserLastModifiedDate": user["UserLastModifiedDate"],
        "UserAttributes": user["Attributes"],
    }


def _event(body: dict[str, Any] | None, *, groups: str = "admin") -> dict[str, Any]:
    return {
        "httpMethod": "POST",
        "path": "/v1/admin/cognito-users",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body is not None else "",
        "requestContext": {
            "requestId": "req-1",
            "authorizer": {"groups": groups, "userSub": "admin-sub"},
        },
    }


@pytest.fixture(autouse=True)
def _cognito_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-1")
    monkeypatch.delenv("ADMIN_GROUP", raising=False)
    monkeypatch.delenv("MANAGER_GROUP", raising=False)


def _patch_proxy(monkeypatch: pytest.MonkeyPatch, responder) -> list[tuple]:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_proxy(service: str, action: str, params: dict) -> dict:
        assert service == "cognito-idp"
        calls.append((action, params))
        return responder(action, params)

    monkeypatch.setattr(admin_cognito, "aws_proxy", fake_proxy)
    return calls


def _body(response: dict[str, Any]) -> dict[str, Any]:
    return json.loads(response["body"])


def test_confirmation_secret_meets_pool_policy() -> None:
    secret = admin_cognito._passwordless_confirmation_secret()
    assert len(secret) >= 12
    assert any(char.islower() for char in secret)
    assert any(char.isupper() for char in secret)
    assert any(char.isdigit() for char in secret)
    assert any(char in admin_cognito._PASSWORD_SYMBOLS for char in secret)


def test_create_confirms_user_and_grants_manager(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        admin_cognito,
        "_passwordless_confirmation_secret",
        lambda: SECRET,
    )
    created = _list_user(status="FORCE_CHANGE_PASSWORD")

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            return {"Users": []}
        if action == "admin_create_user":
            assert params["MessageAction"] == "SUPPRESS"
            assert params["Username"] == EMAIL
            return {"User": created}
        if action == "admin_set_user_password":
            assert params["Permanent"] is True
            assert params["Password"] == SECRET
            return {}
        if action == "admin_get_user":
            return _admin_get(created)
        if action == "admin_list_groups_for_user":
            return {"Groups": []}
        if action in {"admin_add_user_to_group", "admin_user_global_sign_out"}:
            return {}
        raise AssertionError(action)

    calls = _patch_proxy(monkeypatch, responder)

    with caplog.at_level("INFO"):
        response = admin_cognito._handle_create_cognito_manager(
            _event({"email": "  New.Manager@Example.com  "})
        )

    actions = [action for action, _ in calls]
    assert actions == [
        "list_users",
        "admin_create_user",
        "admin_set_user_password",
        "admin_get_user",
        "admin_list_groups_for_user",
        "admin_add_user_to_group",
        "admin_user_global_sign_out",
    ]
    body = _body(response)
    assert response["statusCode"] == 200
    assert body["sub"] == SUB
    assert body["email"] == EMAIL
    assert body["groups"] == ["manager"]
    assert body["status"] == "CONFIRMED"
    assert SECRET not in response["body"]
    assert SECRET not in caplog.text


def test_existing_confirmed_user_keeps_password_and_gains_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _list_user()

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            return {"Users": [existing]}
        if action == "admin_list_groups_for_user":
            return {"Groups": [{"GroupName": "admin"}]}
        if action in {"admin_add_user_to_group", "admin_user_global_sign_out"}:
            return {}
        raise AssertionError(action)

    calls = _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_create_cognito_manager(_event({"email": EMAIL}))

    actions = [action for action, _ in calls]
    assert "admin_create_user" not in actions
    assert "admin_set_user_password" not in actions
    assert _body(response)["groups"] == ["admin", "manager"]


def test_existing_manager_is_not_signed_out(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _list_user()

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            return {"Users": [existing]}
        if action == "admin_list_groups_for_user":
            return {"Groups": [{"GroupName": "manager"}, {"GroupName": "other"}]}
        raise AssertionError(action)

    calls = _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_create_cognito_manager(_event({"email": EMAIL}))

    actions = [action for action, _ in calls]
    assert actions == ["list_users", "admin_list_groups_for_user"]
    assert _body(response)["groups"] == ["manager"]


def test_unconfirmed_existing_user_is_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _list_user(status="FORCE_CHANGE_PASSWORD")

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            return {"Users": [existing]}
        if action == "admin_set_user_password":
            return {}
        if action == "admin_get_user":
            return _admin_get(existing)
        if action == "admin_list_groups_for_user":
            return {"Groups": [{"GroupName": "manager"}]}
        raise AssertionError(action)

    calls = _patch_proxy(monkeypatch, responder)

    admin_cognito._handle_create_cognito_manager(_event({"email": EMAIL}))

    actions = [action for action, _ in calls]
    assert actions.index("admin_set_user_password") < actions.index("admin_get_user")
    assert "admin_add_user_to_group" not in actions


def test_username_exists_reuses_the_account(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _list_user()
    lookups = {"count": 0}

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            lookups["count"] += 1
            if lookups["count"] == 1:
                return {"Users": []}
            return {"Users": [existing]}
        if action == "admin_create_user":
            raise AwsProxyError("UsernameExistsException", "exists")
        if action == "admin_list_groups_for_user":
            return {"Groups": [{"GroupName": "manager"}]}
        raise AssertionError(action)

    _patch_proxy(monkeypatch, responder)

    response = admin_cognito._handle_create_cognito_manager(_event({"email": EMAIL}))

    assert response["statusCode"] == 200
    assert _body(response)["sub"] == SUB


def test_invalid_email_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_proxy(monkeypatch, lambda action, params: {})
    with pytest.raises(ValidationError):
        admin_cognito._handle_create_cognito_manager(_event({"email": "not-an-email"}))
    assert calls == []


def test_quoted_email_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_proxy(monkeypatch, lambda action, params: {})
    with pytest.raises(ValidationError):
        admin_cognito._handle_create_cognito_manager(
            _event({"email": 'bad"quote@example.com'})
        )
    assert calls == []


def test_missing_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        admin_cognito._handle_create_cognito_manager(_event({}))


def test_manager_group_cannot_create_accounts() -> None:
    response = lambda_handler(_event({"email": EMAIL}, groups="manager"), None)
    assert response["statusCode"] == 403


def test_admin_route_creates_a_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    created = _list_user(status="FORCE_CHANGE_PASSWORD")

    def responder(action: str, params: dict) -> dict:
        if action == "list_users":
            return {"Users": []}
        if action == "admin_create_user":
            return {"User": created}
        if action == "admin_set_user_password":
            return {}
        if action == "admin_get_user":
            return _admin_get(created)
        if action == "admin_list_groups_for_user":
            return {"Groups": []}
        if action in {"admin_add_user_to_group", "admin_user_global_sign_out"}:
            return {}
        raise AssertionError(action)

    _patch_proxy(monkeypatch, responder)

    response = lambda_handler(_event({"email": EMAIL}), None)

    assert response["statusCode"] == 200
    assert _body(response)["groups"] == ["manager"]
