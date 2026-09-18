"""Lambda handler for search.

This module provides the public search API endpoint,
using shared utilities and centralized database management.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import (
    ActivitySchema,
    ActivitySearchResponseSchema,
    ActivitySearchResultSchema,
    LocationSchema,
    OrganizationSchema,
    PricingSchema,
    ScheduleEntrySchema,
    ScheduleSchema,
)
from app.db.engine import get_engine
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    GeographicArea,
    Location,
    Organization,
    PricingType,
    ScheduleType,
)
from app.db.queries import (
    ActivitySearchCursor,
    ActivitySearchFilters,
    build_search_query,
)
from app.api.partner_auth import PartnerContext, get_partner_context
from app.api.search_validation import validate_search_query_params
from app.exceptions import CursorError, ValidationError
from app.utils import json_response, parse_decimal, parse_enum, parse_int
from app.utils.logging import configure_logging, get_logger, set_request_context
from app.utils.parsers import (
    collect_query_params,
    first_param,
    parse_languages,
    parse_uuid_list,
)
from app.utils.responses import get_cors_headers, get_security_headers
from app.utils.translations import build_translation_map

# Configure logging on module load
configure_logging()
logger = get_logger(__name__)


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Handle API Gateway request for search."""

    # Set request context for logging
    request_id = event.get("requestContext", {}).get("requestId", "")
    set_request_context(req_id=request_id)

    partner: PartnerContext | None = None
    if _is_partner_path(event.get("path", "")):
        partner = get_partner_context(event)
        if partner is None:
            logger.warning("Partner search called without API-key context")
            return json_response(403, {"error": "Forbidden"}, event=event)

    try:
        filters = parse_filters(event)
        if partner is not None and partner.org_id is not None:
            # Org-scoped keys only see their own organization's activities.
            filters = replace(filters, org_ids=(UUID(partner.org_id),))
        logger.debug("Search filters parsed", extra={"filters": str(filters)})
        response = fetch_search_response(filters)
        logger.info(
            f"Search completed: {len(response.items)} results",
            extra={
                "count": len(response.items),
                "has_more": response.next_cursor is not None,
            },
        )
        return _create_response(200, response, event)
    except (ValidationError, CursorError) as exc:
        logger.warning(f"Validation error: {exc.message}")
        return json_response(exc.status_code, exc.to_dict(), event=event)
    except ValueError as exc:
        logger.warning(f"Value error: {exc}")
        return json_response(400, {"error": str(exc)}, event=event)
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception(f"Unexpected error in search: {type(exc).__name__}")
        return json_response(500, {"error": "Internal server error"}, event=event)


def _is_partner_path(path: str) -> bool:
    """Return True for /v1/partner/activities/search requests."""
    parts = [segment for segment in path.split("/") if segment]
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    return parts[:1] == ["partner"]


def parse_filters(event: Mapping[str, Any]) -> ActivitySearchFilters:
    """Parse query parameters into search filters."""

    params = collect_query_params(event)

    area_id_str = first_param(params, "area_id")
    area_id = UUID(area_id_str) if area_id_str else None

    activity_id_str = first_param(params, "activity_id")
    activity_id = UUID(activity_id_str) if activity_id_str else None

    age = parse_int(first_param(params, "age"))
    day_of_week_utc = parse_int(first_param(params, "day_of_week_utc"))
    start_minutes_utc = parse_int(first_param(params, "start_minutes_utc"))
    end_minutes_utc = parse_int(first_param(params, "end_minutes_utc"))
    price_min = parse_decimal(first_param(params, "price_min"))
    price_max = parse_decimal(first_param(params, "price_max"))
    languages = parse_languages(params.get("language", []))
    limit = parse_int(first_param(params, "limit")) or 50

    validated_languages = validate_search_query_params(
        age=age,
        day_of_week_utc=day_of_week_utc,
        start_minutes_utc=start_minutes_utc,
        end_minutes_utc=end_minutes_utc,
        price_min=price_min,
        price_max=price_max,
        languages=languages,
        limit=limit,
    )

    return ActivitySearchFilters(
        age=age,
        area_id=area_id,
        activity_id=activity_id,
        category_ids=parse_uuid_list(params.get("category_id", [])),
        pricing_type=parse_enum(first_param(params, "pricing_type"), PricingType),
        price_min=price_min,
        price_max=price_max,
        schedule_type=parse_enum(
            first_param(params, "schedule_type"),
            ScheduleType,
        ),
        day_of_week_utc=day_of_week_utc,
        start_minutes_utc=start_minutes_utc,
        end_minutes_utc=end_minutes_utc,
        languages=validated_languages,
        cursor=_parse_cursor(first_param(params, "cursor")),
        limit=limit,
    )


def fetch_search_response(
    filters: ActivitySearchFilters,
) -> ActivitySearchResponseSchema:
    """Fetch search response from the database or staging fixture."""

    from app.services.staging_search_store import (
        fetch_staging_search_response,
        staging_search_data_enabled,
    )

    if staging_search_data_enabled():
        return fetch_staging_search_response(filters)

    engine = get_engine()
    requested_limit = filters.limit
    query_filters = replace(filters, limit=requested_limit + 1)
    query = build_search_query(query_filters).options(
        selectinload(ActivitySchedule.entries)
    )

    with Session(engine) as session:
        rows = session.execute(query).all()
        region_cache = _load_region_area_cache(session)

    has_more = len(rows) > requested_limit
    trimmed_rows = rows[:requested_limit]
    include_place_id = filters.activity_id is not None
    items = [
        map_row_to_result(
            row,
            region_cache,
            include_place_id=include_place_id,
        )
        for row in trimmed_rows
    ]
    next_cursor = None
    if has_more and trimmed_rows:
        last_row = trimmed_rows[-1]
        schedule = last_row._mapping[ActivitySchedule]
        order_day = last_row._mapping["order_day_of_week"]
        order_start = last_row._mapping["order_start_minutes"]
        next_cursor = _encode_cursor(order_day, order_start, schedule.id)
    return ActivitySearchResponseSchema(items=items, next_cursor=next_cursor)


