"""Prompt construction for category enrichment."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.age_bounds import inclusive_age_bounds
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
_MAX_DESCRIPTION = 300


def redact_contacts(value: str) -> str:
    """Remove emails and phone-like numbers before a prompt leaves the VPC."""
    text = _EMAIL_RE.sub("[redacted-email]", value)
    return _PHONE_RE.sub("[redacted-phone]", text)


def build_enrichment_prompt(
    session: Session,
    suggestion: CategorySuggestion,
    *,
    max_evidence: int,
) -> tuple[str, str]:
    """Return system and user prompts for one suggestion."""
    evidence = _evidence(session, suggestion, limit=max_evidence)
    taxonomy = _taxonomy(session)
    rejected = _rejected_names(session)
    system = (
        "You categorise children's activities in Hong Kong for a directory. "
        "Prefer mapping the requested name onto an existing category. "
        "Otherwise propose a sub-category under an existing root unless the "
        "place clearly needs a new root. Use Traditional Chinese for zh. "
        "Do not invent near-duplicates of existing names. "
        "Reply with one JSON object and no markdown. Schema: "
        '{"maps_to_existing":{"category_id":string|null,"confidence":number},'
        '"propose":{"name_en":string,"name_zh":string,"parent_id":string|null,'
        '"rationale":string,"display_order_hint":number},'
        '"confidence":number,"rationale":string,'
        '"alternatives":[{"name_en":string,"parent_id":string|null,'
        '"confidence":number}]}'
    )
    user = {
        "requested_name": redact_contacts(suggestion.requested_name),
        "evidence": evidence,
        "taxonomy": taxonomy,
        "do_not_propose": rejected,
    }
    import json

    return system, json.dumps(user, ensure_ascii=False)


def _evidence(
    session: Session,
    suggestion: CategorySuggestion,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    links = list(
        session.scalars(
            select(CategorySuggestionActivity)
            .where(CategorySuggestionActivity.suggestion_id == suggestion.id)
            .order_by(CategorySuggestionActivity.created_at.desc())
            .limit(limit)
        ).all()
    )
    items: list[dict[str, Any]] = []
    for link in links:
        activity = session.get(Activity, link.activity_id)
        org = session.get(Organization, link.org_id)
        if activity is None:
            continue
        lower, upper = inclusive_age_bounds(activity.age_range)
        description = (activity.description or "")[:_MAX_DESCRIPTION]
        items.append(
            {
                "activity_name": redact_contacts(activity.name),
                "description": redact_contacts(description),
                "age_min": lower,
                "age_max": upper,
                "organization": redact_contacts(org.name) if org is not None else "",
                "organization_zh": _zh_name(org),
                "source": (org.source if org is not None else None) or "",
            }
        )
    return items


def _zh_name(org: Organization | None) -> str:
    if org is None or not isinstance(org.name_translations, dict):
        return ""
    value = org.name_translations.get("zh") or ""
    return redact_contacts(str(value))


def _taxonomy(session: Session) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(ActivityCategory).order_by(
                ActivityCategory.display_order,
                ActivityCategory.name,
            )
        ).all()
    )
    by_id = {row.id: row for row in rows}
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.id == PENDING_CATEGORY_ID:
            continue
        items.append(
            {
                "id": str(row.id),
                "path": _path(row, by_id),
                "name_zh": _translation(row, "zh"),
            }
        )
    return items


def _path(row: ActivityCategory, by_id: dict) -> str:
    parts = [row.name]
    parent_id = row.parent_id
    seen: set = set()
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None or parent.id == PENDING_CATEGORY_ID:
            break
        parts.append(parent.name)
        parent_id = parent.parent_id
    parts.reverse()
    return " / ".join(parts)


def _translation(row: ActivityCategory, language: str) -> str:
    raw = row.name_translations or {}
    if not isinstance(raw, dict):
        return ""
    value = raw.get(language)
    return str(value) if isinstance(value, str) else ""


def _rejected_names(session: Session) -> list[str]:
    rows = session.scalars(
        select(CategorySuggestion.requested_name)
        .where(CategorySuggestion.status == "rejected")
        .limit(50)
    ).all()
    return [redact_contacts(name) for name in rows]
