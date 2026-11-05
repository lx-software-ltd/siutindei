"""Partner access to organization rejection. Full-access crud keys only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.admin_enrichment import organization_tail
from app.api.admin_org_review_actions import apply_organization_rejection
from app.api.partner_auth import (
    PartnerContext,
    partner_actor,
    require_crud,
    require_full_access,
)
from app.utils import json_response


def handle_partner_org_reject(
    event: Mapping[str, Any],
    method: str,
    org_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    """Reject one organization.

    Same reason, notes, and listing status as an admin reject decision.
    A full-access ``crud`` key is the partner equivalent of an admin.
    The actor is the authorizer subject when it is present, and
    ``api-key:<id>`` when the authorizer omits ``userSub``.
    """
    require_full_access(partner)
    require_crud(partner)
    tail = organization_tail(str(event.get("path") or ""))
    if method != "POST" or tail != ["reject"] or not org_id:
        return json_response(404, {"error": "Not found"}, event=event)
    return apply_organization_rejection(
        event,
        org_id,
        reviewer=partner_actor(event, partner),
    )
