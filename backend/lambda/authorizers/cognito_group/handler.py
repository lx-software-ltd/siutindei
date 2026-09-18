"""API Gateway request authorizer for Cognito group-based access control.

This Lambda validates JWT tokens with proper signature verification and checks
if the user belongs to the required Cognito groups before allowing access.

SECURITY NOTES:
- JWT signatures are verified using Cognito's JWKS endpoint
- Token expiration is validated to prevent replay attacks
- Issuer is verified to prevent token confusion attacks

Environment Variables:
    ALLOWED_GROUPS: Comma-separated list of groups that can access the endpoint
                    (e.g., "admin" or "admin,manager")
    IMPORTER_GROUP: Optional extra group allowed on catalog import
                    and owner-UI listing routes (see
                    ``_importer_path_allowed``).
"""

from __future__ import annotations

import os
from typing import Any

from app.auth.authorizer_helpers import extract_token, policy
from app.auth.jwt_validator import (
    JWTValidationError,
    decode_and_verify_token,
)
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_IMPORTER_POST_PATHS = (
    ("v1", "admin", "imports"),
    ("v1", "admin", "imports", "presign"),
)


def _importer_path_allowed(method_arn: str) -> bool:
    """Return True for importer catalog and owner-UI listing routes.

    methodArn shape from API Gateway REST:
    ``arn:aws:execute-api:region:acct:apiId/stage/METHOD/v1/admin/...``
    so index 2 is the HTTP method.
    """
    parts = method_arn.split("/")
    if len(parts) < 6:
        return False
    method = parts[2]
    path = tuple(parts[3:])
    if method == "POST" and path in _IMPORTER_POST_PATHS:
        return True
    if method == "GET" and path == ("v1", "admin", "organizations"):
        return True
    if method == "GET" and len(path) == 4:
        if path[:3] == ("v1", "admin", "imports"):
            return path[3] not in {"presign", "export"}
        if path[:3] == ("v1", "admin", "organizations"):
            return True
    if method in {"PATCH", "ANY"} and len(path) == 4:
        return path[:3] == ("v1", "admin", "organizations")
    return False


def _importer_method_arns(method_arn: str) -> list[str]:
    """Cached Allow covers import plus owner-UI listing routes."""
    parts = method_arn.split("/")
    prefix = "/".join(parts[:2])
    return [
        f"{prefix}/POST/v1/admin/imports",
        f"{prefix}/POST/v1/admin/imports/presign",
        f"{prefix}/GET/v1/admin/imports/*",
        f"{prefix}/GET/v1/admin/organizations",
        f"{prefix}/GET/v1/admin/organizations/*",
        f"{prefix}/PATCH/v1/admin/organizations/*",
        f"{prefix}/ANY/v1/admin/organizations/*",
    ]


def _allow_policy(
    method_arn: str,
    user_sub: str,
    context: dict[str, Any],
    *,
    importer_only: bool,
) -> dict[str, Any]:
    """Allow admin (cached ``/*``) or importer (two import ARNs only)."""
    if not importer_only:
        return policy("Allow", method_arn, user_sub, context)
    allowed = policy(
        "Allow",
        method_arn,
        user_sub,
        context,
        broaden_resource=False,
    )
    allowed["policyDocument"]["Statement"][0]["Resource"] = _importer_method_arns(
        method_arn
    )
    return allowed


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Authorize requests based on Cognito group membership.

    This authorizer:
    1. Extracts the JWT token from the Authorization header
    2. Verifies the token signature using Cognito's JWKS
    3. Validates token expiration and issuer
    4. Checks if the user belongs to any of the allowed groups

    Args:
        event: API Gateway authorizer event containing headers and methodArn
        _context: Lambda context (unused)

    Returns:
        IAM policy document allowing or denying the request
    """
    headers = event.get("headers") or {}
    method_arn = event.get("methodArn", "")

    # Get configuration
    allowed_groups_str = os.getenv("ALLOWED_GROUPS", "")
    if not allowed_groups_str:
        logger.error("ALLOWED_GROUPS environment variable not configured")
        return policy("Deny", method_arn, "misconfigured", {"reason": "misconfigured"})

    allowed_groups = {g.strip() for g in allowed_groups_str.split(",") if g.strip()}

    # Extract token from Authorization header
    token = extract_token(headers)
    if not token:
        logger.warning("Missing or invalid Authorization header")
        return policy("Deny", method_arn, "anonymous", {"reason": "missing_token"})

    try:
        # Verify and decode the JWT token with signature validation
        claims = decode_and_verify_token(token)

        user_sub = claims.sub
        email = claims.email
        user_groups = set(claims.groups)

        # Check if user is in any of the allowed groups
        matching_groups = user_groups & allowed_groups
        importer_group = os.getenv("IMPORTER_GROUP", "").strip()
        importer_allowed = (
            bool(importer_group)
            and importer_group in user_groups
            and _importer_path_allowed(method_arn)
        )

        if matching_groups or importer_allowed:
            matched = matching_groups or {importer_group}
            logger.info(
                f"Access granted for user {user_sub[:8]}*** "
                f"(groups: {', '.join(matched)})"
            )
            return _allow_policy(
                method_arn,
                user_sub,
                {
                    "userSub": user_sub,
                    "email": email,
                    "groups": ",".join(user_groups),
                    "matchedGroups": ",".join(matched),
                },
                importer_only=not bool(matching_groups),
            )
        else:
            logger.warning(
                f"Access denied for user {user_sub[:8]}*** "
                f"(user groups: {user_groups}, required: {allowed_groups})"
            )
            return policy(
                "Deny",
                method_arn,
                user_sub,
                {"reason": "insufficient_permissions", "userSub": user_sub},
            )

    except JWTValidationError as exc:
        logger.warning(f"JWT validation failed: {exc.message} (reason: {exc.reason})")
        return policy("Deny", method_arn, "invalid", {"reason": exc.reason})
    except Exception as exc:
        # SECURITY: Don't expose internal error details
        logger.warning(f"Token validation failed: {type(exc).__name__}")
        return policy("Deny", method_arn, "invalid", {"reason": "invalid_token"})
