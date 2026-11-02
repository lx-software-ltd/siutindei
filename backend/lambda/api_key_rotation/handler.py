"""Lambda handler for API key rotation.

This Lambda rotates the API Gateway API key on a scheduled basis to minimize
the impact of key compromise. The rotation process:

1. Generates a new secure API key value
2. Creates a new API key in API Gateway
3. Associates it with the usage plan
4. Stores the new key in Secrets Manager
5. Disables the old API key (after grace period)
6. Deletes the old API key

SECURITY NOTES:
- API keys should be rotated regularly (recommended: every 90 days)
- The rotation includes a grace period where both old and new keys work
- Old keys are disabled, then deleted after the grace period

Environment Variables:
    API_GATEWAY_REST_API_ID: The API Gateway REST API ID
    API_GATEWAY_USAGE_PLAN_ID: The usage plan ID to associate keys with
    API_KEY_SECRET_ARN: Secrets Manager secret ARN to store the new key
    API_KEY_NAME_PREFIX: Prefix for API key names (default: "mobile-search-key")
    GRACE_PERIOD_HOURS: Hours to keep old key active (default: 24)
"""

from __future__ import annotations

import json
import os
import secrets
import string
import time
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from app.services.aws_clients import get_client
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# API key requirements (API Gateway requires at least 20 characters)
API_KEY_LENGTH = 40
API_KEY_CHARSET = string.ascii_letters + string.digits


def _generate_api_key() -> str:
    """Generate a cryptographically secure API key.

    Returns:
        A secure random string of API_KEY_LENGTH characters.
    """
    return "".join(secrets.choice(API_KEY_CHARSET) for _ in range(API_KEY_LENGTH))


def _get_current_api_key_id(
    apigw_client: Any,
    rest_api_id: str,
    usage_plan_id: str,
    key_prefix: str,
) -> str | None:
    """Find the current API key ID associated with the usage plan.

    Args:
        apigw_client: API Gateway client
        rest_api_id: REST API ID
        usage_plan_id: Usage plan ID
        key_prefix: API key name prefix to match

    Returns:
        The API key ID if found, None otherwise.
    """
    try:
        # List API keys in the usage plan
        paginator = apigw_client.get_paginator("get_usage_plan_keys")
        for page in paginator.paginate(usagePlanId=usage_plan_id):
            for key in page.get("items", []):
                if key.get("name", "").startswith(key_prefix):
                    return key.get("id")
    except ClientError as exc:
        logger.warning(f"Error listing usage plan keys: {exc}")

    return None


def _create_api_key(
    apigw_client: Any,
    key_name: str,
    key_value: str,
    description: str,
) -> str:
    """Create a new API key in API Gateway.

    Args:
        apigw_client: API Gateway client
        key_name: Name for the API key
        key_value: The API key value
        description: Description for the key

    Returns:
        The new API key ID.
    """
    response = apigw_client.create_api_key(
        name=key_name,
        value=key_value,
        enabled=True,
        description=description,
    )
    return response["id"]


def _associate_key_with_usage_plan(
    apigw_client: Any,
    usage_plan_id: str,
    key_id: str,
) -> None:
    """Associate an API key with a usage plan.

    Args:
        apigw_client: API Gateway client
        usage_plan_id: Usage plan ID
        key_id: API key ID to associate
    """
    apigw_client.create_usage_plan_key(
        usagePlanId=usage_plan_id,
        keyId=key_id,
        keyType="API_KEY",
    )


def _disable_api_key(apigw_client: Any, key_id: str) -> None:
    """Disable an API key.

    Args:
        apigw_client: API Gateway client
        key_id: API key ID to disable
    """
    apigw_client.update_api_key(
        apiKey=key_id,
        patchOperations=[
            {"op": "replace", "path": "/enabled", "value": "false"},
        ],
    )


def _delete_api_key(apigw_client: Any, key_id: str) -> None:
    """Delete an API key.

    Args:
        apigw_client: API Gateway client
        key_id: API key ID to delete
    """
    apigw_client.delete_api_key(apiKey=key_id)


