"""Admin routes for category suggestions."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Mapping
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_category_suggestion_settings import handle_settings
from app.api.admin_request import _parse_body, _query_param, parse_limit
from app.db.engine import get_engine
from app.db.models import Activity, Organization
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.category_suggestions.decisions import apply_decision
from app.services.category_suggestions.events import enqueue_enrichment
from app.utils import json_response

_STATUSES = {"pending", "approved", "merged", "rejected"}
_ENRICHMENT = {"none", "queued", "running", "done", "failed"}


def _handle_admin_category_suggestions(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/category-suggestions."""
    if resource_id == "settings":
        return handle_settings(event, method, sub_resource)
    if method == "GET" and resource_id is None:
        return _handle_list(event)
    if method == "GET" and resource_id == "summary":
        return _handle_summary(event)
    if method == "GET" and resource_id and sub_resource is None:
        return _handle_detail(event, resource_id)
    if method == "POST" and resource_id and sub_resource == "decision":
        return _handle_decision(event, resource_id)
    if method == "POST" and resource_id and sub_resource == "enrich":
        return _handle_enrich(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _handle_list(event: Mapping[str, Any]) -> dict[str, Any]:
    limit = parse_limit(event)
    status = _optional_choice(_query_param(event, "status"), _STATUSES, "status")
    enrichment = _optional_choice(
        _query_param(event, "enrichment_status"),
        _ENRICHMENT,
        "enrichment_status",
    )
    import_job_id = _optional_uuid(
        _query_param(event, "import_job_id"), "import_job_id"
    )
    query_text = (_query_param(event, "q") or "").strip()
    cursor = _parse_list_cursor(_query_param(event, "cursor"))
    with Session(get_engine()) as session:
        rows = list(
            session.scalars(
                _list_query(
                    status=status,
                    enrichment=enrichment,
                    import_job_id=import_job_id,
                    query_text=query_text,
                    cursor=cursor,
                ).limit(limit + 1)
            ).all()
        )
        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = _encode_list_cursor(page[-1]) if has_more and page else None
        return json_response(
            200,
            {
                "items": [serialize_suggestion(row) for row in page],
                "next_cursor": next_cursor,
            },
            event=event,
        )


def _handle_summary(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        return json_response(200, _summary(session), event=event)


def _handle_detail(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    suggestion_id = _parse_uuid(resource_id)
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            raise NotFoundError("category suggestion", str(suggestion_id))
        payload = serialize_suggestion(suggestion)
        payload["activities"] = _links(session, suggestion.id)
        return json_response(200, payload, event=event)


def _handle_decision(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    suggestion_id = _parse_uuid(resource_id)
    body = _object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            raise NotFoundError("category suggestion", str(suggestion_id))
        apply_decision(
            session,
            suggestion,
            body,
            decided_by=_get_user_sub(event),
        )
        payload = serialize_suggestion(suggestion)
        session.commit()
        return json_response(200, payload, event=event)


def _handle_enrich(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    suggestion_id = _parse_uuid(resource_id)
    _object_body(event)
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            raise NotFoundError("category suggestion", str(suggestion_id))
    enqueue_enrichment([str(suggestion_id)], force=True)
    return json_response(
        202,
        {"id": str(suggestion_id), "status": "queued"},
        event=event,
    )


def serialize_suggestion(row: CategorySuggestion) -> dict[str, Any]:
    """Serialize one suggestion for the admin API."""
    confidence = None if row.confidence is None else float(row.confidence)
    return {
        "id": str(row.id),
        "fingerprint": row.fingerprint,
        "requested_name": row.requested_name,
        "source": row.source,
        "status": row.status,
        "enrichment_status": row.enrichment_status,
        "enrichment_error": row.enrichment_error,
        "enriched_at": _iso(row.enriched_at),
        "model_used": row.model_used,
        "suggested_name": row.suggested_name,
        "name_translations": row.name_translations or {},
        "suggested_parent_id": _uuid_text(row.suggested_parent_id),
        "maps_to_category_id": _uuid_text(row.maps_to_category_id),
        "confidence": confidence,
        "rationale": row.rationale,
        "alternatives": row.alternatives or {},
        "usage": row.usage or {},
        "created_category_id": _uuid_text(row.created_category_id),
        "merged_into_category_id": _uuid_text(row.merged_into_category_id),
        "decided_by": row.decided_by,
        "decided_at": _iso(row.decided_at),
        "decision_notes": row.decision_notes,
        "activity_count": int(row.activity_count or 0),
        "reopened_at": _iso(row.reopened_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _summary(session: Session) -> dict[str, Any]:
    by_status = {
        status: int(count)
        for status, count in session.execute(
            select(CategorySuggestion.status, func.count()).group_by(
                CategorySuggestion.status
            )
        ).all()
    }
    by_enrichment = {
        status: int(count)
        for status, count in session.execute(
            select(CategorySuggestion.enrichment_status, func.count()).group_by(
                CategorySuggestion.enrichment_status
            )
        ).all()
    }
    pending_activities = int(
        session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.category_id == PENDING_CATEGORY_ID)
        )
        or 0
    )
    month_start = datetime.now(timezone.utc).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    month_rows = session.scalars(
        select(CategorySuggestion).where(CategorySuggestion.enriched_at >= month_start)
    ).all()
    month_cost = 0.0
    for row in month_rows:
        usage = row.usage if isinstance(row.usage, dict) else {}
        month_cost += float(usage.get("cost_usd") or 0)
    return {
        "by_status": by_status,
        "by_enrichment_status": by_enrichment,
        "pending_activity_total": pending_activities,
        "month_cost_usd": round(month_cost, 6),
    }


def _links(session: Session, suggestion_id: UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(CategorySuggestionActivity, Activity.name, Organization.name)
        .join(Activity, Activity.id == CategorySuggestionActivity.activity_id)
        .join(Organization, Organization.id == CategorySuggestionActivity.org_id)
        .where(CategorySuggestionActivity.suggestion_id == suggestion_id)
        .order_by(CategorySuggestionActivity.created_at.desc())
    ).all()
    return [
        {
            "activity_id": str(link.activity_id),
            "activity_name": activity_name,
            "org_id": str(link.org_id),
            "org_name": org_name,
            "import_job_id": _uuid_text(link.import_job_id),
            "requested_name": link.requested_name,
            "created_at": _iso(link.created_at),
        }
        for link, activity_name, org_name in rows
    ]


def _list_query(
    *,
    status: str | None,
    enrichment: str | None,
    import_job_id: UUID | None,
    query_text: str,
    cursor: tuple[int, datetime, UUID] | None,
):
    query = select(CategorySuggestion)
    if status:
        query = query.where(CategorySuggestion.status == status)
    if enrichment:
        query = query.where(CategorySuggestion.enrichment_status == enrichment)
    if import_job_id is not None:
        linked = (
            select(CategorySuggestionActivity.suggestion_id)
            .where(CategorySuggestionActivity.import_job_id == import_job_id)
            .where(CategorySuggestionActivity.suggestion_id == CategorySuggestion.id)
        )
        query = query.where(linked.exists())
    if query_text:
        like = f"%{query_text.casefold()}%"
        query = query.where(
            or_(
                func.lower(CategorySuggestion.requested_name).like(like),
                func.lower(func.coalesce(CategorySuggestion.suggested_name, "")).like(
                    like
                ),
            )
        )
    if cursor is not None:
        count, created_at, suggestion_id = cursor
        query = query.where(
            or_(
                CategorySuggestion.activity_count < count,
                and_(
                    CategorySuggestion.activity_count == count,
                    CategorySuggestion.created_at < created_at,
                ),
                and_(
                    CategorySuggestion.activity_count == count,
                    CategorySuggestion.created_at == created_at,
                    CategorySuggestion.id < suggestion_id,
                ),
            )
        )
    return query.order_by(
        CategorySuggestion.activity_count.desc(),
        CategorySuggestion.created_at.desc(),
        CategorySuggestion.id.desc(),
    )


def _object_body(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    if not str(raw).strip():
        return {}
    body = _parse_body(event)
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    return body


def _optional_choice(
    value: str | None,
    allowed: set[str],
    field: str,
) -> str | None:
    if value in (None, ""):
        return None
    if value not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return value


def _optional_uuid(value: str | None, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    return _parse_uuid(value, field)


def _parse_uuid(value: str, field: str = "id") -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Invalid UUID: {value}", field=field) from exc


def _encode_list_cursor(row: CategorySuggestion) -> str:
    import base64
    import json

    payload = json.dumps(
        {
            "activity_count": int(row.activity_count or 0),
            "created_at": _iso(row.created_at),
            "id": str(row.id),
        }
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _parse_list_cursor(value: str | None) -> tuple[int, datetime, UUID] | None:
    if value in (None, ""):
        return None
    import base64
    import json

    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        return (
            int(payload["activity_count"]),
            created_at,
            UUID(str(payload["id"])),
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _uuid_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
