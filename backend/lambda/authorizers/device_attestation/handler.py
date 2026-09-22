"""API Gateway request authorizer for device attestation.

This Lambda validates device attestation tokens for mobile API requests,
ensuring only legitimate app instances can access the API.

The public website cannot mint a Firebase App Check JWT. It sends a static
token as ``x-device-attestation``. That token is accepted only when CloudFront
also injected ``x-origin-verify`` (a secret the browser never sees). Mobile
JWTs do not need the origin header.

SECURITY NOTES:
- In production, ATTESTATION_FAIL_CLOSED should be "true" to deny requests
  when attestation is not configured.
- Setting ATTESTATION_FAIL_CLOSED to "false" is only for development/testing.
- Do not add ``x-origin-verify`` as an API Gateway identity source. Mobile
  clients omit it, and a missing identity source is rejected with 401 before
  this function runs.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from app.auth.authorizer_helpers import get_header, policy
from app.auth.attestation import (
    is_attestation_enabled,
    verify_attestation_token,
)
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# Reject accidentally short secrets. CDK parameters use the same minimum.
_MIN_SECRET_LENGTH = 32
_WEB_CREDENTIAL_ENV = "PUBLIC_WWW_ATTESTATION_TOKEN"
_ORIGIN_VERIFY_ENV = "PUBLIC_WWW_ORIGIN_VERIFY_SECRET"
_ORIGIN_HEADER = "x-origin-verify"


def _is_fail_closed() -> bool:
    """Return True if fail-closed mode is enabled (production default)."""
    return os.getenv("ATTESTATION_FAIL_CLOSED", "true").lower() in {
        "1",
        "true",
        "yes",
    }


def _configured_secret(name: str) -> str:
    """Return a secret env var, or empty when it is missing or too short."""
    value = os.getenv(name, "").strip()
    if len(value) < _MIN_SECRET_LENGTH:
        return ""
    return value


def _secrets_equal(left: str, right: str) -> bool:
    """Compare two secrets without leaking length or contents."""
    if not left or not right:
        return False
    return hmac.compare_digest(
        hashlib.sha256(left.encode("utf-8")).digest(),
        hashlib.sha256(right.encode("utf-8")).digest(),
    )


def _public_www_decision(token: str, headers: dict[str, Any]) -> str:
    """Classify a static public-website credential.

    Returns ``allow`` when the attestation token and CloudFront origin
    secret both match, ``deny`` when the website token is presented without
    a matching origin secret, and ``skip`` for every other request (mobile
    JWTs continue through Firebase verification).
    """
    web_token = _configured_secret(_WEB_CREDENTIAL_ENV)
    if not web_token or not _secrets_equal(token, web_token):
        return "skip"
    origin_secret = _configured_secret(_ORIGIN_VERIFY_ENV)
    origin_header = get_header(headers, _ORIGIN_HEADER).strip()
    if origin_secret and _secrets_equal(origin_header, origin_secret):
        return "allow"
    return "deny"


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Authorize requests based on device attestation token."""

    headers = event.get("headers") or {}
    method_arn = event.get("methodArn", "")
    token = get_header(headers, "x-device-attestation")

    web_decision = _public_www_decision(token, headers)
    if web_decision == "allow":
        logger.info("Public website attestation accepted")
        return policy(
            "Allow",
            method_arn,
            "public-www",
            {"attested": "web"},
            broaden_resource=False,
        )
    if web_decision == "deny":
        logger.warning("Public website attestation rejected")
        return policy(
            "Deny",
            method_arn,
            "public-www",
            {"reason": "origin_verify_failed"},
            broaden_resource=False,
        )

    # SECURITY: Check if attestation is configured
    if not is_attestation_enabled():
        if _is_fail_closed():
            # Production mode: Deny all requests when attestation is not configured
            logger.warning(
                "Device attestation not configured but fail-closed mode is enabled. "
                "Denying request. Configure ATTESTATION_JWKS_URL or set "
                "ATTESTATION_FAIL_CLOSED=false for development."
            )
            return policy(
                "Deny",
                method_arn,
                "unconfigured",
                {"reason": "attestation_not_configured"},
                broaden_resource=False,
            )
        else:
            # Development mode: Allow requests without attestation (explicit opt-in)
            logger.info(
                "Device attestation disabled (development mode), allowing request"
            )
            return policy(
                "Allow",
                method_arn,
                "bypass",
                {"bypass": "true", "mode": "development"},
                broaden_resource=False,
            )

    # Require token when attestation is enabled
    if not token:
        logger.warning("Missing device attestation token")
        return policy(
            "Deny",
            method_arn,
            "anonymous",
            {"reason": "missing_token"},
            broaden_resource=False,
        )

    try:
        decoded = verify_attestation_token(token)

        # Handle bypass mode (for testing) - only works when attestation returns bypass
        if decoded.get("bypass"):
            logger.info("Device attestation bypassed via token")
            return policy(
                "Allow",
                method_arn,
                "bypass",
                {"bypass": "true"},
                broaden_resource=False,
            )

        principal = decoded.get("sub", "device")
        logger.info(f"Device attestation verified for principal: {principal[:8]}***")
        return policy(
            "Allow",
            method_arn,
            principal,
            {"attested": "true"},
            broaden_resource=False,
        )

    except Exception as exc:
        # SECURITY: Don't expose detailed error messages to clients
        logger.warning(f"Device attestation failed: {type(exc).__name__}")
        return policy(
            "Deny",
            method_arn,
            "invalid",
            {"reason": "verification_failed"},
            broaden_resource=False,
        )
