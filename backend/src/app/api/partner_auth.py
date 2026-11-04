"""Authorization helpers for partner API-key routes.

The partner API-key Lambda authorizer validates the ``x-partner-key``
header against the ``api_keys`` table and passes the key identity to
handlers through the authorizer context:

- ``apiKeyId``: UUID of the validated key
- ``scope``: ``read`` or ``crud``
- ``orgId``: organization UUID for org-scoped keys, empty for full access
- ``userSub``: ``api-key:<id>`` so audit logging attributes writes to the key
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.api.admin_auth import _get_user_sub
from app.exceptions import AuthorizationError

SCOPE_READ = "read"
SCOPE_CRUD = "crud"


@dataclass(frozen=True)
class PartnerContext:
    """Identity of a validated partner API key."""

    api_key_id: str
    scope: str
    org_id: str | None


def get_partner_context(event: Mapping[str, Any]) -> PartnerContext | None:
    """Extract the partner API-key context set by the authorizer.

    Returns:
        The partner context, or None when the request was not authorized
        by the partner API-key authorizer.
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {}) or {}
    api_key_id = authorizer.get("apiKeyId")
    scope = authorizer.get("scope")
    if not api_key_id or scope not in (SCOPE_READ, SCOPE_CRUD):
        return None
    return PartnerContext(
        api_key_id=str(api_key_id),
        scope=str(scope),
        org_id=str(authorizer.get("orgId")) if authorizer.get("orgId") else None,
    )


def require_full_access(partner: PartnerContext) -> None:
    """Reject organization-scoped keys on full-catalog partner routes."""
    if partner.org_id:
        raise AuthorizationError("This API key is limited to one organization")


def require_crud(partner: PartnerContext) -> None:
    """Reject read-only keys on routes reserved for crud keys."""
    if partner.scope != SCOPE_CRUD:
        raise AuthorizationError("This API key does not allow write access")


def partner_actor(event: Mapping[str, Any], partner: PartnerContext) -> str:
    """Authorizer subject, or the API key id when ``userSub`` is omitted."""
    return _get_user_sub(event) or f"api-key:{partner.api_key_id}"
