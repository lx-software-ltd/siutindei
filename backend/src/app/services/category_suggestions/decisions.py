"""Admin decisions that approve, map, or reject a suggestion."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.db.repositories import ActivityCategoryRepository
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.exceptions import ValidationError
from app.services.activity_categories import create_activity_category

_DECIDABLE = {"pending", "rejected"}
_ACTIONS = {"approve", "map", "reject"}


def apply_decision(
    session: Session,
    suggestion: CategorySuggestion,
    body: dict[str, Any],
    *,
    decided_by: str | None,
) -> CategorySuggestion:
    """Apply one admin decision and reassign activities still pending."""
    if suggestion.status not in _DECIDABLE:
        raise ValidationError(
            "Suggestion is already decided",
            field="status",
        )
    action = body.get("action")
    if action not in _ACTIONS:
        raise ValidationError(
            "action must be approve, map, or reject",
            field="action",
        )
    if action == "approve":
        target = _approve(session, suggestion, body)
    elif action == "map":
        target = _require_target(session, body)
        suggestion.status = "merged"
        suggestion.merged_into_category_id = target.id
    else:
        target = _optional_target(session, body)
        suggestion.status = "rejected"
        suggestion.merged_into_category_id = target.id if target else None
    if target is not None:
        _reassign_pending(session, suggestion.id, target.id)
    suggestion.decided_by = decided_by
    suggestion.decided_at = datetime.now(timezone.utc)
    suggestion.decision_notes = _notes(body.get("notes", body.get("decision_notes")))
    suggestion.updated_at = suggestion.decided_at
    CategorySuggestionRepository(session).refresh_activity_count(suggestion)
    session.flush()
    return suggestion


def _approve(
    session: Session,
    suggestion: CategorySuggestion,
    body: dict[str, Any],
) -> ActivityCategory:
    repo = ActivityCategoryRepository(session)
    category = create_activity_category(repo, _approve_body(suggestion, body))
    try:
        with session.begin_nested():
            session.add(category)
            session.flush()
    except IntegrityError as exc:
        raise ValidationError(
            "A category with this name already exists under that parent. "
            "Map the suggestion instead.",
            field="name",
        ) from exc
    suggestion.status = "approved"
    suggestion.created_category_id = category.id
    suggestion.merged_into_category_id = None
    return category


def _approve_body(
    suggestion: CategorySuggestion,
    body: dict[str, Any],
) -> dict[str, Any]:
    name = body.get("name") or suggestion.suggested_name or suggestion.requested_name
    translations = body.get("name_translations")
    if translations is None:
        translations = suggestion.name_translations or {}
    if "parent_id" in body:
        parent_id = body.get("parent_id")
    elif suggestion.suggested_parent_id is not None:
        parent_id = str(suggestion.suggested_parent_id)
    else:
        parent_id = None
    display_order = body.get("display_order")
    if display_order is None:
        hint = (suggestion.alternatives or {}).get("display_order_hint")
        display_order = hint if isinstance(hint, int) else 0
    return {
        "name": name,
        "name_translations": translations,
        "parent_id": parent_id,
        "display_order": display_order,
    }


def _require_target(session: Session, body: dict[str, Any]) -> ActivityCategory:
    category = _optional_target(session, body)
    if category is None:
        raise ValidationError("category_id is required", field="category_id")
    return category


def _optional_target(
    session: Session,
    body: dict[str, Any],
) -> ActivityCategory | None:
    raw = body.get("category_id")
    if raw in (None, ""):
        return None
    try:
        category_id = UUID(str(raw))
    except ValueError as exc:
        raise ValidationError("Invalid category_id", field="category_id") from exc
    if category_id == PENDING_CATEGORY_ID:
        raise ValidationError(
            "Pending categorisation cannot be a decision target",
            field="category_id",
        )
    category = session.get(ActivityCategory, category_id)
    if category is None:
        raise ValidationError("category_id not found", field="category_id")
    return category


def _reassign_pending(
    session: Session,
    suggestion_id: UUID,
    target_id: UUID,
) -> None:
    activity_ids = list(
        session.scalars(
            select(CategorySuggestionActivity.activity_id).where(
                CategorySuggestionActivity.suggestion_id == suggestion_id
            )
        ).all()
    )
    if not activity_ids:
        return
    activities = session.scalars(
        select(Activity).where(Activity.id.in_(activity_ids))
    ).all()
    for activity in activities:
        if str(activity.category_id) == str(PENDING_CATEGORY_ID):
            activity.category_id = target_id


def _notes(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError("notes must be a string", field="notes")
    text = value.strip()
    return text[:2000] if text else None
