"""Prompt construction for category enrichment."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.age_bounds import inclusive_age_bounds
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_suggestion import (
    LEGACY_CATEGORY_IDS,
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


_RECHECK_NOTE = (
    " The activity has no trusted category. Choose the best leaf in the "
    "taxonomy. Reply reassign with that leaf's category_id. Reply propose "
    "only when no leaf fits. Do not reply confirm."
)


def build_scan_prompt(
    session: Session,
    activities: list[Activity],
    *,
    ignore_current_category: bool = False,
) -> tuple[str, str]:
    """Return system and user prompts for one category-check batch."""
    rows = list(session.scalars(select(ActivityCategory)).all())
    by_id = {row.id: row for row in rows}
    system = (
        "You check categories for children's activities in Hong Kong. "
        "Each activity already has a category. Reply confirm when that "
        "category fits. Reply reassign with an existing category_id when "
        "a different existing category is clearly better. Reply propose "
        "only when no existing category fits. Use Traditional Chinese for "
        "zh names. Never confirm Pending categorisation. Do not invent "
        "near-duplicates of existing names. Reply with one JSON object "
        "and no markdown. Schema: "
        '{"results":[{"activity_id":string,'
        '"verdict":"confirm"|"reassign"|"propose",'
        '"category_id":string|null,"confidence":number,"rationale":string,'
        '"propose":{"name_en":string,"name_zh":string,"parent_id":string|null,'
        '"rationale":string}}]}'
    )
    if ignore_current_category:
        system += _RECHECK_NOTE
    user = {
        "activities": [
            _scan_item(
                session,
                activity,
                by_id,
                ignore_current=ignore_current_category,
            )
            for activity in activities
        ],
        "taxonomy": _taxonomy(session, leaves_only=ignore_current_category),
        "do_not_propose": _rejected_names(session),
    }
    return system, json.dumps(user, ensure_ascii=False)


def _scan_item(
    session: Session,
    activity: Activity,
    by_id: dict,
    *,
    ignore_current: bool = False,
) -> dict[str, Any]:
    org = session.get(Organization, activity.org_id)
    category = by_id.get(activity.category_id)
    lower, upper = inclusive_age_bounds(activity.age_range)
    template = org is not None and org.description_source == "template"
    description = "" if ignore_current and template else (activity.description or "")
    description = description[:_MAX_DESCRIPTION]
    item: dict[str, Any] = {
        "activity_id": str(activity.id),
        "activity_name": redact_contacts(activity.name),
        "description": redact_contacts(description),
        "age_min": lower,
        "age_max": upper,
        "organization": redact_contacts(org.name) if org is not None else "",
        "organization_zh": _zh_name(org),
        "source_label": redact_contacts(activity.source_category_name or ""),
    }
    if ignore_current:
        item["description_is_template"] = template
        item["organization_source"] = "" if org is None else (org.source or "")
        item["source_url_host"] = _source_host(org)
        return item
    path = ""
    category_id = None
    if category is not None:
        path = (
            category.name
            if category.id == PENDING_CATEGORY_ID
            else _path(category, by_id)
        )
        category_id = str(category.id)
    item["current_category_id"] = category_id
    item["current_category"] = path
    return item


def _source_host(org: Organization | None) -> str:
    if org is None or not org.source_url:
        return ""
    host = (urlparse(str(org.source_url)).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def build_discovery_prompt(
    session: Session,
    suggestions: list[CategorySuggestion],
) -> tuple[str, str]:
    """Return one prompt for a batch of imported labels."""
    system = (
        "You categorise children's activities in Hong Kong for a directory. "
        "Each item is an imported category label that is not in the taxonomy. "
        "Prefer mapping it onto an existing category. Otherwise propose a "
        "sub-category under an existing root unless the place clearly needs "
        "a new root. Use Traditional Chinese for zh. Do not invent "
        "near-duplicates of existing names. Reply with one JSON object and "
        "no markdown. Schema: "
        '{"results":[{"suggestion_id":string,'
        '"maps_to_existing":{"category_id":string|null,"confidence":number},'
        '"propose":{"name_en":string,"name_zh":string,"parent_id":string|null,'
        '"rationale":string,"display_order_hint":number},'
        '"confidence":number,"rationale":string,'
        '"alternatives":[{"name_en":string,"parent_id":string|null,'
        '"confidence":number}]}]}'
    )
    labels = [
        {
            "suggestion_id": str(suggestion.id),
            "requested_name": redact_contacts(suggestion.requested_name),
            "evidence": _evidence(session, suggestion, limit=5),
        }
        for suggestion in suggestions
    ]
    user = {
        "labels": labels,
        "taxonomy": _taxonomy(session),
        "do_not_propose": _rejected_names(session),
    }
    return system, json.dumps(user, ensure_ascii=False)


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


def _taxonomy(session: Session, *, leaves_only: bool = False) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(ActivityCategory).order_by(
                ActivityCategory.display_order,
                ActivityCategory.name,
            )
        ).all()
    )
    by_id = {row.id: row for row in rows}
    parent_ids = {row.parent_id for row in rows if row.parent_id is not None}
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.id == PENDING_CATEGORY_ID:
            continue
        if leaves_only and (row.id in LEGACY_CATEGORY_IDS or row.id in parent_ids):
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
