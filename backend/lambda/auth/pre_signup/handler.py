"""Cognito Pre Sign-up trigger.

Auto-confirms passwordless sign-up and links a new Google or Apple
sign-in to the existing account for that verified email.

SECURITY NOTES:
- Email addresses are masked in logs to comply with privacy regulations
- Never log passwords or sensitive user data
- Linking requires the provider to mark the email verified
"""

from __future__ import annotations

from typing import Any, Mapping

from app.services.aws_clients import get_cognito_idp_client
from app.utils.logging import configure_logging, get_logger, mask_email

configure_logging()
logger = get_logger(__name__)

_LINKABLE_PROVIDERS = frozenset({"Google", "SignInWithApple"})


class _ProviderLinked(Exception):
    """The provider was linked, so Cognito must not create a second user."""


def lambda_handler(event, _context):
    """Handle pre-signup trigger."""
    request = event.get("request", {})
    response = event.setdefault("response", {})
    user_attributes = request.get("userAttributes", {})
    email = user_attributes.get("email", "")

    logger.info(f"Pre-signup for {mask_email(email)}")

    if event.get("triggerSource") == "PreSignUp_ExternalProvider":
        _link_verified_provider(event)

    response["autoConfirmUser"] = True
    response["autoVerifyEmail"] = True
    return event


def _link_verified_provider(event: Mapping[str, Any]) -> None:
    provider, subject = _provider_identity(str(event.get("userName") or ""))
    if provider is None or subject is None:
        return
    attributes = event.get("request", {}).get("userAttributes", {}) or {}
    email = _verified_email(attributes)
    if email is None:
        logger.info("Skipped provider link; email is not verified")
        return
    user_pool_id = event.get("userPoolId")
    if not user_pool_id:
        return
    try:
        native = _native_user(str(user_pool_id), email)
    except Exception as exc:
        logger.warning(
            "Skipped provider link; lookup failed",
            extra={"user": mask_email(email), "error": type(exc).__name__},
        )
        return
    if native is None:
        return
    username = str(native.get("Username") or "")
    if not username:
        return
    try:
        get_cognito_idp_client().admin_link_provider_for_user(
            UserPoolId=str(user_pool_id),
            DestinationUser={
                "ProviderName": "Cognito",
                "ProviderAttributeValue": username,
            },
            SourceUser={
                "ProviderName": provider,
                "ProviderAttributeName": "Cognito_Subject",
                "ProviderAttributeValue": subject,
            },
        )
    except Exception as exc:
        logger.warning(
            "Failed to link provider account",
            extra={"user": mask_email(email), "error": type(exc).__name__},
        )
        return
    logger.info(
        "Linked provider to existing account",
        extra={"user": mask_email(email), "provider": provider},
    )
    raise _ProviderLinked(
        "This email is already registered. Sign in again to continue."
    )


def _provider_identity(user_name: str) -> tuple[str | None, str | None]:
    provider, separator, subject = user_name.partition("_")
    if not separator or provider not in _LINKABLE_PROVIDERS or not subject:
        return None, None
    return provider, subject


def _verified_email(attributes: Mapping[str, Any]) -> str | None:
    if attributes.get("email_verified") not in {"true", True}:
        return None
    email = str(attributes.get("email") or "").strip().lower()
    if not email or "@" not in email or '"' in email or "\\" in email:
        return None
    return email


def _native_user(user_pool_id: str, email: str) -> dict[str, Any] | None:
    response = get_cognito_idp_client().list_users(
        UserPoolId=user_pool_id,
        Filter=f'email = "{email}"',
        Limit=10,
    )
    native: list[dict[str, Any]] = []
    prefixes = tuple(f"{name}_" for name in _LINKABLE_PROVIDERS)
    for user in response.get("Users", []):
        stored = ""
        for attr in user.get("Attributes") or []:
            if attr.get("Name") == "email":
                stored = str(attr.get("Value") or "")
        if stored.lower() != email:
            continue
        username = str(user.get("Username") or "")
        if username.startswith(prefixes):
            continue
        native.append(user)
    if len(native) == 1:
        return native[0]
    if len(native) > 1:
        logger.warning(
            "Skipped provider link; several accounts share this email",
            extra={"user": mask_email(email)},
        )
    return None
