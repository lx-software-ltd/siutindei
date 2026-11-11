"""Lambda handler for search.

This module provides the public search API endpoint,
using shared utilities and centralized database management.
"""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.partner_auth import PartnerContext, get_partner_context
from app.api.schemas import (
    ActivitySchema,
    ActivitySearchResponseSchema,
    ActivitySearchResultSchema,
    LocationSchema,
    OrganizationSchema,
    PricingSchema,
    ScheduleEntrySchema,
    ScheduleSchema,
    dump_search_response,
)
from app.api.search_validation import validate_search_query_params
from app.db.age_bounds import inclusive_age_bounds
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
    applied_search_area_scope,
    build_incomplete_search_query,
    build_search_query,
    category_match_mode,
    search_area_scope_labels,
)
from app.exceptions import CursorError, ValidationError
from app.services.description_boilerplate import (
    hides_template_description,
    omit_import_boilerplate,
)
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

_REGION_CACHE_TTL_SECONDS = 600
_PUBLIC_SEARCH_CACHE_CONTROL = "public, max-age=60, s-maxage=300"
_region_area_cache: tuple[float, dict[str, str | None]] | None = None


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
        if partner is not None:
            # Partner keys are a B2B integration and are not limited to the
            # public neighbourhood scope. Org-scoped keys still see only
            # their own organization's activities.
            filters = replace(
                filters,
                apply_area_scope=False,
                org_ids=(UUID(partner.org_id),) if partner.org_id else (),
            )
        logger.debug("Search filters parsed", extra={"filters": str(filters)})
        response = fetch_search_response(filters)
        logger.info(
            f"Search completed: {len(response.items)} results",
            extra={
                "count": len(response.items),
                "has_more": response.next_cursor is not None,
            },
        )
        return _create_response(
            200,
            response,
            event,
            view=filters.view,
            edge_cacheable=partner is None,
            include_area_scope=filters.cursor is None,
        )
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

    validated = validate_search_query_params(
        age=age,
        day_of_week_utc=day_of_week_utc,
        start_minutes_utc=start_minutes_utc,
        end_minutes_utc=end_minutes_utc,
        price_min=price_min,
        price_max=price_max,
        languages=languages,
        limit=limit,
        q=first_param(params, "q"),
        view=first_param(params, "view"),
        include_incomplete=first_param(params, "include_incomplete"),
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
        languages=validated.languages,
        cursor=_parse_cursor(first_param(params, "cursor")),
        limit=limit,
        text_query=validated.text_query,
        view=validated.view,
        include_incomplete=validated.include_incomplete,
    )


def _staging_search_enabled() -> bool:
    """True when this process should read the staging fixture."""
    raw = os.environ.get("STAGING_SEARCH_DATA_ENABLED", "").strip().lower()
    return raw in {"1", "true", "yes"}


def fetch_search_response(
    filters: ActivitySearchFilters,
) -> ActivitySearchResponseSchema:
    """Fetch search response from the database or staging fixture."""

    if _staging_search_enabled():
        from app.services.staging_search_store import fetch_staging_search_response

        return fetch_staging_search_response(filters)

    engine = get_engine()
    with Session(engine) as session:
        rows, next_cursor = _load_search_rows(session, filters)
        region_cache = _load_region_area_cache(session)
        match_mode = category_match_mode(
            session,
            filters.category_ids,
            applied_search_area_scope(filters),
        )
        include_place_id = filters.activity_id is not None
        items = [
            map_row_to_result(
                row,
                region_cache,
                include_place_id=include_place_id,
                view=filters.view,
            )
            for row in rows
        ]
    return ActivitySearchResponseSchema(
        items=items,
        next_cursor=next_cursor,
        category_match=match_mode,
        area_scope=search_area_scope_labels(),
    )


def _load_search_rows(
    session: Session,
    filters: ActivitySearchFilters,
) -> tuple[list[Any], str | None]:
    """Complete rows first, then approved rows missing a price or schedule."""

    requested = filters.limit
    phase = filters.cursor.phase if filters.cursor is not None else "complete"
    loaded = selectinload(ActivitySchedule.entries)
    if phase == "incomplete":
        return _incomplete_page(
            session,
            filters,
            requested,
            after_activity_id=(
                filters.cursor.activity_id if filters.cursor is not None else None
            ),
            loaded=loaded,
        )

    complete_filters = replace(filters, limit=requested + 1)
    complete_rows = list(
        session.execute(build_search_query(complete_filters).options(loaded)).all()
    )
    if len(complete_rows) > requested:
        page = complete_rows[:requested]
        last_row = page[-1]
        schedule = last_row._mapping[ActivitySchedule]
        return page, _encode_complete_cursor(
            last_row._mapping["order_day_of_week"],
            last_row._mapping["order_start_minutes"],
            schedule.id,
        )
    if not filters.include_incomplete:
        return complete_rows, None
    remaining = requested - len(complete_rows)
    if remaining == 0:
        probe, _probe_cursor = _incomplete_page(
            session,
            filters,
            1,
            after_activity_id=None,
            loaded=loaded,
        )
        if not probe:
            return complete_rows, None
        return complete_rows, _encode_incomplete_cursor(None)
    extra, extra_cursor = _incomplete_page(
        session,
        filters,
        remaining,
        after_activity_id=None,
        loaded=loaded,
    )
    return [*complete_rows, *extra], extra_cursor


