"""HTTP /health is a liveness probe and does not open the database."""

from __future__ import annotations

import json

import app.db.engine as engine_module
from app.api.health import lambda_handler


def test_http_health_returns_ok_without_a_database_connection(monkeypatch) -> None:
    """A gateway event returns status ok and never asks for an engine."""

    def fail_engine(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("HTTP /health must not open a database connection")

    monkeypatch.setattr(engine_module, "get_engine", fail_engine)
    response = lambda_handler(
        {
            "httpMethod": "GET",
            "path": "/health",
            "requestContext": {"httpMethod": "GET", "requestId": "health-req"},
        },
        None,
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ok"}
