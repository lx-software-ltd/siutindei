"""Cognito management helpers for admin APIs."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_list_filters import cognito_email_prefix_filter
from app.api.admin_request import (
    _parse_group_name,
    _query_param,
    _require_env,
    parse_limit,
)
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
MAX_ORG_TRANSFER_LIMIT = 1000
# Cognito caps ListUsersInGroup at 60 members per page.
GROUP_MEMBERS_PAGE_SIZE = 60
# Hard stop on group pagination so a runaway NextToken can never exhaust the
# Lambda timeout; 50 pages x 60 members is far beyond any realistic pool.
MAX_GROUP_PAGES = 50


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


def _handle_list_cognito_users(event: Mapping[str, Any]) -> dict[str, Any]:
    """List Cognito users for manager selection."""
    limit = parse_limit(event, max_limit=MAX_COGNITO_LIST_LIMIT)

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

    result: dict[str, Any] = {"items": users}
    next_token = response.get("PaginationToken")
    if next_token:
        result["pagination_token"] = next_token

    logger.info(f"Listed {len(users)} Cognito users")
    return json_response(200, result, event=event)


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


def _managed_group_names() -> list[str]:
    """Return the Cognito groups the admin console exposes as roles."""
    names = [
        os.getenv("ADMIN_GROUP") or "admin",
        os.getenv("MANAGER_GROUP") or "manager",
    ]
    return list(dict.fromkeys(names))


def _list_group_memberships(user_pool_id: str) -> dict[str, list[str]]:
    """Map username -> group names for the managed groups.

    A failure for one group degrades to "no members" for that group only,
    so the user list still renders; the failure is logged for follow-up.
    """
    memberships: dict[str, list[str]] = {}
    for group_name in _managed_group_names():
        for username in _iter_group_members(user_pool_id, group_name):
            memberships.setdefault(username, []).append(group_name)
    return memberships


def _iter_group_members(user_pool_id: str, group_name: str) -> list[str]:
    members: list[str] = []
    next_token: Optional[str] = None
    for _ in range(MAX_GROUP_PAGES):
        params: dict[str, Any] = {
            "UserPoolId": user_pool_id,
            "GroupName": group_name,
            "Limit": GROUP_MEMBERS_PAGE_SIZE,
        }
        if next_token:
            params["NextToken"] = next_token
        try:
            response = _cognito("list_users_in_group", **params)
        except AwsProxyError as exc:
            logger.warning(
                "Failed to list Cognito group members",
                extra={
                    "group": group_name,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
            break
        for user in response.get("Users", []):
            username = user.get("Username")
            if username:
                members.append(username)
        next_token = response.get("NextToken")
        if not next_token:
            break
    else:
        logger.warning(
            "Cognito group pagination exceeded MAX_GROUP_PAGES; results truncated",
            extra={"group": group_name},
        )
    return members


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
