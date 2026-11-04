"""Preview the fields, counts, and values a merge would write."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityCategoryReview,
    ActivityPricing,
    ActivitySchedule,
    ApiKey,
    CategoryScanRun,
    CategorySuggestionActivity,
    Location,
    Organization,
    OrganizationFeedback,
    Ticket,
)
from app.services.org_merge_checks import merge_warnings

FILL_FIELDS = (
    "description",
    "phone_country_code",
    "phone_number",
    "email",
    "website",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
    "logo_media_url",
    "place_id",
    "source",
    "source_id",
    "source_url",
    "source_note",
    "description_source",
)

PREVIEW_FIELDS = (
    ("name", "Name"),
    ("description", "Description"),
    ("phone_country_code", "Phone country"),
    ("phone_number", "Phone"),
    ("email", "Email"),
    ("website", "Website"),
    ("source_url", "Source URL"),
    ("place_id", "Place id"),
    ("source", "Source"),
    ("source_id", "Source id"),
    ("manager_id", "Manager"),
)

TRANSLATION_FIELDS = (
    ("name_zh", "name_translations", "zh", "Chinese name"),
    ("name_yue", "name_translations", "yue", "Cantonese name"),
    ("description_zh", "description_translations", "zh", "Chinese description"),
    ("description_yue", "description_translations", "yue", "Cantonese description"),
)

REPARENT_TARGETS = (
    (Location, Location.org_id, "locations"),
    (Activity, Activity.org_id, "activities"),
    (OrganizationFeedback, OrganizationFeedback.organization_id, "feedback"),
    (ApiKey, ApiKey.org_id, "api_keys"),
    (ActivityCategoryReview, ActivityCategoryReview.org_id, "category_reviews"),
    (CategorySuggestionActivity, CategorySuggestionActivity.org_id, "suggestion_links"),
    (CategoryScanRun, CategoryScanRun.org_id, "scan_runs"),
    (Ticket, Ticket.organization_id, "tickets"),
    (Ticket, Ticket.created_organization_id, "tickets"),
)


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def suggest_survivor_id(organizations: list[Organization]) -> str:
    """Prefer an approved, operational, complete, older organization."""

    def rank(org: Organization) -> tuple:
        review = {"approved": 0, "pending_review": 1, "rejected": 2}.get(
            org.review_status,
            3,
        )
        status = 0 if org.status == "operational" else 1
        filled = sum(1 for field in FILL_FIELDS if text_value(getattr(org, field)))
        created = org.created_at.timestamp() if org.created_at is not None else 0
        return (review, status, -filled, created, str(org.id))

    return str(min(organizations, key=rank).id)


def build_merge_plan(
    session: Session,
    survivor: Organization,
    sources: list[Organization],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Fields, child counts, and values the merge would write."""
    source_ids = [source.id for source in sources]
    fields = [
        _field_plan(survivor, sources, overrides, name, label)
        for name, label in PREVIEW_FIELDS
    ]
    fields.extend(_translation_plans(survivor, sources, overrides))
    values = {field["field"]: field["result"] for field in fields}
    shown = {field["field"] for field in fields}
    for field in FILL_FIELDS:
        if field in shown:
            continue
        picked = _field_plan(survivor, sources, overrides, field, field)
        if picked["result"]:
            values[field] = picked["result"]
    media = _union_media(survivor, sources)
    return {
        "survivor_id": str(survivor.id),
        "source_ids": [str(source.id) for source in sources],
        "suggested_survivor_id": suggest_survivor_id([survivor, *sources]),
        "fields": fields,
        "moved": _moved_counts(session, source_ids),
        "warnings": merge_warnings(session, survivor, sources),
        "media_urls": media,
        "values": values,
    }


def _field_plan(survivor, sources, overrides, field: str, label: str) -> dict[str, Any]:
    survivor_value = text_value(getattr(survivor, field))
    source_values = [
        {
            "id": str(source.id),
            "name": source.name,
            "value": text_value(getattr(source, field)),
        }
        for source in sources
        if text_value(getattr(source, field))
    ]
    if field in overrides:
        result = text_value(overrides[field]) if overrides[field] is not None else ""
    elif survivor_value or field == "manager_id":
        result = survivor_value
    else:
        result = next((item["value"] for item in source_values), "")
    conflict = bool(survivor_value) and any(
        item["value"] != survivor_value for item in source_values
    )
    return {
        "field": field,
        "label": label,
        "survivor_value": survivor_value or None,
        "source_values": source_values,
        "result": result or None,
        "conflict": conflict,
    }


def _translation_plans(survivor, sources, overrides) -> list[dict[str, Any]]:
    plans = []
    for field, column, key, label in TRANSLATION_FIELDS:
        survivor_map = getattr(survivor, column) or {}
        survivor_value = text_value(
            survivor_map.get(key) if isinstance(survivor_map, dict) else ""
        )
        source_values = []
        for source in sources:
            raw = getattr(source, column) or {}
            value = text_value(raw.get(key) if isinstance(raw, dict) else "")
            if value:
                source_values.append(
                    {"id": str(source.id), "name": source.name, "value": value}
                )
        if field in overrides:
            result = text_value(overrides[field])
        elif survivor_value:
            result = survivor_value
        else:
            result = next((item["value"] for item in source_values), "")
        conflict = bool(survivor_value) and any(
            item["value"] != survivor_value for item in source_values
        )
        if not survivor_value and not source_values and field not in overrides:
            continue
        plans.append(
            {
                "field": field,
                "label": label,
                "survivor_value": survivor_value or None,
                "source_values": source_values,
                "result": result or None,
                "conflict": conflict,
            }
        )
    return plans


def _moved_counts(session: Session, source_ids: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model, column, key in REPARENT_TARGETS:
        amount = int(
            session.scalar(
                select(func.count()).select_from(model).where(column.in_(source_ids))
            )
            or 0
        )
        counts[key] = counts.get(key, 0) + amount
    activity_ids = select(Activity.id).where(Activity.org_id.in_(source_ids))
    counts["pricing"] = int(
        session.scalar(
            select(func.count())
            .select_from(ActivityPricing)
            .where(ActivityPricing.activity_id.in_(activity_ids))
        )
        or 0
    )
    counts["schedules"] = int(
        session.scalar(
            select(func.count())
            .select_from(ActivitySchedule)
            .where(ActivitySchedule.activity_id.in_(activity_ids))
        )
        or 0
    )
    return counts


def _union_media(survivor: Organization, sources: list[Organization]) -> list[str]:
    urls = list(survivor.media_urls or [])
    for source in sources:
        for url in source.media_urls or []:
            if url not in urls:
                urls.append(url)
    return urls