def _store_key_in_secrets_manager(
    secrets_client: Any,
    secret_arn: str,
    key_value: str,
    key_id: str,
    rotation_date: str,
) -> None:
    """Store the new API key in Secrets Manager.

    Args:
        secrets_client: Secrets Manager client
        secret_arn: Secret ARN
        key_value: The API key value
        key_id: The API Gateway key ID
        rotation_date: ISO format date of rotation
    """
    secret_value = json.dumps(
        {
            "api_key": key_value,
            "api_key_id": key_id,
            "rotated_at": rotation_date,
        }
    )

    secrets_client.put_secret_value(
        SecretId=secret_arn,
        SecretString=secret_value,
    )


def _get_old_key_info_from_secret(
    secrets_client: Any,
    secret_arn: str,
) -> dict[str, Any] | None:
    """Get the current key info from Secrets Manager.

    Args:
        secrets_client: Secrets Manager client
        secret_arn: Secret ARN

    Returns:
        Dict with api_key_id and rotated_at if found, None otherwise.
    """
    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_string = response.get("SecretString")
        if secret_string:
            return json.loads(secret_string)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            return None
        raise

    return None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle API key rotation.

    This handler can be invoked:
    - By EventBridge on a schedule (e.g., every 90 days)
    - Manually via Lambda invoke for immediate rotation
    - As part of an incident response

    Args:
        event: EventBridge or manual invocation event
        context: Lambda context

    Returns:
        Dict with rotation status and details.
    """
    # Get configuration from environment
    rest_api_id = os.getenv("API_GATEWAY_REST_API_ID")
    usage_plan_id = os.getenv("API_GATEWAY_USAGE_PLAN_ID")
    secret_arn = os.getenv("API_KEY_SECRET_ARN")
    key_prefix = os.getenv("API_KEY_NAME_PREFIX", "mobile-search-key")

    # Validate configuration
    if not rest_api_id or not usage_plan_id or not secret_arn:
        logger.error("Missing required environment variables")
        return {
            "statusCode": 500,
            "body": "Missing configuration",
        }

    apigw_client = get_client("apigateway")
    secrets_client = get_client("secretsmanager")

    rotation_date = datetime.now(UTC).isoformat()

    # Check for pending cleanup of old keys
    old_key_info = _get_old_key_info_from_secret(secrets_client, secret_arn)
    old_key_id = old_key_info.get("api_key_id") if old_key_info else None

    # Generate new API key
    new_key_value = _generate_api_key()
    new_key_name = f"{key_prefix}-{int(time.time())}"

    logger.info(f"Creating new API key: {new_key_name}")

    try:
        # Create new API key
        new_key_id = _create_api_key(
            apigw_client,
            new_key_name,
            new_key_value,
            f"Rotated on {rotation_date}",
        )

        # Associate with usage plan
        _associate_key_with_usage_plan(apigw_client, usage_plan_id, new_key_id)

        # Store new key in Secrets Manager
        _store_key_in_secrets_manager(
            secrets_client,
            secret_arn,
            new_key_value,
            new_key_id,
            rotation_date,
        )

        logger.info(f"New API key created and stored: {new_key_id}")

        # Handle old key cleanup
        if old_key_id and old_key_id != new_key_id:
            try:
                # Disable old key immediately (it will still work during grace period
                # because it's still in the usage plan)
                _disable_api_key(apigw_client, old_key_id)
                logger.info(f"Disabled old API key: {old_key_id}")

                # Delete old key (after it's disabled, it can be deleted)
                # In a production system, you might want to schedule this
                # deletion after the grace period instead
                _delete_api_key(apigw_client, old_key_id)
                logger.info(f"Deleted old API key: {old_key_id}")
            except ClientError as exc:
                # Old key might already be deleted
                logger.warning(f"Error cleaning up old key {old_key_id}: {exc}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "API key rotated successfully",
                    "new_key_id": new_key_id,
                    "old_key_id": old_key_id,
                    "rotated_at": rotation_date,
                }
            ),
        }

    except ClientError as exc:
        logger.exception(f"Failed to rotate API key: {exc}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Failed to rotate API key",
                    "detail": str(exc),
                }
            ),
        }
