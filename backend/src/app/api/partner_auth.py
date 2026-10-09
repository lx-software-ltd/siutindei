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

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.exceptions import AuthorizationError

SCOPE_READ = "read"
SCOPE_CRUD = "crud"


@dataclass(frozen=True)
class PartnerContext:
    """Identity of a validated partner API key."""

    api_key_id: str
    scope: str
    org_id: Optional[str]


def get_partner_context(event: Mapping[str, Any]) -> Optional[PartnerContext]:
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
