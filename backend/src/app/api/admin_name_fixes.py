"""Alias for /v1/admin/name-fixes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.data_quality.proposal_lifecycle import ProposalKind


def handle_name_fixes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/name-fixes routes."""
    from app.api.admin_proposals import handle_proposals

    return handle_proposals(
        event,
        method,
        ProposalKind.NAMES,
        resource_id,
        sub_resource,
    )
