"""Partner access to organization merge. Full-access crud keys only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.admin_org_duplicates import _merge
from app.api.partner_auth import PartnerContext, require_full_access


def handle_partner_org_merge(
    event: Mapping[str, Any],
    partner: PartnerContext,
) -> dict[str, Any]:
    """Merge organizations. Same body as the admin merge route."""
    require_full_access(partner)
    return _merge(event)
