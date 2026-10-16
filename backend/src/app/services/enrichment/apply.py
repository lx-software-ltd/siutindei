"""Apply or dismiss enrichment proposals through the existing write paths."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.types.range import Range
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.admin_imports_lookups import lookup_district_area_id
from app.api.admin_imports_utils import parse_time_minutes, to_utc_weekly
from app.api.admin_validators import (
    MAX_MEDIA_URLS_COUNT,
    _validate_email,
    _validate_phone_fields,
    _validate_social_value,
    _validate_string_length,
    _validate_url,
)
from app.db.audit import AuditService
from app.db.models import Activity, ActivityLocation, ActivityPricing, ActivitySchedule
from app.db.models import ActivityScheduleEntry, Location, Organization
from app.db.models.activity_category import ActivityCategory
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.models.enums import PricingType, ScheduleType
from app.db.models.org_enrichment import OrgEnrichmentProposal
from app.exceptions import AppError, ValidationError
from app.services.area_assignment import get_leaf
from app.services.category_suggestions.resolve import normalize_category_key
from app.services.enrichment.constants import MAX_APPLY_IDS

HK = ZoneInfo("Asia/Hong_Kong")
CopyImage = Callable[[str, str], str]


def apply_proposals(
    session: Session,
    org_id: UUID,
    ids: list[str],
    overrides: dict[str, dict[str, Any]],
    *,
    user_id: str | None,
    request_id: str | None,
    copy_image: CopyImage | None = None,
) -> list[dict[str, Any]]:
    if not ids or len(ids) > MAX_APPLY_IDS:
        raise ValidationError("ids must contain 1 to 200 proposals", field="ids")
    org = session.get(Organization, org_id)
    if org is None:
        raise AppError("Organization not found", status_code=404)
    _mark_reason(session)
    results: list[dict[str, Any]] = []
    fields: list[str] = []
    for raw_id in ids:
        proposal = _load(session, org_id, raw_id)
        if proposal is None:
            results.append({"id": raw_id, "status": "error", "error": "not found"})
            continue
        if proposal.status != "pending":
            results.append({"id": raw_id, "status": "error", "error": "not pending"})
            continue
        try:
            _apply_one(
                session,
                org,
                proposal,
                overrides.get(raw_id) or {},
                copy_image=copy_image,
            )
        except (ValidationError, AppError) as exc:
            results.append({"id": raw_id, "status": "error", "error": exc.message})
            continue
        proposal.status = "applied"
        proposal.decided_by = user_id
        proposal.decided_at = datetime.now(timezone.utc)
        fields.append(proposal.field or proposal.kind)
        results.append({"id": raw_id, "status": "applied"})
    if fields:
        AuditService(session, user_id=user_id, request_id=request_id).log_custom(
            table_name="organizations",
            record_id=str(org_id),
            action="ENRICH_APPLY",
            new_values={"fields": fields, "proposal_ids": ids},
        )
        _link_run(session, proposal_run_id(session, ids[0], org_id))
    session.flush()
    return results


def dismiss_proposals(
    session: Session,
    org_id: UUID,
    ids: list[str],
    *,
    user_id: str | None,
) -> list[dict[str, Any]]:
    if not ids or len(ids) > MAX_APPLY_IDS:
        raise ValidationError("ids must contain 1 to 200 proposals", field="ids")
    results = []
    for raw_id in ids:
        proposal = _load(session, org_id, raw_id)
        if proposal is None or proposal.status != "pending":
            results.append({"id": raw_id, "status": "error", "error": "not pending"})
            continue
        proposal.status = "dismissed"
        proposal.decided_by = user_id
        proposal.decided_at = datetime.now(timezone.utc)
        results.append({"id": raw_id, "status": "dismissed"})
    session.flush()
    return results


def proposal_run_id(session: Session, raw_id: str, org_id: UUID) -> str | None:
    row = _load(session, org_id, raw_id)
    return str(row.run_id) if row is not None else None


def _apply_one(
    session: Session,
    org: Organization,
    proposal: OrgEnrichmentProposal,
    override: dict[str, Any],
    *,
    copy_image: CopyImage | None,
) -> None:
    proposed = (
        proposal.proposed_value if isinstance(proposal.proposed_value, dict) else {}
    )
    if proposal.kind == "update_organization":
        _apply_org(org, proposal, proposed)
        return
    if proposal.kind == "add_media":
        _apply_media(session, org, proposed, copy_image=copy_image)
        return
    if proposal.kind == "create_location":
        _apply_location(session, org, proposal, proposed, override)
        return
    if proposal.kind == "create_activity":
        _apply_activity(session, org, proposal, proposed, override)
        return
    if proposal.kind == "create_pricing":
        _apply_pricing(session, org, proposed, override)
        return
    if proposal.kind == "create_schedule":
        _apply_schedule(session, org, proposed, override)
        return
    raise ValidationError("unsupported proposal", field="kind")


def _apply_org(
    org: Organization,
    proposal: OrgEnrichmentProposal,
    proposed: dict[str, Any],
) -> None:
    if "description_translations" in proposed:
        if not _empty_translation(org, proposal.current_value):
            raise ValidationError(
                "description changed since the crawl", field="description"
            )
        merged = dict(org.description_translations or {})
        merged.update(proposed["description_translations"])
        org.description_translations = merged
        return
    if "phone_country_code" in proposed or "phone_number" in proposed:
        if not _still(
            org, proposal.current_value, ("phone_country_code", "phone_number")
        ):
            raise ValidationError("phone changed since the crawl", field="phone_number")
        country, number = _validate_phone_fields(
            proposed.get("phone_country_code"),
            proposed.get("phone_number"),
        )
        org.phone_country_code = country
        org.phone_number = number
        return
    field = proposal.field or ""
    if field not in proposed:
        raise ValidationError("proposal has no value", field=field or "field")
    if not _still(org, proposal.current_value, (field,)):
        raise ValidationError(f"{field} changed since the crawl", field=field)
    value = proposed[field]
    if field == "description":
        org.description = _validate_string_length(value, "description", 5000)
    elif field == "email":
        org.email = _validate_email(value)
    elif field == "website":
        org.website = _validate_url(str(value), "website")
    elif field in {
        "whatsapp",
        "facebook",
        "instagram",
        "tiktok",
        "twitter",
        "xiaohongshu",
        "wechat",
    }:
        setattr(org, field, _validate_social_value(value, field))
    else:
        raise ValidationError("field cannot be enriched", field=field)


def _apply_media(
    session: Session,
    org: Organization,
    proposed: dict[str, Any],
    *,
    copy_image: CopyImage | None,
) -> None:
    source = str(proposed.get("source_url") or "")
    if not source:
        raise ValidationError("image URL is missing", field="source_url")
    from app.services.enrichment.store import load_settings

    settings = load_settings(session)
    if settings.copy_media:
        if copy_image is None:
            from app.services.aws_proxy import crawl_invoke

            def copy_image(image_url: str, org_id: str) -> str:
                copied = crawl_invoke(
                    {"op": "image", "url": image_url, "org_id": org_id}
                )
                return str(copied.get("url") or "")

        stored = copy_image(source, str(org.id))
    else:
        stored = _validate_url(source, "media_urls")
    urls = list(org.media_urls or [])
    if stored not in urls:
        if len(urls) >= MAX_MEDIA_URLS_COUNT:
            raise ValidationError("media_urls is full", field="media_urls")
        urls.append(stored)
        org.media_urls = sorted(urls)
    if proposed.get("logo"):
        org.logo_media_url = stored


def _apply_location(
    session: Session,
    org: Organization,
    proposal: OrgEnrichmentProposal,
    proposed: dict[str, Any],
    override: dict[str, Any],
) -> None:
    address = str(proposed.get("address") or "").strip()
    if not address:
        raise ValidationError("address is required", field="address")
    existing = _location_by_address(session, org.id, address)
    if existing is not None:
        proposal.entity_id = existing.id
        return
    area_id = str(override.get("area_id") or "")
    if not area_id:
        area_id = lookup_district_area_id(session, proposed.get("area_name"))
    if get_leaf(session, area_id) is None:
        raise ValidationError("area_id must be a neighbourhood", field="area_id")
    session.add(Location(org_id=org.id, area_id=area_id, address=address[:500]))
    session.flush()


def _apply_activity(
    session: Session,
    org: Organization,
    proposal: OrgEnrichmentProposal,
    proposed: dict[str, Any],
    override: dict[str, Any],
) -> None:
    name = str(proposed.get("name") or "").strip()
    if not name:
        raise ValidationError("name is required", field="name")
    category_id = override.get("category_id") or _resolve_category(
        session, str(proposed.get("category_name") or "")
    )
    if category_id is None:
        if org.review_status == "approved":
            raise ValidationError(
                "Pick a category before adding this activity to an approved organization",
                field="category_id",
            )
        category_id = PENDING_CATEGORY_ID
    age_min = override.get("age_min", proposed.get("age_min"))
    age_max = override.get("age_max", proposed.get("age_max"))
    if age_min is None or age_max is None:
        raise ValidationError(
            "age_min and age_max were not on the website",
            field="age_min",
        )
    activity = Activity(
        org_id=org.id,
        category_id=category_id,
        name=name[:200],
        description=_validate_string_length(
            proposed.get("description"), "description", 5000
        ),
        name_translations={"zh": proposed["name_zh"]}
        if proposed.get("name_zh")
        else {},
        description_translations={},
        source_category_name=str(proposed.get("category_name") or "")[:200] or None,
        age_range=Range(int(age_min), int(age_max), bounds="[]"),
    )
    session.add(activity)
    session.flush()
    proposal.entity_id = activity.id
    venue = _location_by_address(
        session, org.id, str(proposed.get("location_address") or "")
    )
    if venue is not None:
        session.add(ActivityLocation(activity_id=activity.id, location_id=venue.id))


def _apply_pricing(
    session: Session,
    org: Organization,
    proposed: dict[str, Any],
    override: dict[str, Any],
) -> None:
    activity = _activity_by_name(
        session, org.id, str(proposed.get("activity_name") or "")
    )
    location = _resolve_venue(session, org.id, proposed, override)
    if activity is None or location is None:
        raise ValidationError("activity and venue are required", field="location_id")
    pricing_type = str(proposed.get("pricing_type") or "per_class")
    amount = Decimal(str(proposed.get("amount") or "0"))
    sessions = proposed.get("sessions_count")
    if pricing_type == "per_sessions" and not sessions:
        raise ValidationError("sessions_count is required", field="sessions_count")
    session.add(
        ActivityPricing(
            activity_id=activity.id,
            location_id=location.id,
            pricing_type=PricingType(pricing_type),
            amount=amount,
            currency=str(proposed.get("currency") or "HKD"),
            sessions_count=int(sessions) if sessions else None,
            free_trial_class_offered=bool(proposed.get("free_trial_class_offered")),
        )
    )


def _apply_schedule(
    session: Session,
    org: Organization,
    proposed: dict[str, Any],
    override: dict[str, Any],
) -> None:
    activity = _activity_by_name(
        session, org.id, str(proposed.get("activity_name") or "")
    )
    location = _resolve_venue(session, org.id, proposed, override)
    if activity is None or location is None:
        raise ValidationError("activity and venue are required", field="location_id")
    schedule = ActivitySchedule(
        activity_id=activity.id,
        location_id=location.id,
        schedule_type=ScheduleType.WEEKLY,
        languages=list(proposed.get("languages") or ["zh-HK"]),
    )
    session.add(schedule)
    session.flush()
    for entry in proposed.get("entries") or []:
        start = parse_time_minutes(entry.get("start_time"), "start_time")
        end = parse_time_minutes(entry.get("end_time"), "end_time")
        day, start_utc, end_utc = to_utc_weekly(
            int(entry["day_of_week"]), start, end, HK
        )
        session.add(
            ActivityScheduleEntry(
                schedule_id=schedule.id,
                day_of_week_utc=day,
                start_minutes_utc=start_utc,
                end_minutes_utc=end_utc,
            )
        )


def _resolve_category(session: Session, name: str) -> UUID | None:
    cleaned = name.strip()
    if not cleaned:
        return None
    exact = list(
        session.scalars(
            select(ActivityCategory).where(ActivityCategory.name == cleaned)
        ).all()
    )
    if len(exact) == 1 and exact[0].id != PENDING_CATEGORY_ID:
        return exact[0].id
    key = normalize_category_key(cleaned)
    matches = [
        row
        for row in session.scalars(select(ActivityCategory)).all()
        if normalize_category_key(row.name) == key and row.id != PENDING_CATEGORY_ID
    ]
    if len(matches) == 1:
        return matches[0].id
    return None


def _resolve_venue(
    session: Session,
    org_id: Any,
    proposed: dict[str, Any],
    override: dict[str, Any],
) -> Location | None:
    if override.get("location_id"):
        row = session.get(Location, override["location_id"])
        if row is None or str(row.org_id) != str(org_id):
            raise ValidationError("location_id not found", field="location_id")
        return row
    matched = _location_by_address(
        session, org_id, str(proposed.get("location_address") or "")
    )
    if matched is not None:
        return matched
    rows = list(
        session.scalars(select(Location).where(Location.org_id == org_id)).all()
    )
    if len(rows) == 1:
        return rows[0]
    return None


def _location_by_address(
    session: Session, org_id: Any, address: str
) -> Location | None:
    target = " ".join(address.split()).casefold()
    if not target:
        return None
    for row in session.scalars(select(Location).where(Location.org_id == org_id)).all():
        if " ".join((row.address or "").split()).casefold() == target:
            return row
    return None


def _activity_by_name(session: Session, org_id: Any, name: str) -> Activity | None:
    target = " ".join(name.split()).casefold()
    for row in session.scalars(select(Activity).where(Activity.org_id == org_id)).all():
        if " ".join(row.name.split()).casefold() == target:
            return row
    return None


def _still(org: Organization, current: object, fields: tuple[str, ...]) -> bool:
    for field in fields:
        stored = getattr(org, field, None) or None
        expected = current.get(field) if isinstance(current, dict) else None
        expected = expected or None
        if stored != expected:
            return False
    return True


def _empty_translation(org: Organization, current: object) -> bool:
    stored = (org.description_translations or {}).get("zh") or None
    expected = None
    if isinstance(current, dict):
        translations = current.get("description_translations") or {}
        expected = translations.get("zh") or None
    return stored == expected


def _load(session: Session, org_id: UUID, raw_id: str) -> OrgEnrichmentProposal | None:
    try:
        proposal_id = UUID(str(raw_id))
    except ValueError:
        return None
    row = session.get(OrgEnrichmentProposal, proposal_id)
    if row is None or str(row.org_id) != str(org_id):
        return None
    return row


def _mark_reason(session: Session) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT set_config('app.catalog_version_reason', 'enrichment', true)")
    )


def _link_run(session: Session, run_id: str | None) -> None:
    bind = session.get_bind()
    if not run_id or bind is None or bind.dialect.name != "postgresql":
        return
    session.execute(
        text(
            "UPDATE catalog_versions SET related_id = :run_id "
            "WHERE txid = txid_current() AND reason = 'enrichment' "
            "AND related_id IS NULL"
        ),
        {"run_id": run_id},
    )
