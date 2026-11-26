"""Tests for the partner API-key request authorizer."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

import app.auth.api_key_authorizer as authorizer_module  # noqa: E402
from app.auth.api_key_authorizer import authorize_api_key  # noqa: E402
from app.services.api_keys import generate_api_key  # noqa: E402

METHOD_ARN = "arn:aws:execute-api:eu-west-1:123:api/prod/GET/v1/partner"


def _event(headers: dict | None = None) -> dict:
    return {"headers": headers or {}, "methodArn": METHOD_ARN}


def _bearer(token: str, name: str = "Authorization") -> dict[str, str]:
    return {name: f"Bearer {token}"}


class FakeSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class FakeRepo:
    def __init__(self, api_key) -> None:
        self._api_key = api_key
        self.touched = False

    def find_active_by_hash(self, key_hash: str):
        return self._api_key

    def touch_last_used(self, api_key) -> None:
        self.touched = True


def _install_fakes(monkeypatch, api_key) -> FakeRepo:
    repo = FakeRepo(api_key)

    @contextmanager
    def fake_session(engine):
        yield FakeSession()

    monkeypatch.setattr(authorizer_module, "Session", fake_session)
    monkeypatch.setattr(authorizer_module, "get_engine", lambda: None)
    monkeypatch.setattr(authorizer_module, "ApiKeyRepository", lambda session: repo)
    return repo


def _statement_effect(response: dict) -> str:
    return response["policyDocument"]["Statement"][0]["Effect"]


def test_missing_header_denied() -> None:
    """Requests without an Authorization bearer token are denied."""
    response = authorize_api_key(_event())
    assert _statement_effect(response) == "Deny"
    assert response["context"]["reason"] == "missing_key"


def test_malformed_key_denied_without_db() -> None:
    """Malformed keys are denied before any database lookup."""
    response = authorize_api_key(_event(_bearer("wrong-format")))
    assert _statement_effect(response) == "Deny"
    assert response["context"]["reason"] == "invalid_key"


def test_unknown_key_denied(monkeypatch) -> None:
    """Keys that don't match an active row are denied."""
    _install_fakes(monkeypatch, api_key=None)
    plaintext = generate_api_key().plaintext
    response = authorize_api_key(_event(_bearer(plaintext)))
    assert _statement_effect(response) == "Deny"
    assert response["context"]["reason"] == "invalid_key"


def test_valid_key_allowed_with_context(monkeypatch) -> None:
    """Valid keys yield an Allow policy carrying the key identity."""
    key_id = uuid4()
    org_id = uuid4()
    api_key = SimpleNamespace(
        id=key_id,
        scope="crud",
        org_id=org_id,
        last_used_at=None,
    )
    repo = _install_fakes(monkeypatch, api_key)

    plaintext = generate_api_key().plaintext
    response = authorize_api_key(
        _event(_bearer(plaintext, "authorization"))  # header lookup is case-insensitive
    )
    assert _statement_effect(response) == "Allow"
    context = response["context"]
    assert context["apiKeyId"] == str(key_id)
    assert context["scope"] == "crud"
    assert context["orgId"] == str(org_id)
    assert context["userSub"] == f"api-key:{key_id}"
    assert repo.touched is True


def test_full_access_key_has_empty_org(monkeypatch) -> None:
    """Full-access keys pass an empty orgId in the context."""
    api_key = SimpleNamespace(
        id=uuid4(),
        scope="read",
        org_id=None,
        last_used_at=None,
    )
    _install_fakes(monkeypatch, api_key)
    plaintext = generate_api_key().plaintext
    response = authorize_api_key(_event(_bearer(plaintext)))
    assert _statement_effect(response) == "Allow"
    assert response["context"]["orgId"] == ""


def test_recent_last_used_not_touched(monkeypatch) -> None:
    """last_used_at updates are throttled."""
    api_key = SimpleNamespace(
        id=uuid4(),
        scope="read",
        org_id=None,
        last_used_at=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    repo = _install_fakes(monkeypatch, api_key)
    plaintext = generate_api_key().plaintext
    response = authorize_api_key(_event(_bearer(plaintext)))
    assert _statement_effect(response) == "Allow"
    assert repo.touched is False
