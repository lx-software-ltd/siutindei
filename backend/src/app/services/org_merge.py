"""Move one organization's records onto another and delete the source."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.audit import AuditService
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
    OrganizationMerge,
    Ticket,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.org_merge_checks import assert_identity_unique, merge_warnings
from app.services.org_merge_children import fold_merged_records
from app.services.org_merge_media import copy_merged_media

_FILL_FIELDS = (
    "description",
    "phone_country_code",
    "phone_number",
    "email",
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

_PREVIEW_FIELDS = (
    ("name", "Name"),
    ("description", "Description"),
    ("phone_country_code", "Phone country"),
    ("phone_number", "Phone"),
    ("email", "Email"),
    ("source_url", "Website"),
    ("place_id", "Place id"),
    ("source", "Source"),
    ("source_id", "Source id"),
    ("manager_id", "Manager"),
)

_TRANSLATION_FIELDS = (
    ("name_zh", "name_translations", "zh", "Chinese name"),
    ("name_yue", "name_translations", "yue", "Cantonese name"),
    ("description_zh", "description_translations", "zh", "Chinese description"),
    ("description_yue", "description_translations", "yue", "Cantonese description"),
)

_OVERRIDE_FIELDS = (
    set(_FILL_FIELDS)
    | {"name", "manager_id"}
    | {item[0] for item in _TRANSLATION_FIELDS}
)

_REPARENT = (
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


def merge_organizations(
    session: Session,
    survivor_id: UUID,
    source_ids: list[UUID],
    overrides: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
    merged_by: str | None = None,
) -> dict[str, Any]:
    """Fill blanks on the survivor, reparent children, and delete sources."""
    chosen = dict(overrides or {})
    unknown = sorted(set(chosen) - _OVERRIDE_FIELDS)
    if unknown:
        raise ValidationError(f"Unknown field {unknown[0]}", field=unknown[0])
    if survivor_id in source_ids:
        raise ValidationError("survivor_id is also a source", field="survivor_id")
    if not source_ids:
        raise ValidationError("source_ids is required", field="source_ids")

    orgs = _lock_orgs(session, [survivor_id, *source_ids])
    by_id = {str(org.id): org for org in orgs}
    survivor = by_id.get(str(survivor_id))
    if survivor is None:
        raise NotFoundError("organizations", str(survivor_id))
    sources: list[Organization] = []
    for source_id in source_ids:
        source = by_id.get(str(source_id))
        if source is None:
            raise NotFoundError("organizations", str(source_id))
        sources.append(source)

    plan = _plan(session, survivor, sources, chosen)
    plan["dry_run"] = dry_run
    if dry_run:
        return plan
    _apply(session, survivor, sources, plan, merged_by)
    plan["merged"] = True
    return plan


def suggest_survivor_id(organizations: list[Organization]) -> str:
    """Prefer an approved, operational, complete, older organization."""

    def rank(org: Organization) -> tuple:
        review = {"approved": 0, "pending_review": 1, "rejected": 2}.get(
            org.review_status,
            3,
        )
        status = 0 if org.status == "operational" else 1
        filled = sum(1 for field in _FILL_FIELDS if _text(getattr(org, field)))
        created = org.created_at.timestamp() if org.created_at is not None else 0
        return (review, status, -filled, created, str(org.id))

    return str(min(organizations, key=rank).id)


def _lock_orgs(session: Session, ids: list[UUID]) -> list[Organization]:
    stmt = select(Organization).where(Organization.id.in_(ids))
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return list(session.scalars(stmt).all())


def _plan(
    session: Session,
    survivor: Organization,
    sources: list[Organization],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    source_ids = [source.id for source in sources]
    fields = [
        _field_plan(survivor, sources, overrides, name, label)
        for name, label in _PREVIEW_FIELDS
    ]
    fields.extend(_translation_plans(survivor, sources, overrides))
    values = {field["field"]: field["result"] for field in fields}
    shown = {field["field"] for field in fields}
    for field in _FILL_FIELDS:
        if field in shown:
            continue
        picked = _field_plan(survivor, sources, overrides, field, field)
        if picked["result"]:
            values[field] = picked["result"]
    warnings = merge_warnings(session, survivor, sources)
    media = _union_media(survivor, sources)
    return {
        "survivor_id": str(survivor.id),
        "source_ids": [str(source.id) for source in sources],
        "suggested_survivor_id": suggest_survivor_id([survivor, *sources]),
        "fields": fields,
        "moved": _moved_counts(session, source_ids),
        "warnings": warnings,
        "media_urls": media,
        "values": values,
    }


def _field_plan(survivor, sources, overrides, field: str, label: str) -> dict[str, Any]:
    survivor_value = _text(getattr(survivor, field))
    source_values = [
        {
            "id": str(source.id),
            "name": source.name,
            "value": _text(getattr(source, field)),
        }
        for source in sources
        if _text(getattr(source, field))
    ]
    if field in overrides:
        result = _text(overrides[field]) if overrides[field] is not None else ""
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
    for field, column, key, label in _TRANSLATION_FIELDS:
        survivor_map = getattr(survivor, column) or {}
        survivor_value = _text(
            survivor_map.get(key) if isinstance(survivor_map, dict) else ""
        )
        source_values = []
        for source in sources:
            raw = getattr(source, column) or {}
            value = _text(raw.get(key) if isinstance(raw, dict) else "")
            if value:
                source_values.append(
                    {"id": str(source.id), "name": source.name, "value": value}
                )
        if field in overrides:
            result = _text(overrides[field])
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
    for model, column, key in _REPARENT:
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


def _apply(session, survivor, sources, plan, merged_by: str | None) -> None:
    values = plan["values"]
    filled = [
        field
        for field, value in values.items()
        if _text(value) and _changed(survivor, field, value)
    ]
    originals = [
        {
            "snapshot": _snapshot(source),
            "source": source.source,
            "source_id": source.source_id,
            "place_id": source.place_id,
        }
        for source in sources
    ]
    for source in sources:
        source.name = f"merged-{source.id}"
        source.place_id = None
        source.source_id = None
    session.flush()
    _write_scalars(survivor, values)
    _write_translations(survivor, values)
    assert_identity_unique(session, survivor)
    pending: list[str] = []
    media = []
    for source in sources:
        for url in source.media_urls or []:
            rewritten, delete_key = copy_merged_media(
                url,
                str(source.id),
                str(survivor.id),
            )
            if delete_key:
                pending.append(delete_key)
            if rewritten not in media and rewritten not in (survivor.media_urls or []):
                media.append(rewritten)
    survivor.media_urls = [*(survivor.media_urls or []), *media]
    if not _text(survivor.logo_media_url):
        for source in sources:
            if _text(source.logo_media_url):
                rewritten, delete_key = copy_merged_media(
                    source.logo_media_url,
                    str(source.id),
                    str(survivor.id),
                )
                survivor.logo_media_url = rewritten or None
                if delete_key:
                    pending.append(delete_key)
                break
    plan["pending_deletes"] = pending
    source_ids = [source.id for source in sources]
    session.execute(
        update(OrganizationMerge)
        .where(OrganizationMerge.survivor_org_id.in_(source_ids))
        .values(survivor_org_id=survivor.id)
    )
    for source, original in zip(sources, originals, strict=True):
        session.add(
            OrganizationMerge(
                merged_org_id=source.id,
                survivor_org_id=survivor.id,
                source=original["source"],
                source_id=original["source_id"],
                place_id=original["place_id"],
                snapshot=original["snapshot"],
                moved_counts=plan["moved"],
                merged_by=merged_by,
            )
        )
    session.flush()
    fold_merged_records(session, survivor, sources)
    for model, column, _key in _REPARENT:
        if model in (Location, Activity):
            continue
        rows = session.scalars(select(model).where(column.in_(source_ids))).all()
        for row in rows:
            setattr(row, column.key, survivor.id)
    session.flush()
    for source in sources:
        session.expire(source, ["locations", "activities"])
    AuditService(session, user_id=merged_by).log_custom(
        "organizations",
        survivor.id,
        "MERGE",
        new_values={
            "source_ids": [str(source.id) for source in sources],
            "moved": plan["moved"],
            "filled_fields": filled,
        },
    )
    for source in sources:
        session.delete(source)
    session.flush()
    from app.services.org_duplicates import invalidate_duplicate_cache

    invalidate_duplicate_cache()


def _changed(survivor, field: str, value: str) -> bool:
    if field in {item[0] for item in _TRANSLATION_FIELDS}:
        return True
    return _text(getattr(survivor, field, "")) != value


def _write_scalars(survivor: Organization, values: dict[str, Any]) -> None:
    for field in ("name", "manager_id", *_FILL_FIELDS):
        if field not in values:
            continue
        result = values[field]
        if field == "name" and not result:
            raise ValidationError("name is required", field="name")
        if field == "manager_id" and not result:
            raise ValidationError("manager_id is required", field="manager_id")
        setattr(survivor, field, result or None)


def _write_translations(survivor: Organization, values: dict[str, Any]) -> None:
    for field, column, key, _label in _TRANSLATION_FIELDS:
        if field not in values:
            continue
        current = dict(getattr(survivor, column) or {})
        result = values[field]
        if result:
            current[key] = result
        else:
            current.pop(key, None)
        setattr(survivor, column, current)


def _snapshot(org: Organization) -> dict[str, Any]:
    return {
        "id": str(org.id),
        "name": org.name,
        "description": org.description,
        "manager_id": org.manager_id,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "email": org.email,
        "place_id": org.place_id,
        "source": org.source,
        "source_id": org.source_id,
        "source_url": org.source_url,
        "review_status": org.review_status,
        "status": org.status,
        "media_urls": list(org.media_urls or []),
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
