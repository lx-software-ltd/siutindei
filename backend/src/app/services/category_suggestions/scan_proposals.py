"""Group proposed category names from one category-check batch."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import CategoryScanRun
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
)
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.services.category_suggestions.capture import (
    _link_activity,
    _replace_other_links,
)
from app.services.category_suggestions.resolve import (
    matching_category_id,
    normalize_category_key,
)
from app.services.category_suggestions.scan_apply import (
    _add_review,
    _apply_reassign,
    _category,
    _confidence,
    _name,
    _text,
)


def record_proposals(
    session: Session,
    run: CategoryScanRun,
    proposals: list[tuple[Activity, dict[str, Any]]],
    orgs: dict[str, Organization],
    counts: dict[str, int],
    now: datetime,
    *,
    threshold: float | None,
    overridden: set[str],
) -> None:
    """Collapse identical proposed names and link the activities."""
    groups: dict[str, list[tuple[Activity, dict[str, Any]]]] = {}
    for activity, result in proposals:
        name = _name((result.get("propose") or {}).get("name_en"))
        key = normalize_category_key(name or "") if name else ""
        if not key:
            counts["failed"] += 1
            continue
        groups.setdefault(key, []).append((activity, result))
    for key, items in groups.items():
        sample = items[0][1]
        raw_propose = sample.get("propose")
        propose = raw_propose if isinstance(raw_propose, dict) else {}
        name = _name(propose.get("name_en")) or key
        matched = matching_category_id(session, name)
        if matched is None:
            matched = _suggestion_target(session, key)
        if matched is not None:
            target = session.get(ActivityCategory, matched)
            if target is None:
                counts["failed"] += len(items)
                continue
            for activity, result in items:
                _apply_reassign(
                    session,
                    run,
                    activity,
                    orgs.get(str(activity.org_id)),
                    target,
                    confidence=_confidence(result.get("confidence")),
                    rationale=_text(result.get("rationale")),
                    threshold=threshold,
                    overridden=str(activity.id) in overridden,
                    counts=counts,
                    now=now,
                )
            continue
        suggestion = _ensure_suggestion(session, key, name, propose, items, now)
        for activity, result in items:
            org = orgs.get(str(activity.org_id))
            if org is not None:
                _replace_other_links(
                    session,
                    activity_id=UUID(str(activity.id)),
                    keep=suggestion.id,
                )
                _link_activity(
                    session,
                    suggestion=suggestion,
                    activity=activity,
                    org=org,
                    import_job_id=None,
                    requested_name=name,
                )
            _add_review(
                session,
                run=run,
                activity=activity,
                verdict="propose",
                status="pending",
                confidence=_confidence(result.get("confidence")),
                rationale=_text(result.get("rationale") or propose.get("rationale")),
                now=now,
                suggestion_id=suggestion.id,
            )
            counts["proposed"] += 1
        CategorySuggestionRepository(session).refresh_activity_count(suggestion)


def _ensure_suggestion(
    session: Session,
    fingerprint: str,
    name: str,
    propose: dict[str, Any],
    items: list[tuple[Activity, dict[str, Any]]],
    now: datetime,
) -> CategorySuggestion:
    repo = CategorySuggestionRepository(session)
    suggestion = repo.get_by_fingerprint(fingerprint)
    name_zh = _name(propose.get("name_zh"))
    parent = _category(session, propose.get("parent_id"))
    parent_id = None if parent is None else UUID(str(parent.id))
    confidence = max(
        (
            value
            for value in (_confidence(item.get("confidence")) for _, item in items)
            if value is not None
        ),
        default=None,
    )
    rationale = _text(propose.get("rationale"))
    if suggestion is None:
        suggestion = CategorySuggestion(
            fingerprint=fingerprint,
            requested_name=name,
            source="scan",
            status="pending",
            enrichment_status="done",
            suggested_name=name,
            name_translations={"zh": name_zh} if name_zh else {},
            suggested_parent_id=parent_id,
            confidence=confidence,
            rationale=rationale,
            enriched_at=now,
        )
        session.add(suggestion)
        session.flush()
        return suggestion
    if (
        suggestion.status == "rejected"
        and suggestion.created_category_id is None
        and suggestion.merged_into_category_id is None
    ):
        suggestion.status = "pending"
        suggestion.reopened_at = now
        suggestion.enrichment_status = "done"
        suggestion.enrichment_error = None
    if suggestion.suggested_name is None:
        suggestion.suggested_name = name
    if name_zh and not (suggestion.name_translations or {}).get("zh"):
        suggestion.name_translations = {"zh": name_zh}
    if suggestion.suggested_parent_id is None and parent_id is not None:
        suggestion.suggested_parent_id = parent_id
    if suggestion.confidence is None:
        suggestion.confidence = confidence
    if not suggestion.rationale and rationale:
        suggestion.rationale = rationale
    suggestion.enriched_at = suggestion.enriched_at or now
    suggestion.updated_at = now
    session.flush()
    return suggestion


def _suggestion_target(session: Session, fingerprint: str) -> UUID | None:
    suggestion = CategorySuggestionRepository(session).get_by_fingerprint(fingerprint)
    if suggestion is None:
        return None
    target = suggestion.created_category_id or suggestion.merged_into_category_id
    if target is None or target == PENDING_CATEGORY_ID:
        return None
    return target
