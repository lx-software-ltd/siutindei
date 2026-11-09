"""Search Lambda handler with API Gateway REST proxy events."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.api.partner_auth import SCOPE_READ
from app.api.search import lambda_handler
from app.services import staging_search_store


@pytest.fixture(autouse=True)
def enable_staging_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def _event(
    path: str = "/v1/activities/search",
    query: dict[str, list[str]] | None = None,
    authorizer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    multi = query or {"limit": ["2"]}
    return {
        "resource": path,
        "path": path,
        "httpMethod": "GET",
        "headers": {"origin": "https://siutindei.lx-software.com"},
        "queryStringParameters": {key: values[-1] for key, values in multi.items()},
        "multiValueQueryStringParameters": multi,
        "requestContext": {"requestId": "req-1", "authorizer": authorizer or {}},
        "body": None,
    }


def test_public_search_is_cacheable_at_the_edge() -> None:
    response = lambda_handler(_event(), None)

    assert response["statusCode"] == 200
    headers = response["headers"]
    assert headers["Cache-Control"] == "public, max-age=60, s-maxage=300"
    assert "Pragma" not in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Access-Control-Allow-Origin"] == (
        "https://siutindei.lx-software.com"
    )
    body = json.loads(response["body"])
    assert 0 < len(body["items"]) <= 2
    assert all("manager_id" not in item["organization"] for item in body["items"])


@pytest.mark.parametrize(
    "origin", ["https://admin.siutindei.com", "https://api.siutindei.com"]
)
def test_siutindei_com_hosts_are_default_cors_origins(
    origin: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    event = _event()
    event["headers"] = {"origin": origin}

    response = lambda_handler(event, None)

    assert response["headers"]["Access-Control-Allow-Origin"] == origin


def test_card_view_response_is_cacheable() -> None:
    response = lambda_handler(_event(query={"limit": ["1"], "view": ["card"]}), None)

    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"].startswith("public,")


def test_invalid_query_is_not_cached() -> None:
    response = lambda_handler(_event(query={"age": ["-5"]}), None)

    assert response["statusCode"] == 400
    assert response["headers"]["Cache-Control"].startswith("no-store")


def test_partner_search_is_not_cached() -> None:
    response = lambda_handler(
        _event(
            path="/v1/partner/activities/search",
            authorizer={"apiKeyId": "key-1", "scope": SCOPE_READ},
        ),
        None,
    )

    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"].startswith("no-store")


def test_partner_search_without_key_context_is_forbidden() -> None:
    response = lambda_handler(_event(path="/v1/partner/activities/search"), None)

    assert response["statusCode"] == 403
    assert response["headers"]["Cache-Control"].startswith("no-store")
