"""Query builders for search."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on  # type: ignore[attr-defined]
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import CompoundSelect

from app.data.hk_neighbourhoods import resolve_search_area_scope
from app.db.category_visibility import public_category_clause
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    GeographicArea,
    Location,
    Organization,
    PricingType,
    ScheduleType,
)
from app.db.models.category_suggestion import (
    LEGACY_CATEGORY_IDS,
    PENDING_CATEGORY_ID,
    WIZARD_GROUP_IDS,
)
from app.db.search_conditions import (
    SEARCH_SORTS,
    UNPRICED_SORT_KEY,
    apply_entry_filters,
    build_language_conditions,
    price_conditions,
    price_sort_key,
    text_query_condition,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ActivitySearchCursor:
    """Cursor for activity search pagination.

    ``phase`` is ``complete`` for a schedule row and ``incomplete`` for
    an approved activity that is missing a price, a schedule, or both.
    Older cursors omit ``phase`` and stay on the complete rows.
    """

    day_of_week_utc: int
    start_minutes_utc: int
    schedule_id: UUID
    phase: str = "complete"
    activity_id: UUID | None = None
    org_name: str | None = None
    activity_name: str | None = None
    sort: str = "time"
    price_key: Decimal | None = None


@dataclass(frozen=True)
class ActivitySearchFilters:
    """Filters for activity search queries."""

    age: int | None = None
    area_id: UUID | None = None
    category_ids: Sequence[UUID] = ()
    pricing_type: PricingType | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    schedule_type: ScheduleType | None = None
    day_of_week_utc: int | None = None
    start_minutes_utc: int | None = None
    end_minutes_utc: int | None = None
    languages: Sequence[str] = ()
    activity_id: UUID | None = None
    org_ids: Sequence[UUID] = ()
    cursor: ActivitySearchCursor | None = None
    limit: int = 50
    text_query: str | None = None
    view: str = "full"
    apply_area_scope: bool = True
    include_incomplete: bool = False
    days_of_week_hkt: Sequence[int] = ()
    free_trial: bool = False
    class_price_max: Decimal | None = None
    sort: str = "time"
    include_total: bool = False


def validate_filters(filters: ActivitySearchFilters) -> None:
    """Validate filter combinations for search."""

    if (
        filters.start_minutes_utc is not None
        and filters.end_minutes_utc is not None
        and filters.start_minutes_utc >= filters.end_minutes_utc
    ):
        raise ValueError("start_minutes_utc must be less than end_minutes_utc.")

    if filters.limit <= 0 or filters.limit > 200:
        raise ValueError("limit must be between 1 and 200.")

    if filters.sort not in SEARCH_SORTS:
        raise ValueError("sort must be time or price.")


def build_search_query(filters: ActivitySearchFilters) -> Select:
    """Build a SQLAlchemy query for search."""

    validate_filters(filters)
    area_scope = applied_search_area_scope(filters)

    entry_subquery = _entry_order_subquery(filters)
    query = (
        select(
            Activity,
            Organization,
            Location,
            ActivityPricing,
            ActivitySchedule,
            entry_subquery.c.day_of_week_utc.label("order_day_of_week"),
            entry_subquery.c.start_minutes_utc.label("order_start_minutes"),
            price_sort_key().label("order_price"),
        )
        .join(Organization, Organization.id == Activity.org_id)
        .join(ActivitySchedule, ActivitySchedule.activity_id == Activity.id)
        .join(
            entry_subquery,
            entry_subquery.c.schedule_id == ActivitySchedule.id,
        )
        .join(Location, Location.id == ActivitySchedule.location_id)
        .join(
            ActivityPricing,
            and_(
                ActivityPricing.activity_id == Activity.id,
                ActivityPricing.location_id == Location.id,
            ),
        )
        .where(Organization.status.in_(("operational", "closed_temporarily")))
        .where(Location.status.in_(("open", "temporarily_closed")))
    )
    if review_gate_enabled():
        query = query.where(Organization.review_status == "approved")
    query = query.where(Activity.category_id != PENDING_CATEGORY_ID)
    query = query.where(public_category_clause(Activity.category_id))

    conditions: list = []

    if filters.age is not None:
        conditions.append(Activity.age_range.contains(filters.age))

    if filters.area_id is not None:
        area_ids = area_descendant_ids_subquery(filters.area_id)
        conditions.append(Location.area_id.in_(area_ids))

    if filters.category_ids:
        category_ids = _category_descendant_ids_subquery(
            filters.category_ids,
            area_scope,
        )
        conditions.append(Activity.category_id.in_(category_ids))

    if filters.activity_id is not None:
        conditions.append(Activity.id == filters.activity_id)

    if filters.org_ids:
        conditions.append(Activity.org_id.in_(filters.org_ids))

    conditions.extend(price_conditions(filters))

    if filters.schedule_type is not None:
        conditions.append(ActivitySchedule.schedule_type == filters.schedule_type)

    if filters.languages:
        language_conditions = build_language_conditions(filters.languages)
        conditions.append(or_(*language_conditions))

    if filters.text_query:
        conditions.append(text_query_condition(filters.text_query))

    if area_scope is not None:
        if area_scope:
            conditions.append(Location.area_id.in_(tuple(area_scope)))
        else:
            conditions.append(sa.false())

    order_columns = _order_columns(entry_subquery, filters.sort)
    if filters.cursor is not None:
        cursor_values = _cursor_values(filters.cursor, filters.sort)
        conditions.append(sa.tuple_(*order_columns) > sa.tuple_(*cursor_values))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(*order_columns)
    return query.limit(filters.limit)


def _entry_order_subquery(filters: ActivitySearchFilters) -> sa.Subquery:
    """Pick the first entry per schedule without a window over every row.

    Inner order is schedule, day, start, id. The outer query still orders
    by day, start, then schedule id.
    """
    entry_query = (
        select(
            ActivityScheduleEntry.schedule_id.label("schedule_id"),
            ActivityScheduleEntry.day_of_week_utc.label("day_of_week_utc"),
            ActivityScheduleEntry.start_minutes_utc.label("start_minutes_utc"),
            ActivityScheduleEntry.id.label("entry_id"),
        )
        .ext(distinct_on(ActivityScheduleEntry.schedule_id))  # type: ignore[attr-defined]
        .order_by(
            ActivityScheduleEntry.schedule_id,
            ActivityScheduleEntry.day_of_week_utc,
            ActivityScheduleEntry.start_minutes_utc,
            ActivityScheduleEntry.id,
        )
    )
    conditions: list = []
    apply_entry_filters(filters, conditions)
    if conditions:
        entry_query = entry_query.where(and_(*conditions))
    return entry_query.subquery()


def _order_columns(entry_subquery: sa.Subquery, sort: str = "time") -> list:
    """Return ordering columns for pagination."""
    columns = [
        entry_subquery.c.day_of_week_utc,
        entry_subquery.c.start_minutes_utc,
        ActivitySchedule.id,
    ]
    if sort == "price":
        return [price_sort_key(), *columns]
    return columns


def _cursor_values(cursor: ActivitySearchCursor, sort: str = "time") -> list:
    """Return ordering values for the cursor comparison."""
    values: list = [
        cursor.day_of_week_utc,
        cursor.start_minutes_utc,
        cursor.schedule_id,
    ]
    if sort == "price":
        price_key = (
            cursor.price_key if cursor.price_key is not None else UNPRICED_SORT_KEY
        )
        return [price_key, *values]
    return values


def _wizard_group_filter(category_ids: Sequence[UUID]) -> bool:
    """True when every requested id is one of the seven wizard groups."""
    return bool(category_ids) and all(item in WIZARD_GROUP_IDS for item in category_ids)


def category_match_mode(
    session: Session,
    category_ids: Sequence[UUID],
    area_ids: frozenset[UUID] | None = None,
) -> str:
    """Return exact, or legacy_fallback while a wizard group is still empty.

    An empty group would otherwise hide every activity that is still on
    Workshop, Class, Outdoor activity, Indoor fun, or Sport. When
    ``area_ids`` is set, only activities with a schedule in one of those
    neighbourhoods count, so a group that exists only outside the public
    area scope can still fall back.
    """
    if not _wizard_group_filter(category_ids):
        return "exact"
    if area_ids is not None and not area_ids:
        return "exact"
    tree = _category_tree(category_ids)
    assigned_query = (
        select(func.count())
        .select_from(Activity)
        .where(Activity.category_id.in_(select(tree.c.id)))
        .where(Activity.category_id.notin_(tuple(LEGACY_CATEGORY_IDS)))
    )
    in_scope = _activity_in_area_scope(area_ids)
    if in_scope is not None:
        assigned_query = assigned_query.where(in_scope)
    assigned = session.scalar(assigned_query)
    return "legacy_fallback" if not assigned else "exact"


def _activity_in_area_scope(area_ids: frozenset[UUID] | None) -> Any | None:
    """Match activities that have a schedule at one of these neighbourhoods."""
    if area_ids is None:
        return None
    if not area_ids:
        return sa.false()
    return Activity.id.in_(
        select(ActivitySchedule.activity_id)
        .join(Location, Location.id == ActivitySchedule.location_id)
        .where(Location.area_id.in_(tuple(area_ids)))
    )


def _category_descendant_ids_subquery(
    category_ids: Sequence[UUID],
    area_ids: frozenset[UUID] | None = None,
) -> Select[Any] | CompoundSelect[Any]:
    """Return category ids, including descendants.

    A wizard-group search with no activities on that subtree also
    includes the legacy roots. The union drops out once any activity
    sits on the group or one of its leaves. ``area_ids`` limits that
    count to schedules in the public area scope.
    """
    tree = _category_tree(category_ids)
    descendants = select(tree.c.id)
    if not _wizard_group_filter(category_ids):
        return descendants
    if area_ids is not None and not area_ids:
        return descendants
    assigned = (
        select(Activity.id)
        .where(Activity.category_id.in_(select(tree.c.id)))
        .where(Activity.category_id.notin_(tuple(LEGACY_CATEGORY_IDS)))
    )
    in_scope = _activity_in_area_scope(area_ids)
    if in_scope is not None:
        assigned = assigned.where(in_scope)
    legacy = select(ActivityCategory.id).where(
        ActivityCategory.id.in_(tuple(LEGACY_CATEGORY_IDS)),
        ~assigned.exists(),
    )
    return descendants.union(legacy)


def _category_tree(category_ids: Sequence[UUID]) -> Any:
    """Recursive category ids starting at the requested rows."""
    base = (
        select(ActivityCategory.id)
        .where(ActivityCategory.id.in_(tuple(category_ids)))
        .where(ActivityCategory.id != PENDING_CATEGORY_ID)
        .cte(name="category_tree", recursive=True)
    )
    categories = ActivityCategory.__table__
    recursive = select(categories.c.id).where(
        categories.c.parent_id == base.c.id,
        categories.c.id != PENDING_CATEGORY_ID,
    )
    return base.union_all(recursive)


def area_descendant_ids_subquery(area_id: UUID) -> Select[Any]:
    """Return a subquery of area IDs including descendants."""

    base = (
        select(GeographicArea.id)
        .where(GeographicArea.id == area_id)
        .cte(recursive=True)
    )
    geographic_areas = GeographicArea.__table__
    recursive = select(geographic_areas.c.id).where(
        geographic_areas.c.parent_id == base.c.id
    )
    area_tree = base.union_all(recursive)
    return select(area_tree.c.id)


def review_gate_enabled() -> bool:
    """Public search hides unapproved orgs only when this flag is on."""
    raw = os.getenv("ORG_REVIEW_GATE_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


_SEARCH_AREA_SCOPE_CACHE: dict[str, frozenset[UUID] | None] = {}


def clear_search_area_scope_cache() -> None:
    """Drop the parsed SEARCH_AREA_SCOPE cache. Tests call this."""
    _SEARCH_AREA_SCOPE_CACHE.clear()


def configured_search_area_ids() -> frozenset[UUID] | None:
    """Neighbourhood ids from SEARCH_AREA_SCOPE.

    ``None`` means the variable is unset or blank and search is not
    limited. An empty set means every token was unknown.
    """
    raw = os.getenv("SEARCH_AREA_SCOPE", "")
    if raw in _SEARCH_AREA_SCOPE_CACHE:
        return _SEARCH_AREA_SCOPE_CACHE[raw]
    resolved, unknown = resolve_search_area_scope(raw)
    if unknown:
        logger.warning(
            "SEARCH_AREA_SCOPE ignored unknown slugs",
            extra={"unknown_slugs": ",".join(unknown)},
        )
    _SEARCH_AREA_SCOPE_CACHE[raw] = resolved
    return resolved


def search_area_scope_labels() -> list[str] | None:
    """Sorted area ids for the search response, or None when unrestricted."""
    configured = configured_search_area_ids()
    if configured is None:
        return None
    return sorted(str(area_id) for area_id in configured)


def applied_search_area_scope(
    filters: ActivitySearchFilters,
) -> frozenset[UUID] | None:
    """Ids to enforce on this request, or None when it is not limited.

    Partner calls set ``apply_area_scope`` false. A direct activity link
    stays open even when the activity sits outside the public scope.
    """
    if not filters.apply_area_scope or filters.activity_id is not None:
        return None
    return configured_search_area_ids()
