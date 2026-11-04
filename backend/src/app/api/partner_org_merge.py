"""Partner access to organization merge. Full-access crud keys only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.admin_org_duplicates import merge_organizations_from_request
from app.api.partner_auth import PartnerContext, partner_actor, require_full_access


def handle_partner_org_merge(
    event: Mapping[str, Any],
    partner: PartnerContext,
) -> dict[str, Any]:
    """Merge organizations. Same body and result as the admin merge route.

    A full-access ``crud`` key is the partner equivalent of an admin.
    The actor is the authorizer subject when it is present, and
    ``api-key:<id>`` when the authorizer omits ``userSub``.
    """
    require_full_access(partner)
    return merge_organizations_from_request(
        event,
        merged_by=partner_actor(event, partner),
    )
