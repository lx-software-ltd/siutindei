"""Admin list and decision routes for category-check reviews."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from typing import Mapping
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.db.engine import get_engine
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import CategorySuggestion
from app.exceptions import NotFoundError, ValidationError
from app.services.category_suggestions.reviews import apply_review_decision
from app.utils import json_response

_STATUSES = {
    "confirmed",
    "pending",
    "auto_applied",
    "applied",
    "dismissed",
    "reverted",
}
_VERDICTS = {"confirm", "reassign", "propose"}


def handle_reviews(
    event: Mapping[str, Any],
    method: str,
    sub_resource: str | None,
) -> dict[str, Any]:
    """GET /reviews, GET /reviews/{id}, and POST /reviews/{id}."""
    if method == "GET" and sub_resource is None:
        return _list(event)
    if method == "GET" and sub_resource:
        return _detail(event, sub_resource)
    if method == "POST" and sub_resource:
        return _decide(event, sub_resource)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    limit = parse_limit(event)
    status = _choice(_query_param(event, "status"), _STATUSES, "status")
    verdict = _choice(_query_param(event, "verdict"), _VERDICTS, "verdict")
    org_id = _optional_uuid(_query_param(event, "org_id"), "org_id")
    scan_run_id = _optional_uuid(_query_param(event, "scan_run_id"), "scan_run_id")
    query_text = (_query_param(event, "q") or "").strip()
    cursor = _parse_cursor(_query_param(event, "cursor"))
    with Session(get_engine()) as session:
        rows = session.execute(
            _query(
                status=status,
                verdict=verdict,
                org_id=org_id,
                scan_run_id=scan_run_id,
                query_text=query_text,
                cursor=cursor,
            ).limit(limit + 1)
        ).all()
        page = rows[:limit]
        next_cursor = (
            _encode_cursor(page[-1][0]) if len(rows) > limit and page else None
        )
        return json_response(
            200,
            {
                "items": [_serialize(session, *row) for row in page],
                "next_cursor": next_cursor,
            },
            event=event,
        )


def _detail(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    review_id = _parse_uuid(raw_id)
    with Session(get_engine()) as session:
        row = _one(session, review_id)
        if row is None:
            raise NotFoundError("category review", str(review_id))
        return json_response(200, _serialize(session, *row), event=event)


def _decide(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    review_id = _parse_uuid(raw_id)
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        review = session.get(ActivityCategoryReview, review_id)
        if review is None:
            raise NotFoundError("category review", str(review_id))
        apply_review_decision(
            session,
            review,
            body,
            decided_by=_get_user_sub(event),
        )
        session.commit()
        row = _one(session, review_id)
        if row is None:
            raise NotFoundError("category review", str(review_id))
        return json_response(200, _serialize(session, *row), event=event)


def _query(
    *,
    status: str | None,
    verdict: str | None,
    org_id: UUID | None,
    scan_run_id: UUID | None,
    query_text: str,
    cursor: tuple[datetime, UUID] | None,
):
    current = ActivityCategory.__table__.alias("current_category")
    proposed = ActivityCategory.__table__.alias("proposed_category")
    query = (
        select(
            ActivityCategoryReview,
            Activity.name,
            Organization.name,
            current.c.name,
            proposed.c.name,
            CategorySuggestion.suggested_name,
        )
        .join(Activity, Activity.id == ActivityCategoryReview.activity_id)
        .join(Organization, Organization.id == ActivityCategoryReview.org_id)
        .outerjoin(current, current.c.id == ActivityCategoryReview.current_category_id)
        .outerjoin(
            proposed, proposed.c.id == ActivityCategoryReview.proposed_category_id
        )
        .outerjoin(
            CategorySuggestion,
            CategorySuggestion.id == ActivityCategoryReview.suggestion_id,
        )
    )
    if status:
        query = query.where(ActivityCategoryReview.status == status)
    if verdict:
        query = query.where(ActivityCategoryReview.verdict == verdict)
    if org_id is not None:
        query = query.where(ActivityCategoryReview.org_id == org_id)
    if scan_run_id is not None:
        query = query.where(ActivityCategoryReview.scan_run_id == scan_run_id)
    if query_text:
        like = _like(query_text)
        query = query.where(
            or_(
                func.lower(Activity.name).like(like, escape="\\"),
                func.lower(Organization.name).like(like, escape="\\"),
            )
        )
    if cursor is not None:
        created_at, review_id = cursor
        query = query.where(
            or_(
                ActivityCategoryReview.created_at < created_at,
                and_(
                    ActivityCategoryReview.created_at == created_at,
                    ActivityCategoryReview.id < review_id,
                ),
            )
        )
    return query.order_by(
        ActivityCategoryReview.created_at.desc(),
        ActivityCategoryReview.id.desc(),
    )


def _one(session: Session, review_id: UUID):
    return session.execute(
        _query(
            status=None,
            verdict=None,
            org_id=None,
            scan_run_id=None,
            query_text="",
            cursor=None,
        ).where(ActivityCategoryReview.id == review_id)
    ).one_or_none()


def _serialize(
    session: Session,
    review: ActivityCategoryReview,
    activity_name: str,
    org_name: str,
    current_name: str | None,
    proposed_name: str | None,
    suggested_name: str | None,
) -> dict[str, Any]:
    del session
    return {
        "id": str(review.id),
        "scan_run_id": str(review.scan_run_id),
        "activity_id": str(review.activity_id),
        "activity_name": activity_name,
        "org_id": str(review.org_id),
        "org_name": org_name,
        "current_category_id": _text(review.current_category_id),
        "current_category_name": current_name,
        "verdict": review.verdict,
        "proposed_category_id": _text(review.proposed_category_id),
        "proposed_category_name": proposed_name or suggested_name,
        "suggestion_id": _text(review.suggestion_id),
        "confidence": None if review.confidence is None else float(review.confidence),
        "rationale": review.rationale,
        "status": review.status,
        "previous_category_id": _text(review.previous_category_id),
        "decided_by": review.decided_by,
        "decided_at": _iso(review.decided_at),
        "created_at": _iso(review.created_at),
    }


def _choice(value: str | None, allowed: set[str], field: str) -> str | None:
    if value in (None, ""):
        return None
    if value not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return value


def _optional_uuid(value: str | None, field: str) -> UUID | None:
    if not value:
        return None
    return _parse_uuid(value, field)


def _parse_uuid(value: str, field: str = "id") -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid UUID: {value}", field=field) from exc


def _like(value: str) -> str:
    escaped = (
        value.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _encode_cursor(review: ActivityCategoryReview) -> str:
    payload = json.dumps(
        {"created_at": _iso(review.created_at), "id": str(review.id)}
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _parse_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        return created_at, UUID(str(payload["id"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
