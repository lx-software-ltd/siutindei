"""Query filters for admin catalog and organization-scoped lists."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import ORG_STATUSES
from app.api.admin_request import _parse_uuid, _query_param
from app.db.models import Organization
from app.exceptions import ValidationError
from app.services.org_review import REVIEW_STATUSES
from app.utils import json_response

_EMAIL_PREFIX = re.compile(r"^[A-Za-z0-9@.+_-]{1,80}$")


@dataclass(frozen=True)
class OrganizationListFilters:
    """Optional filters on GET /organizations."""

    query: str | None = None
    review_status: str | None = None
    source: str | None = None
    status: str | None = None


def resolve_list_org_scope(
    event: Mapping[str, Any],
    managed_org_ids: Optional[set[str]],
) -> tuple[Optional[set[str]], dict[str, Any] | None]:
    """Return the org ids a list may include, or a 403 response.

    Admins with no ``org_id`` get ``None`` (no extra restriction).
    Managers stay inside ``managed_org_ids``. ``org_id`` narrows to one
    organization when the caller is allowed to see it.
    """
    raw = (_query_param(event, "org_id") or "").strip()
    if not raw:
        return managed_org_ids, None
    org_id = str(_parse_uuid(raw))
    if managed_org_ids is not None and org_id not in managed_org_ids:
        return None, json_response(
            403,
            {"error": "You don't have access to this organization"},
            event=event,
        )
    return {org_id}, None


def parse_organization_list_filters(
    event: Mapping[str, Any],
) -> OrganizationListFilters:
    """Read catalog filters. Blank values are ignored."""
    return OrganizationListFilters(
        query=_blank(_query_param(event, "q")),
        review_status=_choice(
            _query_param(event, "review_status"),
            REVIEW_STATUSES,
            "review_status",
        ),
        source=_blank(_query_param(event, "source")),
        status=_choice(_query_param(event, "status"), ORG_STATUSES, "status"),
    )


def list_organizations(
    session: Session,
    scope: Optional[set[str]],
    filters: OrganizationListFilters,
    limit: int,
    cursor: Optional[UUID],
) -> list[Organization]:
    """Cursor page of organizations matching scope and filters."""
    stmt = select(Organization)
    if scope is not None:
        stmt = stmt.where(Organization.id.in_(list(scope)))
    if filters.review_status:
        stmt = stmt.where(Organization.review_status == filters.review_status)
    if filters.source:
        stmt = stmt.where(Organization.source == filters.source)
    if filters.status:
        stmt = stmt.where(Organization.status == filters.status)
    if filters.query:
        pattern = f"%{_escape_like(filters.query)}%"
        stmt = stmt.where(Organization.name.ilike(pattern, escape="\\"))
    if cursor is not None:
        stmt = stmt.where(Organization.id > cursor)
    stmt = stmt.order_by(Organization.id).limit(limit)
    return list(session.scalars(stmt).all())


def cognito_email_prefix_filter(value: str | None) -> str | None:
    """Cognito ListUsers filter for an email prefix, or None when blank."""
    text = _blank(value)
    if text is None:
        return None
    if _EMAIL_PREFIX.fullmatch(text) is None:
        raise ValidationError(
            "q must be an email prefix (letters, digits, @ . + _ -)",
            field="q",
        )
    return f'email ^= "{text}"'


def _choice(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    text = _blank(value)
    if text is None:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _escape_like(pattern: str) -> str:
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
