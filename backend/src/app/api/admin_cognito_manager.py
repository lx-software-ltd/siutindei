"""Create or reuse a passwordless manager account by email."""

from __future__ import annotations

import os
import secrets
import string
from typing import Any, Mapping, Optional

from app.api.admin_cognito import (
    _cognito,
    _invalidate_user_session,
    _mask_cognito_username,
    _serialize_cognito_user,
)
from app.api.admin_cognito_groups import _managed_group_names
from app.api.admin_request import _require_env, parse_object_body
from app.api.admin_validators import _validate_email
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError
from app.utils import json_response
from app.utils.logging import get_logger, mask_email

logger = get_logger(__name__)

_PASSWORD_SYMBOLS = "!@#$%^&*"
_NEEDS_CONFIRMATION = frozenset(
    {"FORCE_CHANGE_PASSWORD", "RESET_REQUIRED", "UNCONFIRMED"}
)


def _passwordless_confirmation_secret() -> str:
    """Random password that satisfies the user pool policy.

    AdminCreateUser leaves the account in FORCE_CHANGE_PASSWORD.
    Custom auth needs a confirmed account. The app client signs in
    with a one-time code, so this secret is never returned or logged.
    """
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_PASSWORD_SYMBOLS),
    ]
    pool = string.ascii_letters + string.digits + _PASSWORD_SYMBOLS
    required.extend(secrets.choice(pool) for _ in range(28))
    shuffled: list[str] = []
    pending = required
    while pending:
        index = secrets.randbelow(len(pending))
        shuffled.append(pending.pop(index))
    return "".join(shuffled)


def _required_manager_email(event: Mapping[str, Any]) -> str:
    """Return a normalized email safe to embed in a Cognito filter."""
    body = parse_object_body(event)
    email = _validate_email(body.get("email"))
    if email is None:
        raise ValidationError("email is required", field="email")
    if '"' in email or "\\" in email:
        raise ValidationError(
            "email must be a valid email address",
            field="email",
        )
    return email


def _attributes_of(user: Mapping[str, Any]) -> dict[str, str]:
    raw = user.get("Attributes") or user.get("UserAttributes") or []
    return {attr["Name"]: attr["Value"] for attr in raw}


def _as_list_user(user: Mapping[str, Any], username: str) -> dict[str, Any]:
    """Normalize AdminGetUser and AdminCreateUser records for the serializer."""
    attributes = user.get("Attributes") or user.get("UserAttributes") or []
    return {
        "Username": user.get("Username") or username,
        "Attributes": attributes,
        "UserStatus": user.get("UserStatus"),
        "Enabled": user.get("Enabled", True),
        "UserCreateDate": user.get("UserCreateDate"),
        "UserLastModifiedDate": user.get("UserLastModifiedDate"),
    }


def _find_cognito_user_by_email(
    user_pool_id: str,
    email: str,
) -> Optional[dict[str, Any]]:
    response = _cognito(
        "list_users",
        UserPoolId=user_pool_id,
        Filter=f'email = "{email}"',
        Limit=10,
    )
    for user in response.get("Users", []):
        if _attributes_of(user).get("email", "").lower() == email:
            return _as_list_user(user, email)
    return None


def _admin_get_as_list_user(
    user_pool_id: str,
    username: str,
) -> Optional[dict[str, Any]]:
    try:
        response = _cognito(
            "admin_get_user",
            UserPoolId=user_pool_id,
            Username=username,
        )
    except AwsProxyError as exc:
        if exc.code == "UserNotFoundException":
            return None
        raise
    return _as_list_user(response, username)


def _find_or_create_cognito_user(
    user_pool_id: str,
    email: str,
) -> tuple[dict[str, Any], bool]:
    existing = _find_cognito_user_by_email(user_pool_id, email)
    if existing is not None:
        return existing, False
    try:
        created = _cognito(
            "admin_create_user",
            UserPoolId=user_pool_id,
            Username=email,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
        )
    except AwsProxyError as exc:
        if exc.code not in {"UsernameExistsException", "AliasExistsException"}:
            logger.warning(
                "Failed to create manager account",
                extra={"user": mask_email(email), "error_code": exc.code},
            )
            raise ValidationError("Could not add this manager") from None
        existing = _find_cognito_user_by_email(user_pool_id, email)
        if existing is None:
            existing = _admin_get_as_list_user(user_pool_id, email)
        if existing is None:
            raise ValidationError("Could not add this manager") from None
        return existing, False
    user = _as_list_user(created.get("User") or {}, email)
    return user, True


def _confirm_passwordless_user(user_pool_id: str, username: str) -> None:
    secret = _passwordless_confirmation_secret()
    try:
        _cognito(
            "admin_set_user_password",
            UserPoolId=user_pool_id,
            Username=username,
            Password=secret,
            Permanent=True,
        )
    except AwsProxyError as exc:
        logger.warning(
            "Failed to confirm manager account",
            extra={
                "user": _mask_cognito_username(username),
                "error_code": exc.code,
            },
        )
        raise ValidationError("Could not add this manager") from None
    finally:
        del secret


def _ensure_manager_membership(user_pool_id: str, username: str) -> list[str]:
    manager_group = os.getenv("MANAGER_GROUP", "manager")
    response = _cognito(
        "admin_list_groups_for_user",
        UserPoolId=user_pool_id,
        Username=username,
    )
    names = [
        group["GroupName"]
        for group in response.get("Groups", [])
        if group.get("GroupName")
    ]
    if manager_group not in names:
        _cognito(
            "admin_add_user_to_group",
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=manager_group,
        )
        _invalidate_user_session(user_pool_id, username)
        names.append(manager_group)
    present = set(names)
    return [name for name in _managed_group_names() if name in present]


def _handle_create_cognito_manager(event: Mapping[str, Any]) -> dict[str, Any]:
    """Create or reuse a passwordless manager account for an email."""
    email = _required_manager_email(event)
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")
    user, created = _find_or_create_cognito_user(user_pool_id, email)
    username = str(user.get("Username") or email)
    if created or user.get("UserStatus") in _NEEDS_CONFIRMATION:
        _confirm_passwordless_user(user_pool_id, username)
        refreshed = _admin_get_as_list_user(user_pool_id, username)
        if refreshed is not None:
            user = refreshed
    groups = _ensure_manager_membership(user_pool_id, username)
    serialized = _serialize_cognito_user(user)
    if serialized is None:
        raise ValidationError("Could not add this manager")
    serialized["groups"] = groups
    logger.info(
        "Ensured manager account",
        extra={"user": mask_email(email), "account_created": created},
    )
    return json_response(200, serialized, event=event)
