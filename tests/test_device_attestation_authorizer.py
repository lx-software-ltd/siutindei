"""Public-website credential checks for the device attestation authorizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HANDLER_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "lambda"
    / "authorizers"
    / "device_attestation"
    / "handler.py"
)

WEB_TOKEN = "w" * 40
ORIGIN_SECRET = "o" * 40


def _load_handler():
    spec = importlib.util.spec_from_file_location(
        "device_attestation_authorizer",
        HANDLER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load_handler()


def _event(
    token: str = "",
    origin: str = "",
    *,
    origin_header: str = "x-origin-verify",
) -> dict:
    headers: dict[str, str] = {}
    if token:
        headers["x-device-attestation"] = token
    if origin:
        headers[origin_header] = origin
    return {
        "headers": headers,
        "methodArn": (
            "arn:aws:execute-api:ap-southeast-1:123:api/prod/"
            "GET/v1/activities/search"
        ),
    }


def _effect(result: dict) -> str:
    return result["policyDocument"]["Statement"][0]["Effect"]


@pytest.fixture
def web_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_WWW_ATTESTATION_TOKEN", WEB_TOKEN)
    monkeypatch.setenv("PUBLIC_WWW_ORIGIN_VERIFY_SECRET", ORIGIN_SECRET)
    monkeypatch.setenv("ATTESTATION_JWKS_URL", "")
    monkeypatch.setenv("ATTESTATION_FAIL_CLOSED", "true")


def test_public_www_token_and_origin_header_allow(
    web_secrets: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_jwt(_token: str) -> dict:
        raise AssertionError("JWT verification must not run")

    monkeypatch.setattr(handler, "verify_attestation_token", fail_jwt)
    result = handler.lambda_handler(
        _event(WEB_TOKEN, ORIGIN_SECRET, origin_header="X-Origin-Verify"),
        None,
    )
    statement = result["policyDocument"]["Statement"][0]
    assert _effect(result) == "Allow"
    assert result["principalId"] == "public-www"
    assert result["context"] == {"attested": "web"}
    assert statement["Resource"].endswith("GET/v1/activities/search")


def test_public_www_token_without_origin_header_denies(web_secrets: None) -> None:
    result = handler.lambda_handler(_event(WEB_TOKEN), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "origin_verify_failed"


def test_public_www_token_with_wrong_origin_denies(web_secrets: None) -> None:
    result = handler.lambda_handler(_event(WEB_TOKEN, "x" * 40), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "origin_verify_failed"


def test_short_secrets_do_not_open_the_web_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_WWW_ATTESTATION_TOKEN", "short-token")
    monkeypatch.setenv("PUBLIC_WWW_ORIGIN_VERIFY_SECRET", "short-origin")
    monkeypatch.setenv("ATTESTATION_JWKS_URL", "")
    monkeypatch.setenv("ATTESTATION_FAIL_CLOSED", "true")
    result = handler.lambda_handler(_event("short-token", "short-origin"), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "attestation_not_configured"


def test_mobile_request_without_origin_header_keeps_fail_closed(
    web_secrets: None,
) -> None:
    result = handler.lambda_handler(_event("not-the-web-token"), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "attestation_not_configured"


def test_origin_header_alone_does_not_authorize(web_secrets: None) -> None:
    result = handler.lambda_handler(
        _event("not-the-web-token", ORIGIN_SECRET),
        None,
    )
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "attestation_not_configured"


def test_mobile_jwt_still_allowed_when_web_credentials_are_configured(
    web_secrets: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATTESTATION_JWKS_URL", "https://example.invalid/jwks")
    monkeypatch.setattr(
        handler,
        "verify_attestation_token",
        lambda _token: {"sub": "device-subject"},
    )
    result = handler.lambda_handler(_event("header.payload.signature"), None)
    assert _effect(result) == "Allow"
    assert result["principalId"] == "device-subject"
    assert result["context"] == {"attested": "true"}


def test_previous_credential_and_origin_still_allow(
    web_secrets: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_token = "p" * 40
    previous_origin = "q" * 40
    monkeypatch.setenv("PUBLIC_WWW_ATTESTATION_TOKEN_PREVIOUS", previous_token)
    monkeypatch.setenv("PUBLIC_WWW_ORIGIN_VERIFY_SECRET_PREVIOUS", previous_origin)
    current = handler.lambda_handler(_event(WEB_TOKEN, previous_origin), None)
    previous = handler.lambda_handler(_event(previous_token, ORIGIN_SECRET), None)
    both_previous = handler.lambda_handler(
        _event(previous_token, previous_origin),
        None,
    )
    assert _effect(current) == "Allow"
    assert _effect(previous) == "Allow"
    assert _effect(both_previous) == "Allow"


def test_previous_credential_without_origin_denies(
    web_secrets: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_WWW_ATTESTATION_TOKEN_PREVIOUS", "p" * 40)
    result = handler.lambda_handler(_event("p" * 40), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "origin_verify_failed"


def test_unconfigured_web_secrets_do_not_allow_empty_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PUBLIC_WWW_ATTESTATION_TOKEN", raising=False)
    monkeypatch.delenv("PUBLIC_WWW_ORIGIN_VERIFY_SECRET", raising=False)
    monkeypatch.setenv("ATTESTATION_JWKS_URL", "")
    monkeypatch.setenv("ATTESTATION_FAIL_CLOSED", "true")
    result = handler.lambda_handler(_event(), None)
    assert _effect(result) == "Deny"
    assert result["context"]["reason"] == "attestation_not_configured"
