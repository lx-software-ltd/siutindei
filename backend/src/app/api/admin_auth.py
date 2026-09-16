"""Authorization helpers for admin APIs."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.db.audit import set_audit_context
from app.db.engine import get_engine
from app.db.repositories import OrganizationRepository


def _get_authorizer_context(event: Mapping[str, Any]) -> dict[str, Any]:
    """Extract authorizer context from the event.

    Supports both:
    - Lambda authorizers (context fields directly in authorizer)
    - Cognito User Pool authorizers (claims nested under authorizer.claims)
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {})

    # Lambda authorizer puts context fields directly
    if "groups" in authorizer or "userSub" in authorizer:
        return {
            "groups": authorizer.get("groups", ""),
            "sub": authorizer.get("userSub", ""),
            "email": authorizer.get("email", ""),
        }

    # Cognito User Pool authorizer nests under "claims"
    claims = authorizer.get("claims", {})
    return {
        "groups": claims.get("cognito:groups", ""),
        "sub": claims.get("sub", ""),
        "email": claims.get("email", ""),
    }


def _is_admin(event: Mapping[str, Any]) -> bool:
    """Return True when request belongs to an admin user."""
    ctx = _get_authorizer_context(event)
    groups = ctx.get("groups", "")
    admin_group = os.getenv("ADMIN_GROUP", "admin")
    return admin_group in groups.split(",") if groups else False


def _is_manager(event: Mapping[str, Any]) -> bool:
    """Return True when request belongs to a manager user."""
    ctx = _get_authorizer_context(event)
    groups = ctx.get("groups", "")
    manager_group = os.getenv("MANAGER_GROUP", "manager")
    return manager_group in groups.split(",") if groups else False


def _is_importer(event: Mapping[str, Any]) -> bool:
    """Return True when request belongs to an importer user."""
    ctx = _get_authorizer_context(event)
    groups = ctx.get("groups", "")
    importer_group = os.getenv("IMPORTER_GROUP", "importer")
    return importer_group in groups.split(",") if groups else False


def _get_user_sub(event: Mapping[str, Any]) -> Optional[str]:
    """Extract the user's Cognito sub (subject) from authorizer context."""
    ctx = _get_authorizer_context(event)
    return ctx.get("sub") or None


def _get_user_email(event: Mapping[str, Any]) -> Optional[str]:
    """Extract the user's email from authorizer context."""
    ctx = _get_authorizer_context(event)
    return ctx.get("email") or None


def _set_session_audit_context(session: Session, event: Mapping[str, Any]) -> None:
    """Set audit context on the database session for trigger-based logging.

    This sets PostgreSQL session variables that the audit trigger function
    reads to populate user_id and request_id fields in audit_log entries.

    Args:
        session: SQLAlchemy database session.
        event: Lambda event containing user and request context.
    """
    user_sub = _get_user_sub(event)
    request_id = event.get("requestContext", {}).get("requestId", "")
    set_audit_context(session, user_id=user_sub, request_id=request_id)


def _get_managed_organization_ids(event: Mapping[str, Any]) -> set[str]:
    """Get the IDs of organizations managed by the current user.

    Returns:
        Set of organization IDs (as strings) managed by the user.
    """
    user_sub = _get_user_sub(event)
    if not user_sub:
        return set()

    with Session(get_engine()) as session:
        # Read-only query, but set context for consistency
        _set_session_audit_context(session, event)
        repo = OrganizationRepository(session)
        orgs = repo.find_by_manager(user_sub)
        return {str(org.id) for org in orgs}
