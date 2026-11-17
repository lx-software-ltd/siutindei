"""Catalog import for a full-access crud partner key."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_imports_fields import manager_ids_match
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_org_review_actions import (
    ReviewBlockedError,
    _apply_decision,
)
from app.api.admin_request import _parse_body, _query_param
from app.api.admin_resource_organization import _apply_parent_verified
from app.api.partner_auth import (
    PartnerContext,
    partner_actor,
    require_crud,
    require_full_access,
)
from app.db.engine import get_engine
from app.db.models import Organization
from app.exceptions import ValidationError
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_APPLIED_STATUSES = frozenset({"created", "unchanged"})
_FLAG_NAMES = ("dry_run", "mark_parent_verified", "approve")


def handle_partner_imports(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    """Import a catalog file with the full-access crud partner key.

    The body is the admin import JSON. ``manager_id``, ``dry_run``,
    ``mark_parent_verified``, and ``approve`` are query parameters.
    The file cannot set the parent-verified flag or the review status.
    """
    require_full_access(partner)
    require_crud(partner)
    if method != "POST" or resource_id:
        return json_response(404, {"error": "Not found"}, event=event)

    flags = _flags(event)
    payload = _parse_body(event)
    if not isinstance(payload, dict):
        raise ValidationError("Import file must be a JSON object")
    manager_id = resolve_import_manager(
        payload,
        _query_param(event, "manager_id"),
        _catalog_manager_id(),
    )
    if flags["dry_run"] and (flags["mark_parent_verified"] or flags["approve"]):
        raise ValidationError(
            "mark_parent_verified and approve require a live import",
            field="dry_run",
        )

    actor = partner_actor(event, partner)
    with Session(get_engine()) as session:
        if not flags["dry_run"]:
            _set_session_audit_context(session, event, user_id=actor)
        summary, results = process_import_payload(
            session,
            payload,
            [],
            dry_run=flags["dry_run"],
            allow_org_updates=False,
            catalog_manager_id=manager_id,
        )
        verified, approved, blocked = _apply_flags(
            session,
            results,
            mark_parent_verified=flags["mark_parent_verified"],
            approve=flags["approve"],
            reviewer=actor,
        )
        if flags["dry_run"]:
            session.rollback()
        else:
            session.commit()

    logger.info(
        "Partner catalog import",
        extra={
            "dry_run": flags["dry_run"],
            "organizations_created": summary.get("organizations", {}).get("created", 0),
            "verified": len(verified),
            "approved": len(approved),
            "blocked": len(blocked),
        },
    )
    return json_response(
        200,
        {
            "summary": summary,
            "results": results,
            "parent_verified": verified,
            "approved": approved,
            "blocked": blocked,
        },
        event=event,
    )


def resolve_import_manager(
    payload: dict[str, Any],
    requested: str | None,
    catalog: str | None,
) -> str:
    """Fill ``default_manager_id`` and return the catalog manager.

    A placeholder or blank file value is absent. The query value wins,
    then a UUID already in the file, then ``BOARD_CATALOG_MANAGER_ID``.
    When the environment variable is set, every other value must match
    it. The check happens before the import writes.
    """
    file_manager = _uuid_or_none(payload.get("default_manager_id"))
    chosen = _uuid_or_none(requested) or file_manager or _uuid_or_none(catalog)
    if chosen is None:
        raise ValidationError(
            "default_manager_id must be a UUID",
            field="default_manager_id",
        )
    if catalog and not manager_ids_match(chosen, catalog):
        raise ValidationError(
            "manager_id must be the catalog manager",
            field="manager_id",
        )
    if file_manager and not manager_ids_match(file_manager, chosen):
        raise ValidationError(
            "manager_id must match default_manager_id",
            field="manager_id",
        )
    payload["default_manager_id"] = chosen
    return chosen


def _apply_flags(
    session: Session,
    results: list[dict[str, Any]],
    *,
    mark_parent_verified: bool,
    approve: bool,
    reviewer: str,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Verify and approve organisations this file created or matched."""
    verified: list[str] = []
    approved: list[str] = []
    blocked: list[dict[str, Any]] = []
    if not mark_parent_verified and not approve:
        return verified, approved, blocked
    for org_id in _target_ids(results):
        organization = session.get(Organization, UUID(org_id))
        if organization is None:
            continue
        if mark_parent_verified:
            _apply_parent_verified(organization, {"parent_verified": True})
            verified.append(org_id)
        if not approve:
            continue
        try:
            with session.begin_nested():
                _apply_decision(
                    session,
                    organization,
                    "approve",
                    force=False,
                    notes=None,
                    status=None,
                    reviewer_sub=reviewer,
                    notes_provided=False,
                )
                session.flush()
        except ReviewBlockedError as exc:
            blocked.append(
                {
                    "org_id": org_id,
                    "message": exc.message,
                    "issues": [issue.to_dict() for issue in exc.issues],
                }
            )
            continue
        approved.append(org_id)
    return verified, approved, blocked


def _target_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        str(result["id"])
        for result in results
        if result.get("type") == "organizations"
        and result.get("status") in _APPLIED_STATUSES
        and result.get("id")
    ]


def _flags(event: Mapping[str, Any]) -> dict[str, bool]:
    return {name: _flag(event, name) for name in _FLAG_NAMES}


def _flag(event: Mapping[str, Any], name: str) -> bool:
    raw = _query_param(event, name)
    if raw in (None, ""):
        return False
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ValidationError(f"{name} must be true or false", field=name)


def _catalog_manager_id() -> str | None:
    value = os.getenv("BOARD_CATALOG_MANAGER_ID", "").strip()
    return value or None


def _uuid_or_none(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return str(UUID(value.strip()))
    except (ValueError, TypeError):
        return None
