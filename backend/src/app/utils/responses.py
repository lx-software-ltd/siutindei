"""Shared response utilities for Lambda handlers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any
from typing import Mapping
from typing import Optional

from pydantic import BaseModel

from app.exceptions import ValidationError


def validate_content_type(
    event: Mapping[str, Any],
    required_methods: tuple[str, ...] = ("POST", "PUT", "PATCH"),
) -> None:
    """Validate Content-Type header for requests that require a body.

    SECURITY: This prevents content-type confusion attacks and ensures
    the server only processes requests with the expected content type.

    Args:
        event: The Lambda event containing headers and method.
        required_methods: HTTP methods that require Content-Type validation.

    Raises:
        ValidationError: If Content-Type is missing or not application/json.
    """
    method = event.get("httpMethod", "")
    if method not in required_methods:
        return

    headers = event.get("headers") or {}

    # Get Content-Type header case-insensitively
    content_type = None
    for key, value in headers.items():
        if key.lower() == "content-type":
            content_type = str(value).lower().strip()
            break

    if not content_type:
        raise ValidationError(
            "Content-Type header is required for requests with a body",
            field="Content-Type",
        )

    # Check if it's JSON (allowing for charset parameters like "application/json; charset=utf-8")
    if not content_type.startswith("application/json"):
        raise ValidationError(
            "Content-Type must be application/json",
            field="Content-Type",
        )


def get_security_headers() -> dict[str, str]:
    """Get security headers for all responses.

    SECURITY: These headers protect against common web vulnerabilities:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables browser XSS filter (legacy)
    - Cache-Control: Prevents caching of sensitive data

    Returns:
        Dictionary of security headers.
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }


# Default CORS origins for local development
_DEFAULT_CORS_ORIGINS = [
    "capacitor://localhost",
    "ionic://localhost",
    "http://localhost",
    "http://localhost:3000",
    "https://siutindei.lx-software.com",
    "https://siutindei-api.lx-software.com",
]


def get_cors_headers(
    event: Optional[Mapping[str, Any]] = None,
) -> dict[str, str]:
    """Get CORS headers for the response.

    Args:
        event: The Lambda event containing the request origin header.

    Returns:
        Dictionary of CORS headers to include in the response.
    """
    # Get allowed origins from environment or use defaults
    allowed_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if allowed_origins_env:
        allowed_origins = [
            origin.strip()
            for origin in allowed_origins_env.split(",")
            if origin.strip()
        ]
    else:
        allowed_origins = _DEFAULT_CORS_ORIGINS

    # Get the request origin
    request_origin = None
    if event:
        headers = event.get("headers") or {}
        # Headers may be case-insensitive, check both
        request_origin = headers.get("origin") or headers.get("Origin")

    # If the request origin is in our allowed list, return it
    # Otherwise, return the first allowed origin (for non-browser clients)
    if request_origin and request_origin in allowed_origins:
        allow_origin = request_origin
    elif allowed_origins:
        # For requests without an Origin header (like curl), we can't
        # return a specific origin. Return the first one for preflight
        # compatibility, but browsers will handle this correctly.
        allow_origin = allowed_origins[0]
    else:
        allow_origin = "*"

    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Headers": (
            "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token"
        ),
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }


def json_response(
    status_code: int,
    body: Any,
    headers: Optional[dict[str, str]] = None,
    event: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Create a JSON API Gateway response.

    Args:
        status_code: HTTP status code.
        body: Response body (dict, Pydantic model, or dataclass).
        headers: Optional additional headers to include.
        event: Optional Lambda event for CORS origin detection.

    Returns:
        API Gateway response dictionary.
    """
    response_headers = {
        "Content-Type": "application/json",
    }

    # Add security headers
    response_headers.update(get_security_headers())

    # Add CORS headers
    response_headers.update(get_cors_headers(event))

    if headers:
        response_headers.update(headers)

    payload = _serialize_body(body)

    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": json.dumps(payload, default=str),
    }


def text_response(
    status_code: int,
    body: str,
    *,
    content_type: str,
    event: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """API Gateway response whose body is already text."""
    headers = {"Content-Type": content_type}
    headers.update(get_security_headers())
    headers.update(get_cors_headers(event))
    return {"statusCode": status_code, "headers": headers, "body": body}


def _serialize_body(body: Any) -> Any:
    """Serialize response body to JSON-compatible format.

    Args:
        body: The body to serialize.

    Returns:
        JSON-serializable representation of the body.
    """
    if isinstance(body, BaseModel):
        if hasattr(body, "model_dump"):
            return body.model_dump()
        return body.dict()

    if hasattr(body, "__dataclass_fields__"):
        return asdict(body)

    return body


def error_response(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    event: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Create an error response.

    Args:
        status_code: HTTP status code.
        message: Error message.
        detail: Optional additional detail.
        event: Optional Lambda event for CORS origin detection.

    Returns:
        API Gateway response dictionary.
    """
    body: dict[str, Any] = {"error": message}
    if detail:
        body["detail"] = detail

    return json_response(status_code, body, event=event)
