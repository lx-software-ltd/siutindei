"""Tests for partner API-key routes and context parsing."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

import app.api.admin as admin_module  # noqa: E402
from app.api.admin import _handle_partner_routes  # noqa: E402
from app.api.admin_request import _parse_path  # noqa: E402
from app.api.partner_auth import get_partner_context  # noqa: E402
from app.api.search import _is_partner_path  # noqa: E402


def _partner_event(
    method: str,
    path: str,
    scope: str | None = "crud",
    org_id: str = "",
) -> dict:
    authorizer: dict = {}
    if scope is not None:
        key_id = str(uuid4())
        authorizer = {
            "apiKeyId": key_id,
            "scope": scope,
            "orgId": org_id,
            "userSub": f"api-key:{key_id}",
        }
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "body": "{}",
        "requestContext": {"requestId": "req-1", "authorizer": authorizer},
    }


# --- get_partner_context ---


def test_partner_context_parsed_from_authorizer() -> None:
    """Authorizer context maps to a PartnerContext."""
    org_id = str(uuid4())
    event = _partner_event("GET", "/v1/partner/activities", "crud", org_id)
    context = get_partner_context(event)
    assert context is not None
    assert context.scope == "crud"
    assert context.org_id == org_id


def test_partner_context_none_without_key() -> None:
    """Events without API-key context yield no partner context."""
    event = _partner_event("GET", "/v1/partner/activities", scope=None)
    assert get_partner_context(event) is None


def test_partner_context_none_with_invalid_scope() -> None:
    """Unknown scopes are treated as unauthorized."""
    event = _partner_event("GET", "/v1/partner/activities", "superuser")
    assert get_partner_context(event) is None


def test_partner_context_full_access_has_no_org() -> None:
    """An empty orgId means full access."""
    event = _partner_event("GET", "/v1/partner/activities", "read", "")
    context = get_partner_context(event)
    assert context is not None
    assert context.org_id is None


# --- path parsing ---


def test_parse_path_supports_partner_base() -> None:
    """/v1/partner paths parse into the partner base path."""
    assert _parse_path("/v1/partner/activities") == (
        "partner",
        "activities",
        None,
        None,
    )
    resource_id = str(uuid4())
    assert _parse_path(f"/v1/partner/pricing/{resource_id}") == (
        "partner",
        "pricing",
        resource_id,
        None,
    )


def test_is_partner_path() -> None:
    """Partner search paths are detected with or without version prefix."""
    assert _is_partner_path("/v1/partner/activities/search")
    assert _is_partner_path("/partner/activities/search")
    assert not _is_partner_path("/v1/activities/search")


# --- partner route authorization ---


def test_partner_routes_forbidden_without_context() -> None:
    """Requests without an API-key context are rejected."""
    event = _partner_event("GET", "/v1/partner/activities", scope=None)
    response = _handle_partner_routes(event, "GET", "activities", None)
    assert response["statusCode"] == 403


def test_partner_routes_read_key_cannot_write() -> None:
    """A read-scoped key cannot POST/PUT/DELETE."""
    for method in ("POST", "PUT", "DELETE"):
        event = _partner_event(method, "/v1/partner/activities", "read")
        response = _handle_partner_routes(event, method, "activities", None)
        assert response["statusCode"] == 403


def test_partner_routes_unknown_resource_404() -> None:
    """Resources outside the partner set return 404."""
    event = _partner_event("GET", "/v1/partner/cognito-users", "crud")
    response = _handle_partner_routes(event, "GET", "cognito-users", None)
    assert response["statusCode"] == 404


def test_partner_routes_api_keys_not_reachable() -> None:
    """Partner keys can never manage API keys."""
    event = _partner_event("GET", "/v1/partner/api-keys", "crud")
    response = _handle_partner_routes(event, "GET", "api-keys", None)
    assert response["statusCode"] == 404


def test_org_scoped_key_cannot_create_organizations() -> None:
    """Org-scoped keys cannot POST /v1/partner/organizations."""
    event = _partner_event(
        "POST", "/v1/partner/organizations", "crud", str(uuid4())
    )
    response = _handle_partner_routes(event, "POST", "organizations", None)
    assert response["statusCode"] == 403


def test_partner_routes_pass_org_scope_to_crud(monkeypatch) -> None:
    """Org-scoped keys filter CRUD by their organization."""
    org_id = str(uuid4())
    captured: dict = {}

    def fake_crud(event, method, config, resource_id, managed_org_ids=None):
        captured["managed_org_ids"] = managed_org_ids
        return {"statusCode": 200, "body": "{}"}

    monkeypatch.setattr(admin_module, "_handle_crud", fake_crud)
    event = _partner_event("GET", "/v1/partner/locations", "crud", org_id)
    response = _handle_partner_routes(event, "GET", "locations", None)
    assert response["statusCode"] == 200
    assert captured["managed_org_ids"] == {org_id}


def test_full_access_key_has_no_org_filter(monkeypatch) -> None:
    """Full-access keys behave like admin CRUD (no org filter)."""
    captured: dict = {}

    def fake_crud(event, method, config, resource_id, managed_org_ids=None):
        captured["managed_org_ids"] = managed_org_ids
        return {"statusCode": 200, "body": "{}"}

    monkeypatch.setattr(admin_module, "_handle_crud", fake_crud)
    event = _partner_event("POST", "/v1/partner/organizations", "crud", "")
    response = _handle_partner_routes(event, "POST", "organizations", None)
    assert response["statusCode"] == 200
    assert captured["managed_org_ids"] is None


def test_read_key_can_list_resources(monkeypatch) -> None:
    """Read-scoped keys may perform GET on partner resources."""
    monkeypatch.setattr(
        admin_module,
        "_handle_crud",
        lambda *args, **kwargs: {"statusCode": 200, "body": "{}"},
    )
    event = _partner_event("GET", "/v1/partner/schedules", "read")
    response = _handle_partner_routes(event, "GET", "schedules", None)
    assert response["statusCode"] == 200
