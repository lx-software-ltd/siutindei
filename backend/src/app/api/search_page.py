"""Search page assembly: complete rows, then approved incomplete rows."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func, select, union
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import (
    ActivitySchema,
    ActivitySearchResultSchema,
    LocationSchema,
    OrganizationContactSchema,
    OrganizationSchema,
    PricingSchema,
    ScheduleEntrySchema,
    ScheduleSchema,
)
from app.db.age_bounds import inclusive_age_bounds
from app.db.incomplete_search import (
    build_incomplete_search_query,
    incomplete_activity_ids_query,
)
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    Location,
    Organization,
)
from app.db.queries import (
    ActivitySearchCursor,
    ActivitySearchFilters,
    build_search_query,
)
from app.exceptions import CursorError
from app.services.description_boilerplate import (
    hides_template_description,
    omit_import_boilerplate,
)
from app.utils.translations import build_translation_map


def load_search_rows(
    session: Session,
    filters: ActivitySearchFilters,
) -> tuple[list[Any], str | None]:
    """Complete rows first, then approved rows missing a price or schedule."""

    requested = filters.limit
    phase = filters.cursor.phase if filters.cursor is not None else "complete"
    loaded = selectinload(ActivitySchedule.entries)
    if phase == "incomplete":
        if not filters.include_incomplete:
            return [], None
        return _incomplete_page(session, filters, requested, loaded=loaded)

    complete_filters = replace(filters, limit=requested + 1)
    complete_rows = list(
        session.execute(build_search_query(complete_filters).options(loaded)).all()
    )
    if len(complete_rows) > requested:
        page = complete_rows[:requested]
        last_row = page[-1]
        schedule = last_row._mapping[ActivitySchedule]
        return page, encode_complete_cursor(
            last_row._mapping["order_day_of_week"],
            last_row._mapping["order_start_minutes"],
            schedule.id,
            sort=filters.sort,
            price_key=last_row._mapping["order_price"],
        )
    if not filters.include_incomplete:
        return complete_rows, None
    remaining = requested - len(complete_rows)
    if remaining == 0:
        probe, _probe_cursor = _incomplete_page(session, filters, 1, loaded=loaded)
        if not probe:
            return complete_rows, None
        return complete_rows, encode_incomplete_cursor(None)
    extra, extra_cursor = _incomplete_page(session, filters, remaining, loaded=loaded)
    return [*complete_rows, *extra], extra_cursor


def count_search_activities(session: Session, filters: ActivitySearchFilters) -> int:
    """Distinct activities matching the filters across every page."""

    unpaged = replace(filters, cursor=None, limit=1)
    complete_ids = (
        build_search_query(unpaged)
        .with_only_columns(Activity.id.label("activity_id"))
        .order_by(None)
        .limit(None)
    )
    if filters.include_incomplete:
        matched = union(complete_ids, incomplete_activity_ids_query(unpaged)).subquery()
    else:
        matched = complete_ids.subquery()
    return int(session.scalar(select(func.count(distinct(matched.c.activity_id)))) or 0)


def _incomplete_page(
    session: Session,
    filters: ActivitySearchFilters,
    limit: int,
    *,
    loaded: Any,
) -> tuple[list[Any], str | None]:
    """One page of approved activities that lack a price or a schedule."""

    if limit <= 0:
        return [], None
    query_filters = replace(filters, limit=limit + 1)
    rows = list(
        session.execute(
            build_incomplete_search_query(
                query_filters,
                after=filters.cursor,
            ).options(loaded)
        ).all()
    )
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    activity = page[-1]._mapping[Activity]
    organization = page[-1]._mapping[Organization]
    return page, encode_incomplete_cursor(activity.id, organization.name, activity.name)


def map_row_to_result(
    row: Any,
    region_cache: dict[str, str | None],
    include_place_id: bool = False,
    view: str = "full",
) -> ActivitySearchResultSchema:
    """Map a SQLAlchemy row to a search result schema."""

    mapping = row._mapping
    activity: Activity = mapping[Activity]
    organization: Organization = mapping[Organization]
    location: Location = mapping[Location]
    pricing: ActivityPricing | None = mapping[ActivityPricing]
    schedule: ActivitySchedule | None = mapping[ActivitySchedule]

    age_min, age_max = inclusive_age_bounds(activity.age_range)
    card = view == "card"
    is_template = hides_template_description(
        organization.description_source, organization.description
    )
    org_description = None if is_template or card else organization.description
    org_desc_translations = (
        {}
        if is_template or card
        else omit_import_boilerplate(
            build_translation_map(
                organization.description, organization.description_translations
            )
        )
    )
    activity_description = None if is_template or card else activity.description
    activity_desc_translations = (
        {}
        if is_template or card
        else omit_import_boilerplate(
            build_translation_map(
                activity.description, activity.description_translations
            )
        )
    )
    media_urls = list(organization.media_urls or [])
    if card:
        media_urls = media_urls[:1]

    return ActivitySearchResultSchema(
        activity=ActivitySchema(
            id=str(activity.id),
            name=activity.name,
            description=activity_description,
            name_translations=build_translation_map(
                activity.name, activity.name_translations
            ),
            description_translations=activity_desc_translations,
            age_min=age_min,
            age_max=age_max,
            category_id=str(activity.category_id),
        ),
        organization=OrganizationSchema(
            id=str(organization.id),
            name=organization.name,
            description=org_description,
            name_translations=build_translation_map(
                organization.name, organization.name_translations
            ),
            description_translations=org_desc_translations,
            media_urls=media_urls,
            logo_media_url=organization.logo_media_url,
            status=organization.status,
            description_source=organization.description_source,
            place_id=organization.place_id if include_place_id else None,
            parent_verified=bool(organization.parent_verified),
            updated_at=organization.updated_at,
            contact=None if card else _contact(organization),
        ),
        location=LocationSchema(
            id=str(location.id),
            area_id=str(location.area_id),
            region_area_id=region_cache.get(str(location.area_id)),
            name=location.name,
            address=location.address,
            lat=location.lat,
            lng=location.lng,
            status=location.status,
        ),
        pricing=(
            None
            if pricing is None
            else PricingSchema(
                pricing_type=pricing.pricing_type.value,
                amount=pricing.amount,
                currency=pricing.currency,
                sessions_count=pricing.sessions_count,
                free_trial_class_offered=pricing.free_trial_class_offered,
            )
        ),
        schedule=(
            None
            if schedule is None
            else ScheduleSchema(
                schedule_type=schedule.schedule_type.value,
                weekly_entries=_serialize_weekly_entries(
                    schedule, limit=1 if card else None
                ),
                languages=schedule.languages or [],
            )
        ),
    )


def _contact(organization: Organization) -> OrganizationContactSchema:
    return OrganizationContactSchema(
        website=organization.website,
        email=organization.email,
        phone_country_code=organization.phone_country_code,
        phone_number=organization.phone_number,
        whatsapp=organization.whatsapp,
        facebook=organization.facebook,
        instagram=organization.instagram,
        tiktok=organization.tiktok,
        twitter=organization.twitter,
        xiaohongshu=organization.xiaohongshu,
        wechat=organization.wechat,
    )


def _serialize_weekly_entries(
    schedule: ActivitySchedule,
    limit: int | None = None,
) -> list[ScheduleEntrySchema]:
    """Serialize schedule entries for search responses."""
    entries = sorted(
        schedule.entries or [],
        key=lambda entry: (
            entry.day_of_week_utc,
            entry.start_minutes_utc,
            entry.end_minutes_utc,
        ),
    )
    if limit is not None:
        entries = entries[:limit]
    return [
        ScheduleEntrySchema(
            day_of_week_utc=entry.day_of_week_utc,
            start_minutes_utc=entry.start_minutes_utc,
            end_minutes_utc=entry.end_minutes_utc,
        )
        for entry in entries
    ]


def parse_cursor(value: str | None) -> ActivitySearchCursor | None:
    """Parse a pagination cursor."""

    if value is None or value == "":
        return None
    try:
        payload = decode_cursor(value)
        phase = str(payload.get("phase") or "complete")
        if phase == "incomplete":
            raw_activity = payload.get("activity_id")
            return ActivitySearchCursor(
                day_of_week_utc=0,
                start_minutes_utc=0,
                schedule_id=UUID(int=0),
                phase="incomplete",
                activity_id=UUID(str(raw_activity)) if raw_activity else None,
                org_name=_cursor_text(payload.get("org_name")),
                activity_name=_cursor_text(payload.get("activity_name")),
            )
        if phase != "complete":
            raise CursorError("Malformed cursor payload")
        sort = str(payload.get("sort") or "time")
        raw_price = payload.get("price_key")
        return ActivitySearchCursor(
            day_of_week_utc=payload["day_of_week_utc"],
            start_minutes_utc=payload["start_minutes_utc"],
            schedule_id=UUID(payload["schedule_id"]),
            sort=sort,
            price_key=Decimal(str(raw_price)) if raw_price is not None else None,
        )
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        raise CursorError("Malformed cursor payload") from exc


def encode_cursor(
    day_of_week_utc: int,
    start_minutes_utc: int,
    schedule_id: UUID,
) -> str:
    """Encode a schedule cursor. Kept for callers of the previous helper."""
    return encode_complete_cursor(day_of_week_utc, start_minutes_utc, schedule_id)


def encode_complete_cursor(
    day_of_week_utc: int,
    start_minutes_utc: int,
    schedule_id: UUID,
    *,
    sort: str = "time",
    price_key: Decimal | None = None,
) -> str:
    """Encode a cursor that continues the complete rows in ``sort`` order."""
    payload: dict[str, Any] = {
        "phase": "complete",
        "schedule_id": str(schedule_id),
        "day_of_week_utc": day_of_week_utc,
        "start_minutes_utc": start_minutes_utc,
    }
    if sort != "time":
        payload["sort"] = sort
        payload["price_key"] = None if price_key is None else str(price_key)
    return _encode_cursor_payload(payload)


def encode_incomplete_cursor(
    activity_id: UUID | None,
    org_name: str | None = None,
    activity_name: str | None = None,
) -> str:
    """Encode a cursor that continues the approved incomplete rows."""
    payload: dict[str, Any] = {
        "phase": "incomplete",
        "activity_id": None if activity_id is None else str(activity_id),
    }
    if activity_id is not None:
        payload["org_name"] = org_name or ""
        payload["activity_name"] = activity_name or ""
    return _encode_cursor_payload(payload)


def _cursor_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _encode_cursor_payload(payload: Mapping[str, Any]) -> str:
    """Encode a pagination cursor."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode(
        "utf-8"
    )
    return encoded.rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a pagination cursor."""

    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding)
    return json.loads(raw)
