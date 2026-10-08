"""Partner read access to category-check reviews."""

from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_category_reviews import (
    _STATUSES,
    _VERDICTS,
    _choice,
    _encode_cursor,
    _optional_uuid,
    _parse_cursor,
    _query,
    _serialize,
)
from app.api.admin_crud import _handle_crud
from app.api.admin_request import parse_limit, _query_param
from app.api.admin_resources import _RESOURCE_CONFIG
from app.db.engine import get_engine
from app.db.models.category_scan import ActivityCategoryReview
from app.exceptions import ValidationError
from app.utils import json_response


def handle_partner_category_reviews(
    event: Mapping[str, Any],
    org_id: str | None,
) -> dict[str, Any]:
    """List category-check reviews visible to this API key."""
    status = _choice(_query_param(event, "status"), _STATUSES, "status")
    verdict = _choice(_query_param(event, "verdict"), _VERDICTS, "verdict")
    scoped_org_id = _scoped_org_id(event, org_id)
    query_text = (_query_param(event, "q") or "").strip()
    cursor = _parse_cursor(_query_param(event, "cursor"))
    limit = parse_limit(event)
    with Session(get_engine()) as session:
        rows = session.execute(
            _query(
                status=status,
                verdict=verdict,
                org_id=scoped_org_id,
                scan_run_id=None,
                proposed_category_id=_optional_uuid(
                    _query_param(event, "proposed_category_id"),
                    "proposed_category_id",
                ),
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
                "items": [_partner_item(_serialize(session, *row)) for row in page],
                "next_cursor": next_cursor,
            },
            event=event,
        )


def partner_get_activities(
    event: Mapping[str, Any],
    resource_id: str | None,
    managed_org_ids: set[str] | None,
) -> dict[str, Any]:
    """List or fetch activities and attach the latest category review."""
    config = _RESOURCE_CONFIG["activities"]
    response = _handle_crud(event, "GET", config, resource_id, managed_org_ids)
    if response.get("statusCode") != 200:
        return response
    payload = json.loads(response["body"])
    with Session(get_engine()) as session:
        if isinstance(payload.get("items"), list):
            reviews = _latest_by_activity(
                session,
                [UUID(item["id"]) for item in payload["items"]],
            )
            for item in payload["items"]:
                item["category_review"] = reviews.get(item["id"])
        elif payload.get("id"):
            reviews = _latest_by_activity(session, [UUID(payload["id"])])
            payload["category_review"] = reviews.get(payload["id"])
    response["body"] = json.dumps(payload, default=str)
    return response


def _scoped_org_id(event: Mapping[str, Any], org_id: str | None) -> UUID | None:
    requested = _optional_uuid(_query_param(event, "org_id"), "org_id")
    if org_id is None:
        return requested
    scoped = UUID(org_id)
    if requested is not None and requested != scoped:
        raise ValidationError(
            "org_id is outside this API key",
            field="org_id",
        )
    return scoped


def _latest_by_activity(
    session: Session,
    activity_ids: list[UUID],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not activity_ids:
        return latest
    rows = session.execute(
        _query(
            status=None,
            verdict=None,
            org_id=None,
            scan_run_id=None,
            proposed_category_id=None,
            query_text="",
            cursor=None,
        ).where(ActivityCategoryReview.activity_id.in_(activity_ids))
    ).all()
    for row in rows:
        review = row[0]
        key = str(review.activity_id)
        if key in latest:
            continue
        latest[key] = _partner_item(_serialize(session, *row))
    return latest


def _partner_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "activity_id": item["activity_id"],
        "activity_name": item["activity_name"],
        "org_id": item["org_id"],
        "org_name": item["org_name"],
        "current_category_id": item["current_category_id"],
        "current_category_name": item["current_category_name"],
        "verdict": item["verdict"],
        "proposed_category_id": item["proposed_category_id"],
        "proposed_category_name": item["proposed_category_name"],
        "suggestion_id": item["suggestion_id"],
        "confidence": item["confidence"],
        "status": item["status"],
        "created_at": item["created_at"],
    }
