"""Admin organization review queue: list, summary, and detail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_org_review_actions import (
    handle_bulk,
    handle_decision,
)
from app.api.admin_request import (
    _encode_cursor,
    _parse_cursor,
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
from app.utils import json_response

_ORG_STATUSES = (
    "operational",
    "closed_temporarily",
    "closed_permanently",
    "hidden",
)


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
    cursor = _parse_cursor(_query_param(event, "cursor"))
    filters = _parse_filters(event)
    needs_scan = bool(filters.issue) or filters.has_blockers is not None
    with Session(get_engine()) as session:
        organizations = _load_filtered_organizations(
            session,
            filters,
            cursor,
            None if needs_scan else limit + 1,
        )
        snapshots = load_snapshots(session, organizations)
        matched = [item for item in snapshots if _matches_issue(item, filters)]
        page = matched[:limit]
        has_more = len(matched) > limit
        next_cursor = (
            _encode_cursor(page[-1].organization.id) if has_more and page else None
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
        organizations = list(session.scalars(select(Organization)).all())
        snapshots = load_snapshots(session, organizations)
        return json_response(200, _summarize(snapshots), event=event)


def _summarize(snapshots: list[OrgReviewSnapshot]) -> dict[str, Any]:
    by_review = {status: 0 for status in REVIEW_STATUSES}
    by_source: dict[str, int] = {}
    by_status_source: dict[str, int] = {}
    by_issue: dict[str, int] = {}
    with_blockers = 0
    for snapshot in snapshots:
        org = snapshot.organization
        by_review[org.review_status] = by_review.get(org.review_status, 0) + 1
        source_key = org.source or "unknown"
        by_source[source_key] = by_source.get(source_key, 0) + 1
        status_source_key = org.status_source or "unknown"
        by_status_source[status_source_key] = (
            by_status_source.get(status_source_key, 0) + 1
        )
        if snapshot.blocker_count:
            with_blockers += 1
        seen: set[str] = set()
        for issue in snapshot.issues:
            if issue.code in seen:
                continue
            seen.add(issue.code)
            by_issue[issue.code] = by_issue.get(issue.code, 0) + 1
    return {
        "total": len(snapshots),
        "by_review_status": by_review,
        "by_source": by_source,
        "by_status_source": by_status_source,
        "by_issue": by_issue,
        "with_blockers": with_blockers,
    }


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
    cursor: UUID | None,
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
    if cursor is not None:
        stmt = stmt.where(Organization.id > cursor)
    stmt = stmt.order_by(Organization.id)
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
        _ORG_STATUSES,
        "status",
    )
    source = _blank_to_none(_query_param(event, "source"))
    issue = _blank_to_none(_query_param(event, "issue"))
    query = _blank_to_none(_query_param(event, "q"))
    import_job_raw = _blank_to_none(_query_param(event, "import_job_id"))
    import_job_id = _parse_uuid(import_job_raw) if import_job_raw else None
    has_blockers = _parse_optional_bool(_query_param(event, "has_blockers"))
    return ReviewListFilters(
        review_status=review_status,
        source=source,
        import_job_id=import_job_id,
        status=status,
        issue=issue,
        has_blockers=has_blockers,
        query=query,
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
