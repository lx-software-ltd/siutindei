"""The admin content-type error carries the API Gateway request id."""

from __future__ import annotations

import json

from app.api.admin import lambda_handler


def test_content_type_problem_includes_request_id() -> None:
    """request_id in the problem body is the event request id."""
    response = lambda_handler(
        {
            "httpMethod": "POST",
            "path": "/v1/admin/organizations",
            "headers": {"Content-Type": "text/plain"},
            "requestContext": {"requestId": "req-from-the-event"},
            "body": "{}",
        },
        None,
    )
    body = json.loads(response["body"])
    assert response["statusCode"] == 400
    assert body["request_id"] == "req-from-the-event"
    assert body["title"] == "Bad Request"
