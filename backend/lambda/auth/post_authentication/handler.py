"""Cognito Post Authentication trigger.

This Lambda updates the user's last login time in a custom attribute.

SECURITY NOTES:
- Email addresses are masked in logs to comply with privacy regulations
- Never log tokens or secrets
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from app.services.aws_clients import get_cognito_idp_client
from app.utils.logging import configure_logging, get_logger, mask_email, mask_pii

configure_logging()
logger = get_logger(__name__)


def _mask_user_identifier(event: Mapping[str, Any]) -> str:
    user_attrs = event.get("request", {}).get("userAttributes", {}) or {}
    email = user_attrs.get("email") or ""
    if email:
        return mask_email(str(email))
    username = event.get("userName") or ""
    return mask_pii(str(username))


def lambda_handler(event: Mapping[str, Any], _context: Any) -> Mapping[str, Any]:
    """Set the custom:last_auth_time attribute after successful login."""
    user_pool_id = event.get("userPoolId")
    username = event.get("userName")
    if not user_pool_id or not username:
        logger.warning("Post-auth event missing user identifiers")
        return event

    epoch_seconds = str(int(time.time()))
    masked_user = _mask_user_identifier(event)

    try:
        client = get_cognito_idp_client()
        client.admin_update_user_attributes(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[
                {
                    "Name": "custom:last_auth_time",
                    "Value": epoch_seconds,
                }
            ],
        )
        logger.info(f"Updated last login time for {masked_user}")
    except Exception as exc:
        logger.warning(
            "Failed to update last login time",
            extra={"user": masked_user, "error": type(exc).__name__},
        )

    return event
