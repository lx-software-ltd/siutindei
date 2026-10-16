"""Cognito group membership for the admin user list."""

from __future__ import annotations

import os
from typing import Any, Optional

from app.services.aws_proxy import AwsProxyError
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Cognito caps ListUsersInGroup at 60 members per page.
GROUP_MEMBERS_PAGE_SIZE = 60
# Hard stop on group pagination so a runaway NextToken can never exhaust the
# Lambda timeout; 50 pages x 60 members is far beyond any realistic pool.
MAX_GROUP_PAGES = 50


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
    # Imported here because admin_cognito imports this module.
    from app.api.admin_cognito import _cognito

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
