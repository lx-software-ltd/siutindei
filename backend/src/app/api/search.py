"""Lambda handler for search.

This module provides the public search API endpoint,
using shared utilities and centralized database management.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.partner_auth import PartnerContext, get_partner_context
from app.api.schemas import ActivitySearchResponseSchema, dump_search_response
from app.api.search_feedback import load_ratings, load_reviews
from app.api.search_page import (
    count_search_activities,
    load_search_categories,
    map_row_to_result,
)
from app.api.search_page import load_search_rows as _load_search_rows
from app.api.search_page import parse_cursor as _parse_cursor
from app.api.search_validation import (
    validate_date_window,
    validate_listing_filters,
    validate_search_query_params,
    validate_search_refinements,
)
from app.db.engine import get_engine
from app.db.models import GeographicArea, PricingType, ScheduleType
from app.db.queries import (
    ActivitySearchFilters,
    applied_search_area_scope,
    category_match_mode,
    search_area_scope_labels,
)
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
    refinements = validate_search_refinements(
        days_of_week_hkt=[
            parse_int(value) for value in params.get("day_of_week_hkt", []) if value
        ],
        free_trial=first_param(params, "free_trial"),
        class_price_max=parse_decimal(first_param(params, "class_price_max")),
        sort=first_param(params, "sort"),
        include_total=first_param(params, "include_total"),
    )
    listing = validate_listing_filters(
        kinds=params.get("kind", []),
        age=age,
        age_min=parse_int(first_param(params, "age_min")),
        age_max=parse_int(first_param(params, "age_max")),
        verified=first_param(params, "verified"),
    )
    date_from, date_to = validate_date_window(
        first_param(params, "date_from"), first_param(params, "date_to")
    )
    cursor = _parse_cursor(first_param(params, "cursor"))
    if (
        cursor is not None
        and cursor.phase == "complete"
        and cursor.sort != refinements.sort
    ):
        raise CursorError("Cursor does not match sort")

    return ActivitySearchFilters(
        age=age,
        area_id=area_id,
        activity_id=activity_id,
        org_ids=tuple(parse_uuid_list(params.get("organization_id", []))),
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
        cursor=cursor,
        limit=limit,
        text_query=validated.text_query,
        view=validated.view,
        include_incomplete=validated.include_incomplete,
        days_of_week_hkt=refinements.days_of_week_hkt,
        free_trial=refinements.free_trial,
        class_price_max=refinements.class_price_max,
        sort=refinements.sort,
        include_total=refinements.include_total,
        kinds=listing.kinds,
        age_min=listing.age_min,
        age_max=listing.age_max,
        verified_only=listing.verified,
        date_from=date_from,
        date_to=date_to,
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
        categories = load_search_categories(session) if rows else {}
        items = [
            map_row_to_result(
                row,
                region_cache,
                include_place_id=include_place_id,
                view=filters.view,
                categories=categories,
            )
            for row in rows
        ]
        ratings = load_ratings(session, (item.organization.id for item in items))
        reviews_by_org: dict[str, list] = {}
        if filters.activity_id is not None and filters.view != "card":
            for org_id in {item.organization.id for item in items}:
                reviews_by_org[org_id] = load_reviews(session, org_id)
        for item in items:
            item.organization.rating = ratings.get(item.organization.id)
            item.organization.reviews = reviews_by_org.get(item.organization.id, [])
        total = (
            count_search_activities(session, filters)
            if filters.include_total and filters.cursor is None
            else None
        )
    return ActivitySearchResponseSchema(
        items=items,
        next_cursor=next_cursor,
        category_match=match_mode,
        area_scope=search_area_scope_labels(),
        total=total,
    )


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
