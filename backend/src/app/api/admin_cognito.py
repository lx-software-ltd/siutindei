"""Cognito management helpers for admin APIs."""

from __future__ import annotations

import os
import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_cognito_groups import (
    _list_group_memberships,
    _managed_group_names,
)
from app.api.admin_list_filters import cognito_email_prefix_filter
from app.api.admin_request import (
    _parse_group_name,
    _query_param,
    _require_env,
    parse_limit,
    parse_object_body,
)
from app.api.admin_validators import _validate_email
from app.db.engine import get_engine
from app.db.repositories import OrganizationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.aws_proxy import AwsProxyError
from app.services.aws_proxy import invoke as aws_proxy
from app.utils import json_response, parse_datetime
from app.utils.logging import get_logger, mask_email, mask_pii

logger = get_logger(__name__)

USER_SUB_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
MAX_COGNITO_LIST_LIMIT = 60
MANAGED_ORGANIZATIONS_INCLUDE = "managed_organizations"
MAX_ORG_TRANSFER_LIMIT = 1000
_PASSWORD_SYMBOLS = "!@#$%^&*"
_NEEDS_CONFIRMATION = frozenset(
    {"FORCE_CHANGE_PASSWORD", "RESET_REQUIRED", "UNCONFIRMED"}
)


def _mask_cognito_username(username: str) -> str:
    """Mask a Cognito username for safe logging."""
    if "@" in username:
        return mask_email(username)
    return mask_pii(username)


def _cognito(action: str, **params: Any) -> dict[str, Any]:
    """Call a Cognito IDP action via the AWS API proxy Lambda."""
    return aws_proxy("cognito-idp", action, params)


def _handle_user_group(
    event: Mapping[str, Any],
    method: str,
    username: Optional[str],
) -> dict[str, Any]:
    """Handle user group assignment."""
    if not username:
        raise ValidationError("username is required", field="username")

    group_name = _parse_group_name(event)
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")

    if method == "POST":
        masked_username = _mask_cognito_username(username)
        _cognito(
            "admin_add_user_to_group",
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=group_name,
        )
        _invalidate_user_session(user_pool_id, username)
        logger.info(f"Added user {masked_username} to group {group_name}")
        return json_response(200, {"status": "added", "group": group_name}, event=event)

    if method == "DELETE":
        masked_username = _mask_cognito_username(username)
        _cognito(
            "admin_remove_user_from_group",
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=group_name,
        )
        _invalidate_user_session(user_pool_id, username)
        logger.info(f"Removed user {masked_username} from group {group_name}")
        return json_response(
            200, {"status": "removed", "group": group_name}, event=event
        )

    return json_response(405, {"error": "Method not allowed"}, event=event)


def _invalidate_user_session(user_pool_id: str, username: str) -> None:
    """Invalidate a user's session by signing them out globally."""
    masked_username = _mask_cognito_username(username)
    try:
        _cognito(
            "admin_user_global_sign_out",
            UserPoolId=user_pool_id,
            Username=username,
        )
        logger.info(f"Invalidated session for user: {masked_username}")
    except AwsProxyError as exc:
        logger.warning(
            f"Failed to invalidate session for user {masked_username}: "
            f"{exc.code}: {exc.message}"
        )


def _validate_user_sub(user_sub: str) -> str:
    """Validate and normalize a Cognito user sub."""
    normalized = user_sub.strip().lower()
    if USER_SUB_PATTERN.fullmatch(normalized) is None:
        raise ValidationError("Invalid user sub format", field="sub")
    return normalized