def map_row_to_result(
    row: Any,
    region_cache: dict[str, str | None],
    include_place_id: bool = False,
) -> ActivitySearchResultSchema:
    """Map a SQLAlchemy row to a search result schema."""

    mapping = row._mapping
    activity: Activity = mapping[Activity]
    organization: Organization = mapping[Organization]
    location: Location = mapping[Location]
    pricing: ActivityPricing = mapping[ActivityPricing]
    schedule: ActivitySchedule = mapping[ActivitySchedule]

    age_min, age_max = _extract_age_bounds(activity.age_range)
    is_template = organization.description_source == "template"
    org_description = None if is_template else organization.description
    org_desc_translations = (
        {}
        if is_template
        else build_translation_map(
            organization.description, organization.description_translations
        )
    )
    activity_description = None if is_template else activity.description
    activity_desc_translations = (
        {}
        if is_template
        else build_translation_map(
            activity.description, activity.description_translations
        )
    )

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
            manager_id=organization.manager_id,
            media_urls=organization.media_urls or [],
            logo_media_url=organization.logo_media_url,
            status=organization.status,
            description_source=organization.description_source,
            place_id=organization.place_id if include_place_id else None,
        ),
        location=LocationSchema(
            id=str(location.id),
            area_id=str(location.area_id),
            region_area_id=region_cache.get(str(location.area_id)),
            address=location.address,
            lat=location.lat,
            lng=location.lng,
        ),
        pricing=PricingSchema(
            pricing_type=pricing.pricing_type.value,
            amount=pricing.amount,
            currency=pricing.currency,
            sessions_count=pricing.sessions_count,
            free_trial_class_offered=pricing.free_trial_class_offered,
        ),
        schedule=ScheduleSchema(
            schedule_type=schedule.schedule_type.value,
            weekly_entries=_serialize_weekly_entries(schedule),
            languages=schedule.languages or [],
        ),
    )


def _serialize_weekly_entries(
    schedule: ActivitySchedule,
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
    return [
        ScheduleEntrySchema(
            day_of_week_utc=entry.day_of_week_utc,
            start_minutes_utc=entry.start_minutes_utc,
            end_minutes_utc=entry.end_minutes_utc,
        )
        for entry in entries
    ]


def _load_region_area_cache(session: Session) -> dict[str, str | None]:
    """Map each geographic area id to its level=region ancestor id."""

    areas = session.execute(select(GeographicArea)).scalars().all()
    by_id = {str(area.id): area for area in areas}
    cache: dict[str, str | None] = {}

    def resolve_region(area_id: str) -> str | None:
        if area_id in cache:
            return cache[area_id]
        area = by_id.get(area_id)
        if area is None:
            cache[area_id] = None
            return None
        if area.level == "region":
            cache[area_id] = area_id
            return area_id
        if area.parent_id is None:
            cache[area_id] = None
            return None
        parent_key = str(area.parent_id)
        resolved = resolve_region(parent_key)
        cache[area_id] = resolved
        return resolved

    for area_key in by_id:
        resolve_region(area_key)
    return cache


def _extract_age_bounds(age_range: Any) -> tuple[int | None, int | None]:
    """Extract age range bounds from a database range value."""

    lower = getattr(age_range, "lower", None)
    upper = getattr(age_range, "upper", None)
    if lower is not None or upper is not None:
        return lower, upper

    if isinstance(age_range, str):
        cleaned = age_range.strip("[]()")
        parts = cleaned.split(",")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                return None, None
    return None, None


def _create_response(
    status_code: int,
    body: ActivitySearchResponseSchema,
    event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a JSON API Gateway response for Pydantic models."""

    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()

    headers = {
        "Content-Type": "application/json",
        **get_security_headers(),
    }
    headers.update(get_cors_headers(event))

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(payload, default=str),
    }


# --- Cursor encoding/decoding ---


def _parse_cursor(value: str | None) -> ActivitySearchCursor | None:
    """Parse a pagination cursor."""

    if value is None or value == "":
        return None
    try:
        payload = _decode_cursor(value)
        return ActivitySearchCursor(
            day_of_week_utc=payload["day_of_week_utc"],
            start_minutes_utc=payload["start_minutes_utc"],
            schedule_id=UUID(payload["schedule_id"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise CursorError("Malformed cursor payload") from exc


def _encode_cursor(
    day_of_week_utc: int,
    start_minutes_utc: int,
    schedule_id: UUID,
) -> str:
    """Encode a pagination cursor."""
    payload = json.dumps(
        {
            "schedule_id": str(schedule_id),
            "day_of_week_utc": day_of_week_utc,
            "start_minutes_utc": start_minutes_utc,
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("utf-8")
    return encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a pagination cursor."""

    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding)
    return json.loads(raw)
