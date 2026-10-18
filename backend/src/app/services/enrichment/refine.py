"""Fill neighbourhoods, categories, names, and social logos before a proposal is saved."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.activity_category import ActivityCategory
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.models.organization import Organization
from app.services.category_suggestions.resolve import matching_category_id
from app.services.enrichment.logos import social_logo_proposals
from app.services.enrichment.places import GeocodeBudget, place_fields
from app.services.name_sanitizer import organization_name_key, sanitize_name

Lookup = Callable[[str], dict[str, Any] | None]
Sleep = Callable[[float], None]
Fetch = Callable[[str, dict[str, str]], dict[str, Any] | None]


def catalog_names(session: Session) -> list[str]:
    """Catalog category names, with Chinese in parentheses. Pending is left out."""
    rows = session.scalars(
        select(ActivityCategory)
        .where(ActivityCategory.id != PENDING_CATEGORY_ID)
        .order_by(ActivityCategory.name)
    ).all()
    lines: list[str] = []
    for row in rows:
        translations = row.name_translations or {}
        zh = ""
        if isinstance(translations, dict):
            raw = translations.get("zh") or translations.get("zh-HK") or ""
            zh = raw.strip() if isinstance(raw, str) else ""
        lines.append(f"{row.name} ({zh})" if zh else row.name)
    return lines


def annotate(
    session: Session,
    org: Organization,
    items: list[dict[str, Any]],
    *,
    geocode: Lookup | None = None,
    sleep: Sleep | None = None,
    social_fetch: Fetch | None = None,
) -> list[dict[str, Any]]:
    """Resolve places and categories, drop names that must not change, add logos."""
    budget = GeocodeBudget(geocode, sleep)
    kept: list[dict[str, Any]] = []
    for item in items:
        proposed = dict(item.get("proposed") or {})
        kind = str(item.get("kind") or "")
        field = str(item.get("field") or "")
        if kind == "create_location":
            proposed.update(place_fields(session, proposed, budget))
            item = {**item, "proposed": proposed}
        elif kind == "create_activity":
            category_id = _category_id(session, proposed)
            if category_id:
                proposed["category_id"] = category_id
                item = {**item, "proposed": proposed}
        elif kind == "update_organization" and field in {"name", "name_translations"}:
            if not _keep_name(org, field, proposed):
                continue
            item = {**item, "proposed": proposed}
        kept.append(item)
    kept.extend(social_logo_proposals(org, items, fetch=social_fetch))
    return kept


def _category_id(session: Session, proposed: dict[str, Any]) -> str | None:
    for key in ("category_name", "category_words"):
        found = matching_category_id(session, str(proposed.get(key) or ""))
        if found is not None:
            return str(found)
    return None


def _keep_name(org: Organization, field: str, proposed: dict[str, Any]) -> bool:
    if org.review_status != "pending_review":
        return False
    if field == "name":
        cleaned = sanitize_name(
            str(proposed.get("name") or ""), org.name_translations or {}
        ).name
        if organization_name_key(cleaned) == organization_name_key(org.name or ""):
            return False
        proposed["name"] = cleaned
        return True
    translations = proposed.get("name_translations")
    zh = ""
    if isinstance(translations, dict):
        raw = translations.get("zh")
        zh = raw.strip() if isinstance(raw, str) else ""
    current = ""
    stored = org.name_translations or {}
    if isinstance(stored, dict):
        raw_current = stored.get("zh")
        current = raw_current.strip() if isinstance(raw_current, str) else ""
    if not zh or organization_name_key(zh) == organization_name_key(current):
        return False
    proposed["name_translations"] = {"zh": zh}
    return True