def _add_user_to_manager_group(user_sub: str) -> None:
    """Add a user to the 'manager' Cognito group (best effort)."""
    valid_user_sub: Optional[str] = None
    masked_user_sub = mask_pii(user_sub)
    try:
        valid_user_sub = _validate_user_sub(user_sub)
        user_pool_id = _require_env("COGNITO_USER_POOL_ID")
        manager_group = os.getenv("MANAGER_GROUP", "manager")

        response = _cognito(
            "list_users",
            UserPoolId=user_pool_id,
            Filter=f'sub = "{valid_user_sub}"',
            Limit=1,
        )

        users = response.get("Users", [])
        if not users:
            logger.warning(
                f"Could not find Cognito user with sub: {mask_pii(user_sub)}"
            )
            return

        username = users[0].get("Username")
        if not username:
            logger.warning(f"User with sub {mask_pii(user_sub)} has no username")
            return
        masked_username = _mask_cognito_username(username)

        groups_response = _cognito(
            "admin_list_groups_for_user",
            UserPoolId=user_pool_id,
            Username=username,
        )
        existing_groups = [g["GroupName"] for g in groups_response.get("Groups", [])]

        if manager_group in existing_groups:
            logger.info(f"User {masked_username} is already in group {manager_group}")
            return

        _cognito(
            "admin_add_user_to_group",
            UserPoolId=user_pool_id,
            Username=username,
            GroupName=manager_group,
        )
        _invalidate_user_session(user_pool_id, username)
        logger.info(f"Added user {masked_username} to group {manager_group}")
    except ValidationError as exc:
        logger.warning(
            "Skipped manager group assignment due to invalid user sub",
            extra={
                "user_sub": masked_user_sub,
                "error_type": type(exc).__name__,
            },
        )
    except RuntimeError as exc:
        logger.error(
            "Skipped manager group assignment due to missing Cognito config",
            extra={
                "user_sub": masked_user_sub,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
    except AwsProxyError as exc:
        logger.error(
            "Failed to add user to manager group",
            extra={
                "user_sub": valid_user_sub or masked_user_sub,
                "error_code": exc.code,
                "error_message": exc.message,
            },
        )
    except Exception as exc:
        logger.exception(
            "Unexpected manager group assignment failure",
            extra={
                "user_sub": valid_user_sub or masked_user_sub,
                "error_type": type(exc).__name__,
            },
        )


def _include_managed_organizations(event: Mapping[str, Any]) -> bool:
    """True when the caller asked for each user's managed organizations."""
    include = (_query_param(event, "include") or "").strip()
    if not include:
        return False
    if include != MANAGED_ORGANIZATIONS_INCLUDE:
        raise ValidationError("Invalid include", field="include")
    return True


def _managed_organizations_by_sub(
    subs: list[str],
) -> dict[str, list[dict[str, str]]]:
    """Organizations each Cognito sub manages, ordered by name."""
    if not subs:
        return {}
    with Session(get_engine()) as session:
        return OrganizationRepository(session).list_managed_for_subs(subs)


def _handle_list_cognito_users(event: Mapping[str, Any]) -> dict[str, Any]:
    """List Cognito users for manager selection."""
    limit = parse_limit(event, max_limit=MAX_COGNITO_LIST_LIMIT)
    include_managed = _include_managed_organizations(event)

    pagination_token = _query_param(event, "pagination_token")
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")

    params: dict[str, Any] = {"UserPoolId": user_pool_id, "Limit": limit}
    if pagination_token:
        params["PaginationToken"] = pagination_token
    email_filter = cognito_email_prefix_filter(_query_param(event, "q"))
    if email_filter:
        params["Filter"] = email_filter

    try:
        response = _cognito("list_users", **params)
    except AwsProxyError as exc:
        logger.warning(f"Cognito list_users error: {exc.code}: {exc.message}")
        if pagination_token and exc.code == "InvalidParameterException":
            raise ValidationError(
                "Invalid pagination token", field="pagination_token"
            ) from exc
        raise ValidationError(f"Cognito error: {exc.message}") from exc

    # Group membership is resolved per group, not per user: two
    # ListUsersInGroup calls replace N AdminListGroupsForUser calls, so the
    # proxy hop count stays constant regardless of page size.
    memberships = _list_group_memberships(user_pool_id)

    users = []
    for user in response.get("Users", []):
        user_data = _serialize_cognito_user(user)
        if user_data:
            username = user.get("Username")
            user_data["groups"] = list(memberships.get(username or "", []))
            users.append(user_data)

    if include_managed:
        managed = _managed_organizations_by_sub([user["sub"] for user in users])
        for user in users:
            user["managed_organizations"] = managed.get(user["sub"], [])

    result: dict[str, Any] = {"items": users}
    next_token = response.get("PaginationToken")
    if next_token:
        result["pagination_token"] = next_token

    logger.info(f"Listed {len(users)} Cognito users")
    return json_response(200, result, event=event)


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


def _serialize_cognito_user(user: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Serialize a Cognito user for the API response."""
    raw_attributes = user.get("Attributes", [])
    attributes = {attr["Name"]: attr["Value"] for attr in raw_attributes}

    sub = attributes.get("sub")
    if not sub:
        return None

    last_auth_value = attributes.get("custom:last_auth_time")
    last_auth_time = _parse_last_auth_time(last_auth_value)

    return {
        "sub": sub,
        "email": attributes.get("email"),
        "email_verified": attributes.get("email_verified") == "true",
        "name": attributes.get("name"),
        "given_name": attributes.get("given_name"),
        "family_name": attributes.get("family_name"),
        "username": user.get("Username"),
        "status": user.get("UserStatus"),
        "enabled": user.get("Enabled", True),
        "created_at": user.get("UserCreateDate"),
        "updated_at": user.get("UserLastModifiedDate"),
        "last_auth_time": last_auth_time,
        "attributes": attributes,
    }


def _adjust_user_feedback_stars(user_sub: str, delta: int) -> None:
    """Adjust custom:feedback_stars for a user."""
    if delta == 0:
        return
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")
    result = _get_user_by_sub(user_pool_id, user_sub)
    if result is None:
        logger.warning(f"Could not find user for feedback stars: {mask_pii(user_sub)}")
        return
    username, attributes = result
    current = _parse_feedback_stars(attributes)
    next_value = max(0, current + delta)
    _cognito(
        "admin_update_user_attributes",
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[
            {
                "Name": "custom:feedback_stars",
                "Value": str(next_value),
            }
        ],
    )


def _get_user_by_sub(
    user_pool_id: str,
    user_sub: str,
) -> Optional[tuple[str, dict[str, str]]]:
    """Return Cognito username and attributes for a given user sub."""
    valid_user_sub = _validate_user_sub(user_sub)
    response = _cognito(
        "list_users",
        UserPoolId=user_pool_id,
        Filter=f'sub = "{valid_user_sub}"',
        Limit=1,
    )
    users = response.get("Users", [])
    if not users:
        return None
    user = users[0]
    username = user.get("Username")
    if not username:
        return None
    raw_attributes = user.get("Attributes", [])
    attributes = {attr["Name"]: attr["Value"] for attr in raw_attributes}
    return username, attributes


def _parse_feedback_stars(attributes: Mapping[str, str]) -> int:
    """Parse feedback stars from Cognito attributes."""
    raw_value = attributes.get("custom:feedback_stars")
    try:
        parsed = int(raw_value) if raw_value is not None else 0
    except (TypeError, ValueError):
        parsed = 0
    return max(0, parsed)


def _parse_last_auth_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    try:
        epoch_time = float(value)
    except (TypeError, ValueError):
        epoch_time = None

    if epoch_time is not None:
        if epoch_time > 10**11:
            epoch_time = epoch_time / 1000
        return datetime.fromtimestamp(epoch_time, tz=timezone.utc).isoformat()

    try:
        parsed = parse_datetime(value)
    except ValueError:
        return None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat()


def _handle_delete_cognito_user(
    event: Mapping[str, Any],
    username: str,
) -> dict[str, Any]:
    """Delete a Cognito user and transfer their organizations."""
    user_pool_id = _require_env("COGNITO_USER_POOL_ID")

    fallback_manager_id = _get_user_sub(event)
    if not fallback_manager_id:
        return json_response(401, {"error": "User identity not found"}, event=event)

    try:
        user_response = _cognito(
            "admin_get_user", UserPoolId=user_pool_id, Username=username
        )
    except AwsProxyError as exc:
        if exc.code == "UserNotFoundException":
            raise NotFoundError("cognito_user", username)
        raise

    user_sub = None
    for attr in user_response.get("UserAttributes", []):
        if attr["Name"] == "sub":
            user_sub = attr["Value"]
            break

    if not user_sub:
        return json_response(500, {"error": "User has no sub attribute"}, event=event)
    if user_sub == fallback_manager_id:
        return json_response(400, {"error": "Cannot delete yourself"}, event=event)

    transferred_count = 0
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        org_repo = OrganizationRepository(session)
        orgs = org_repo.find_by_manager(user_sub, limit=MAX_ORG_TRANSFER_LIMIT)
        for org in orgs:
            org.manager_id = fallback_manager_id
            org_repo.update(org)
            transferred_count += 1
        session.commit()

    logger.info(
        f"Transferred {transferred_count} orgs from "
        f"{mask_pii(user_sub)} to {mask_pii(fallback_manager_id)}"
    )

    _invalidate_user_session(user_pool_id, username)
    _cognito("admin_delete_user", UserPoolId=user_pool_id, Username=username)
    logger.info(f"Deleted Cognito user: {_mask_cognito_username(username)}")

    return json_response(
        200,
        {
            "status": "deleted",
            "username": username,
            "user_sub": user_sub,
            "transferred_organizations_count": transferred_count,
            "fallback_manager_id": fallback_manager_id,
        },
        event=event,
    )
