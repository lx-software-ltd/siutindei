"""Pre sign-up links a verified Google or Apple identity to the email account."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

HANDLER_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "lambda"
    / "auth"
    / "pre_signup"
    / "handler.py"
)


def _load_handler():
    spec = importlib.util.spec_from_file_location("pre_signup_handler", HANDLER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load_handler()


def _event(
    *,
    trigger: str = "PreSignUp_ExternalProvider",
    user_name: str = "Google_subject-1",
    email: str = "Manager@Example.com",
    verified: str | bool = "true",
) -> dict[str, Any]:
    return {
        "triggerSource": trigger,
        "userPoolId": "pool-1",
        "userName": user_name,
        "request": {
            "userAttributes": {
                "email": email,
                "email_verified": verified,
            }
        },
        "response": {},
    }


def _client(users: list[dict[str, Any]]) -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    class _Cognito:
        def list_users(self, **params: Any) -> dict[str, Any]:
            calls.append({"action": "list_users", **params})
            return {"Users": users}

        def admin_link_provider_for_user(self, **params: Any) -> dict[str, Any]:
            calls.append({"action": "link", **params})
            return {}

    return _Cognito(), calls


def _user(username: str, email: str = "manager@example.com") -> dict[str, Any]:
    return {
        "Username": username,
        "Attributes": [{"Name": "email", "Value": email}],
    }


def test_native_signup_does_not_call_cognito(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise AssertionError("cognito")

    monkeypatch.setattr(handler, "get_cognito_idp_client", boom)
    event = _event(trigger="PreSignUp_SignUp")

    result = handler.lambda_handler(event, None)

    assert result["response"]["autoConfirmUser"] is True
    assert result["response"]["autoVerifyEmail"] is True


def test_verified_google_sign_in_links_the_native_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client([_user("manager@example.com")])
    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: client)

    with pytest.raises(handler._ProviderLinked, match="Sign in again"):
        handler.lambda_handler(_event(), None)

    assert calls[0]["Filter"] == 'email = "manager@example.com"'
    link = calls[1]
    assert link["DestinationUser"] == {
        "ProviderName": "Cognito",
        "ProviderAttributeValue": "manager@example.com",
    }
    assert link["SourceUser"]["ProviderName"] == "Google"
    assert link["SourceUser"]["ProviderAttributeValue"] == "subject-1"


def test_apple_sign_in_uses_the_provider_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client([_user("manager@example.com")])
    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: client)

    with pytest.raises(handler._ProviderLinked):
        handler.lambda_handler(
            _event(user_name="SignInWithApple_apple-subject"),
            None,
        )

    assert calls[1]["SourceUser"]["ProviderName"] == "SignInWithApple"
    assert calls[1]["SourceUser"]["ProviderAttributeValue"] == "apple-subject"


def test_unverified_email_is_not_linked(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise AssertionError("cognito")

    monkeypatch.setattr(handler, "get_cognito_idp_client", boom)
    event = _event(verified="false")

    result = handler.lambda_handler(event, None)

    assert result["response"]["autoConfirmUser"] is True


def test_missing_native_account_continues_signup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client([])
    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: client)

    result = handler.lambda_handler(_event(), None)

    assert result["response"]["autoConfirmUser"] is True
    assert [call["action"] for call in calls] == ["list_users"]


def test_several_native_accounts_are_not_linked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client(
        [
            _user("native-one", "one@example.com"),
            _user("native-two", "one@example.com"),
        ]
    )
    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: client)

    result = handler.lambda_handler(_event(email="one@example.com"), None)

    assert result["response"]["autoConfirmUser"] is True
    assert [call["action"] for call in calls] == ["list_users"]


def test_a_provider_account_alone_is_not_linked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, calls = _client([_user("Google_existing", "manager@example.com")])
    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: client)

    result = handler.lambda_handler(_event(), None)

    assert result["response"]["autoConfirmUser"] is True
    assert [call["action"] for call in calls] == ["list_users"]


def test_quoted_email_is_not_looked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise AssertionError("cognito")

    monkeypatch.setattr(handler, "get_cognito_idp_client", boom)

    result = handler.lambda_handler(_event(email='bad"quote@example.com'), None)

    assert result["response"]["autoConfirmUser"] is True


def test_link_failure_does_not_block_signup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cognito:
        def list_users(self, **_params: Any) -> dict[str, Any]:
            return {"Users": [_user("manager@example.com")]}

        def admin_link_provider_for_user(self, **_params: Any) -> dict[str, Any]:
            raise RuntimeError("link failed")

    monkeypatch.setattr(handler, "get_cognito_idp_client", lambda: _Cognito())

    result = handler.lambda_handler(_event(), None)

    assert result["response"]["autoConfirmUser"] is True