def _incomplete_page(
    session: Session,
    filters: ActivitySearchFilters,
    limit: int,
    *,
    after_activity_id: UUID | None,
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
                after_activity_id=after_activity_id,
            ).options(loaded)
        ).all()
    )
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    activity = page[-1]._mapping[Activity]
    return page, _encode_incomplete_cursor(activity.id)


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
        ),
        location=LocationSchema(
            id=str(location.id),
            area_id=str(location.area_id),
            region_area_id=region_cache.get(str(location.area_id)),
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


def clear_region_area_cache() -> None:
    """Drop the cached area-to-region map. Tests call this between cases."""
    global _region_area_cache
    _region_area_cache = None


def _load_region_area_cache(session: Session) -> dict[str, str | None]:
    """Map each geographic area id to its level=region ancestor id.

    The map is reused for ten minutes inside one Lambda container.
    """
    global _region_area_cache
    now = time.monotonic()
    cached = _region_area_cache
    if cached is not None and now - cached[0] < _REGION_CACHE_TTL_SECONDS:
        return cached[1]
    built = _build_region_area_map(session)
    _region_area_cache = (now, built)
    return built


def _build_region_area_map(session: Session) -> dict[str, str | None]:
    """Load the area-to-region map from the current session."""
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


def _create_response(
    status_code: int,
    body: ActivitySearchResponseSchema,
    event: Mapping[str, Any] | None = None,
    view: str = "full",
    edge_cacheable: bool = False,
    include_area_scope: bool = True,
) -> dict[str, Any]:
    """Create a JSON API Gateway response for Pydantic models."""

    payload = dump_search_response(body, view, include_area_scope=include_area_scope)
    separators = (",", ":") if view == "card" else (", ", ": ")

    headers = {
        "Content-Type": "application/json",
        **get_security_headers(),
    }
    if edge_cacheable:
        # Public results are shared by every caller. The public-website
        # CloudFront search behavior caps its TTL at 300 seconds.
        headers.pop("Pragma", None)
        headers["Cache-Control"] = _PUBLIC_SEARCH_CACHE_CONTROL
    headers.update(get_cors_headers(event))

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(payload, default=str, separators=separators),
    }


# --- Cursor encoding/decoding ---


def _parse_cursor(value: str | None) -> ActivitySearchCursor | None:
    """Parse a pagination cursor."""

    if value is None or value == "":
        return None
    try:
        payload = _decode_cursor(value)
        phase = str(payload.get("phase") or "complete")
        if phase == "incomplete":
            raw_activity = payload.get("activity_id")
            return ActivitySearchCursor(
                day_of_week_utc=0,
                start_minutes_utc=0,
                schedule_id=UUID(int=0),
                phase="incomplete",
                activity_id=UUID(str(raw_activity)) if raw_activity else None,
            )
        if phase != "complete":
            raise CursorError("Malformed cursor payload")
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
    """Encode a schedule cursor. Kept for callers of the previous helper."""
    return _encode_complete_cursor(day_of_week_utc, start_minutes_utc, schedule_id)


def _encode_complete_cursor(
    day_of_week_utc: int,
    start_minutes_utc: int,
    schedule_id: UUID,
) -> str:
    """Encode a cursor that continues the schedule-ordered rows."""
    return _encode_cursor_payload(
        {
            "phase": "complete",
            "schedule_id": str(schedule_id),
            "day_of_week_utc": day_of_week_utc,
            "start_minutes_utc": start_minutes_utc,
        }
    )


def _encode_incomplete_cursor(activity_id: UUID | None) -> str:
    """Encode a cursor that continues the approved incomplete rows."""
    return _encode_cursor_payload(
        {
            "phase": "incomplete",
            "activity_id": None if activity_id is None else str(activity_id),
        }
    )


def _encode_cursor_payload(payload: Mapping[str, Any]) -> str:
    """Encode a pagination cursor."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode(
        "utf-8"
    )
    return encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a pagination cursor."""

    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding)
    return json.loads(raw)
