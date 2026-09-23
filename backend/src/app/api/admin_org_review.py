"""Admin organization review queue: list, summary, and detail."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import ORG_STATUSES
from app.api.admin_org_review_actions import (
    handle_bulk,
    handle_decision,
)
from app.api.admin_request import (
    _decode_cursor,
    _query_param,
    parse_limit,
)
from app.api.admin_resource_activity import _serialize_activity
from app.api.admin_resource_location import _serialize_location
from app.api.admin_resource_organization import _serialize_organization
from app.db.engine import get_engine
from app.db.models import Organization
from app.exceptions import NotFoundError, ValidationError
from app.services.org_review import (
    REVIEW_STATUSES,
    OrgReviewSnapshot,
    load_snapshots,
)
from app.services.org_review_sql import (
    BLOCKER_ISSUE_CODES,
    has_blocker_clause,
    issue_clause,
    summarize_catalog,
)
from app.utils import json_response

_REVIEW_SORTS = ("name", "last_imported_at")


@dataclass(frozen=True)
class ReviewListFilters:
    """Query filters for the review queue."""

    review_status: str | None
    source: str | None
    import_job_id: UUID | None
    status: str | None
    issue: str | None
    has_blockers: bool | None
    query: str | None
    sort: str


def _handle_admin_org_review(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/org-review routes."""
    if method == "GET" and resource_id is None:
        return _handle_list(event)
    if method == "GET" and resource_id == "summary":
        return _handle_summary(event)
    if method == "POST" and resource_id == "bulk":
        return handle_bulk(event)
    if method == "GET" and resource_id and sub_resource is None:
        return _handle_detail(event, resource_id)
    if method == "POST" and resource_id and sub_resource == "decision":
        return handle_decision(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _handle_list(event: Mapping[str, Any]) -> dict[str, Any]:
    limit = parse_limit(event)
    filters = _parse_filters(event)
    cursor = _parse_review_cursor(_query_param(event, "cursor"), filters.sort)
    warning_scan = _needs_warning_scan(filters)
    with Session(get_engine()) as session:
        organizations = _load_filtered_organizations(
            session,
            filters,
            cursor,
            None if warning_scan else limit + 1,
        )
        snapshots = load_snapshots(session, organizations)
        matched = (
            [item for item in snapshots if _matches_issue(item, filters)]
            if warning_scan
            else snapshots
        )
        page = matched[:limit]
        has_more = len(matched) > limit
        next_cursor = (
            _encode_review_cursor(page[-1].organization, filters.sort)
            if has_more and page
            else None
        )
        return json_response(
            200,
            {
                "items": [_serialize_queue_item(item) for item in page],
                "next_cursor": next_cursor,
            },
            event=event,
        )


def _handle_summary(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        return json_response(200, summarize_catalog(session), event=event)


def _needs_warning_scan(filters: ReviewListFilters) -> bool:
    """Warning codes are matched in Python after the SQL page filters."""
    return bool(filters.issue) and filters.issue not in BLOCKER_ISSUE_CODES


def _handle_detail(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    org_id = _parse_uuid(resource_id)
    with Session(get_engine()) as session:
        organization = session.get(Organization, org_id)
        if organization is None:
            raise NotFoundError("organizations", resource_id)
        snapshot = load_snapshots(session, [organization])[0]
        return json_response(200, _serialize_detail(snapshot), event=event)


def _load_filtered_organizations(
    session: Session,
    filters: ReviewListFilters,
    cursor: _ReviewCursor | None,
    limit: int | None,
) -> list[Organization]:
    stmt = select(Organization)
    if filters.review_status:
        stmt = stmt.where(Organization.review_status == filters.review_status)
    if filters.source:
        stmt = stmt.where(Organization.source == filters.source)
    if filters.import_job_id is not None:
        stmt = stmt.where(Organization.import_job_id == filters.import_job_id)
    if filters.status:
        stmt = stmt.where(Organization.status == filters.status)
    if filters.query:
        pattern = f"%{_escape_like(filters.query)}%"
        stmt = stmt.where(Organization.name.ilike(pattern, escape="\\"))
    if filters.has_blockers is True:
        stmt = stmt.where(has_blocker_clause())
    elif filters.has_blockers is False:
        stmt = stmt.where(~has_blocker_clause())
    if filters.issue in BLOCKER_ISSUE_CODES:
        clause = issue_clause(filters.issue)
        if clause is not None:
            stmt = stmt.where(clause)
    stmt = _apply_review_cursor(stmt, filters.sort, cursor)
    stmt = _apply_review_order(stmt, filters.sort)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def _matches_issue(snapshot: OrgReviewSnapshot, filters: ReviewListFilters) -> bool:
    if filters.has_blockers is True and snapshot.blocker_count == 0:
        return False
    if filters.has_blockers is False and snapshot.blocker_count > 0:
        return False
    if filters.issue and not any(
        issue.code == filters.issue for issue in snapshot.issues
    ):
        return False
    return True


def _parse_filters(event: Mapping[str, Any]) -> ReviewListFilters:
    review_status = _optional_choice(
        _query_param(event, "review_status"),
        REVIEW_STATUSES,
        "review_status",
    )
    status = _optional_choice(
        _query_param(event, "status"),
        ORG_STATUSES,
        "status",
    )
    source = _blank_to_none(_query_param(event, "source"))
    issue = _blank_to_none(_query_param(event, "issue"))
    query = _blank_to_none(_query_param(event, "q"))
    import_job_raw = _blank_to_none(_query_param(event, "import_job_id"))
    import_job_id = _parse_uuid(import_job_raw) if import_job_raw else None
    has_blockers = _parse_optional_bool(_query_param(event, "has_blockers"))
    sort = _optional_choice(_query_param(event, "sort"), _REVIEW_SORTS, "sort")
    return ReviewListFilters(
        review_status=review_status,
        source=source,
        import_job_id=import_job_id,
        status=status,
        issue=issue,
        has_blockers=has_blockers,
        query=query,
        sort=sort or "name",
    )


def _serialize_queue_item(snapshot: OrgReviewSnapshot) -> dict[str, Any]:
    org = snapshot.organization
    return {
        "id": str(org.id),
        "name": org.name,
        "status": org.status,
        "review_status": org.review_status,
        "source": org.source,
        "status_source": org.status_source,
        "description_source": org.description_source,
        "import_job_id": str(org.import_job_id) if org.import_job_id else None,
        "last_imported_at": org.last_imported_at,
        "reviewed_at": org.reviewed_at,
        "reviewed_by": org.reviewed_by,
        "place_id": org.place_id,
        "location_count": len(snapshot.locations),
        "activity_count": len(snapshot.activities),
        "pricing_count": sum(snapshot.pricing_counts.values()),
        "schedule_count": sum(snapshot.schedule_counts.values()),
        "issues": [issue.to_dict() for issue in snapshot.issues],
        "completeness": snapshot.completeness,
        "blocker_count": snapshot.blocker_count,
        "warning_count": snapshot.warning_count,
    }


def _serialize_detail(snapshot: OrgReviewSnapshot) -> dict[str, Any]:
    body = _serialize_queue_item(snapshot)
    body["organization"] = _serialize_organization(snapshot.organization)
    body["locations"] = [
        _serialize_location(location) for location in snapshot.locations
    ]
    body["activities"] = [
        _serialize_activity(activity) for activity in snapshot.activities
    ]
    return body


def _optional_choice(
    value: str | None,
    allowed: tuple[str, ...],
    field: str,
) -> str | None:
    text = _blank_to_none(value)
    if text is None:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def _parse_optional_bool(value: str | None) -> bool | None:
    text = _blank_to_none(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    raise ValidationError("has_blockers must be a boolean", field="has_blockers")


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field="id") from exc


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _escape_like(pattern: str) -> str:
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class _ReviewCursor:
    org_id: UUID
    name: str | None
    last_imported_at: datetime | None


def _encode_review_cursor(organization: Organization, sort: str) -> str:
    imported_at = organization.last_imported_at
    payload = json.dumps(
        {
            "sort": sort,
            "id": str(organization.id),
            "name": organization.name,
            "last_imported_at": (
                imported_at.isoformat() if imported_at is not None else None
            ),
        }
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _parse_review_cursor(value: str | None, sort: str) -> _ReviewCursor | None:
    if value is None or value == "":
        return None
    try:
        payload = _decode_cursor(value)
        if payload.get("sort") != sort or "id" not in payload:
            raise ValueError("sort")
        imported_raw = payload.get("last_imported_at")
        imported_at = datetime.fromisoformat(imported_raw) if imported_raw else None
        return _ReviewCursor(
            org_id=UUID(payload["id"]),
            name=payload.get("name"),
            last_imported_at=imported_at,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc


def _apply_review_order(stmt: Any, sort: str) -> Any:
    if sort == "last_imported_at":
        return stmt.order_by(
            Organization.last_imported_at.desc().nulls_last(),
            Organization.id.desc(),
        )
    return stmt.order_by(Organization.name, Organization.id)


def _apply_review_cursor(stmt: Any, sort: str, cursor: _ReviewCursor | None) -> Any:
    if cursor is None:
        return stmt
    if sort == "name":
        name = cursor.name or ""
        return stmt.where(
            or_(
                Organization.name > name,
                and_(
                    Organization.name == name,
                    Organization.id > cursor.org_id,
                ),
            )
        )
    if cursor.last_imported_at is None:
        return stmt.where(
            and_(
                Organization.last_imported_at.is_(None),
                Organization.id < cursor.org_id,
            )
        )
    return stmt.where(
        or_(
            Organization.last_imported_at < cursor.last_imported_at,
            and_(
                Organization.last_imported_at == cursor.last_imported_at,
                Organization.id < cursor.org_id,
            ),
            Organization.last_imported_at.is_(None),
        )
    )
