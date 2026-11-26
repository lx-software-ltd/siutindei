"""API Gateway request authorizer for partner API keys.

This Lambda validates ``Authorization: Bearer <token>`` against hashed keys
stored in the ``api_keys`` table (read via RDS Proxy with IAM auth) and
passes the key identity (id, scope, organization) to the backend handlers.

Unlike the JWT authorizers, this function runs INSIDE the VPC because it
needs database access instead of public JWKS endpoints.
"""

from __future__ import annotations

from typing import Any

from app.auth.api_key_authorizer import authorize_api_key
from app.auth.authorizer_helpers import policy
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Authorize requests based on a partner API key."""
    try:
        return authorize_api_key(event)
    except Exception as exc:
        # SECURITY: fail closed and don't expose internal error details
        logger.exception(f"API key authorization failed: {type(exc).__name__}")
        return policy(
            "Deny",
            event.get("methodArn", ""),
            "error",
            {"reason": "authorization_error"},
        )
