"""Partner access to website enrichment. Full-access crud keys only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.admin_enrichment import (
    handle_enrichment_settings,
    perform_org_enrichment,
)
from app.api.partner_auth import (
    PartnerContext,
    partner_actor,
    require_crud,
    require_full_access,
)


def handle_partner_org_enrichment(
    event: Mapping[str, Any],
    method: str,
    org_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    """Read, start, apply, or dismiss enrichment for one organization.

    Same paths and bodies as the admin organization enrichment routes.
    A full-access ``crud`` key may apply and dismiss.
    """
    require_full_access(partner)
    require_crud(partner)
    return perform_org_enrichment(
        event,
        method,
        org_id,
        actor=partner_actor(event, partner),
        allow_decide=True,
    )


def handle_partner_enrichment_settings(
    event: Mapping[str, Any],
    method: str,
    partner: PartnerContext,
) -> dict[str, Any]:
    """Read or update the website enrichment settings singleton."""
    require_full_access(partner)
    require_crud(partner)
    return handle_enrichment_settings(event, method)
