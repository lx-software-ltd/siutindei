"""Create or reuse a passwordless manager account by email."""

from __future__ import annotations

import os
import secrets
import string
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_cognito import (
    _cognito,
    _invalidate_user_session,
    _mask_cognito_username,
    _serialize_cognito_user,
)
from app.api.admin_cognito_groups import _managed_group_names
from app.api.admin_request import _require_env, parse_object_body
from app.api.admin_validators import _validate_email
from app.db.audit import AuditService
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError
from app.utils import json_response
from app.utils.logging import get_logger, mask_email, mask_pii

logger = get_logger(__name__)

_CONFIRMATION_SYMBOLS = "!@#$%^&*"
_NEEDS_CONFIRMATION = frozenset({"FORCE_CHANGE_PASSWORD", "UNCONFIRMED"})
_FEDERATED_PREFIXES = ("Google_", "SignInWithApple_")
_MAX_LOOKUP_PAGES = 3
_AMBIGUOUS_ACCOUNT = (
    "More than one account uses this email. Choose the user from the list."
)
_RESET_REQUIRED = (
    "This account is waiting for a password reset, so manager access was not granted."
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
        secrets.choice(_CONFIRMATION_SYMBOLS),
    ]
    pool = string.ascii_letters + string.digits + _CONFIRMATION_SYMBOLS
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


def _is_native_username(username: str) -> bool:
    return not username.startswith(_FEDERATED_PREFIXES)


def _matching_users(user_pool_id: str, email: str) -> list[dict[str, Any]]:
    """Users whose email matches, comparing case-insensitively.

    The pool stores alias emails in lowercase and Cognito's filter is
    case-sensitive, so the filter always uses the normalized address.
    A native account is preferred over a Google or Apple account that
    happens to share the address.
    """
    matches: list[dict[str, Any]] = []
    token: Optional[str] = None
    for _ in range(_MAX_LOOKUP_PAGES):
        params: dict[str, Any] = {
            "UserPoolId": user_pool_id,
            "Filter": f'email = "{email}"',
            "Limit": 10,
        }
        if token:
            params["PaginationToken"] = token
        response = _cognito("list_users", **params)
        for user in response.get("Users", []):
            stored = _attributes_of(user).get("email", "")
            if stored.lower() == email:
                matches.append(_as_list_user(user, email))
        token = response.get("PaginationToken")
        if not token:
            break
    return matches


def _choose_existing_user(matches: list[dict[str, Any]]) -> dict[str, Any]:
    native = [
        user for user in matches if _is_native_username(str(user.get("Username") or ""))
    ]
    if len(native) == 1:
        return native[0]
    if len(native) > 1 or len(matches) != 1:
        raise ValidationError(_AMBIGUOUS_ACCOUNT)
    return matches[0]


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
    matches = _matching_users(user_pool_id, email)
    if matches:
        return _choose_existing_user(matches), False
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
        matches = _matching_users(user_pool_id, email)
        if matches:
            return _choose_existing_user(matches), False
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


def _ensure_manager_membership(
    user_pool_id: str, username: str
) -> tuple[list[str], bool]:
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
    signed_out = False
    if manager_group not in names:
        _cognito(
            "admin_add_user_to_group",
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=manager_group,
        )
        signed_out = _invalidate_user_session(user_pool_id, username)
        names.append(manager_group)
    present = set(names)
    groups = [name for name in _managed_group_names() if name in present]
    return groups, signed_out


def _confirmation_failure(created: bool) -> ValidationError:
    if created:
        return ValidationError(
            "The account was created but could not be confirmed. Try again."
        )
    return ValidationError("This account could not be confirmed. Try again.")


def _record_manager_grant(
    event: Mapping[str, Any],
    *,
    email: str,
    user_sub: str,
    created: bool,
    signed_out: bool,
    groups: list[str],
) -> None:
    """Record which admin granted the role. Failure does not undo Cognito."""
    actor = _get_user_sub(event) or ""
    request_id = event.get("requestContext", {}).get("requestId", "")
    try:
        with Session(get_engine()) as session:
            _set_session_audit_context(session, event)
            AuditService(
                session,
                user_id=actor or None,
                request_id=request_id,
            ).log_custom(
                "cognito_user",
                user_sub,
                "INSERT" if created else "UPDATE",
                new_values={
                    "account_created": created,
                    "signed_out": signed_out,
                    "groups": groups,
                },
                changed_fields=["groups"],
            )
            session.commit()
    except Exception as exc:
        logger.warning(
            "Failed to record manager grant",
            extra={
                "user": mask_email(email),
                "actor": mask_pii(actor) if actor else "",
                "error": type(exc).__name__,
            },
        )


def _handle_create_cognito_manager(event: Mapping[str, Any]) -> dict[str, Any]:
    """Create or reuse a passwordless manager account for an email."""
    email = _required_manager_email(event)
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")
    user, created = _find_or_create_cognito_user(user_pool_id, email)
    username = str(user.get("Username") or email)
    status = str(user.get("UserStatus") or "")
    if status == "RESET_REQUIRED":
        raise ValidationError(_RESET_REQUIRED)
    if created or status in _NEEDS_CONFIRMATION:
        try:
            _confirm_passwordless_user(user_pool_id, username)
        except ValidationError:
            raise _confirmation_failure(created) from None
        refreshed = _admin_get_as_list_user(user_pool_id, username)
        if refreshed is not None:
            user = refreshed
    try:
        groups, signed_out = _ensure_manager_membership(user_pool_id, username)
    except AwsProxyError as exc:
        logger.warning(
            "Failed to grant manager role",
            extra={
                "user": _mask_cognito_username(username),
                "error_code": exc.code,
            },
        )
        raise ValidationError(
            "The account exists but the manager role could not be granted. Try again."
        ) from None
    serialized = _serialize_cognito_user(user)
    if serialized is None:
        raise ValidationError("Could not add this manager")
    serialized["groups"] = groups
    serialized["account_created"] = created
    serialized["signed_out"] = signed_out
    actor = _get_user_sub(event) or ""
    logger.info(
        "Ensured manager account",
        extra={
            "user": mask_email(email),
            "actor": mask_pii(actor) if actor else "",
            "account_created": created,
            "signed_out": signed_out,
        },
    )
    _record_manager_grant(
        event,
        email=email,
        user_sub=str(serialized["sub"]),
        created=created,
        signed_out=signed_out,
        groups=groups,
    )
    return json_response(200, serialized, event=event)
