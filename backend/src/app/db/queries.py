"""Query builders for search."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, any_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on  # type: ignore[attr-defined]
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import CompoundSelect

from app.data.hk_neighbourhoods import resolve_search_area_scope
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
from app.services.data_quality.list_params import ilike_pattern
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


SEARCH_SORTS = frozenset({"time", "price"})
HONG_KONG_UTC_OFFSET_MINUTES = 480
MINUTES_PER_DAY = 1440
# Rows with no comparable per-class price sort after every priced row.
UNPRICED_SORT_KEY = Decimal("1000000000")


def class_price_expression(pricing: Any = ActivityPricing) -> Any:
    """Price of one class, or NULL when the pricing type cannot say.

    Free is 0. Per class and per hour are the amount. A term with a
    session count is the amount over the count. Day, month, year, and a
    term without a count have no per-class equivalent.
    """
    return sa.case(
        (pricing.pricing_type == PricingType.FREE, sa.literal(Decimal(0))),
        (
            pricing.pricing_type.in_((PricingType.PER_CLASS, PricingType.PER_HOUR)),
            pricing.amount,
        ),
        (
            and_(
                pricing.pricing_type == PricingType.PER_SESSIONS,
                pricing.sessions_count > 0,
            ),
            pricing.amount / pricing.sessions_count,
        ),
        else_=sa.null(),
    )


def class_price_value(
    pricing_type: str | None,
    amount: Decimal | None,
    sessions_count: int | None,
) -> Decimal | None:
    """Python twin of ``class_price_expression`` for the staging fixture."""
    if pricing_type == PricingType.FREE.value:
        return Decimal(0)
    if amount is None:
        return None
    if pricing_type in (PricingType.PER_CLASS.value, PricingType.PER_HOUR.value):
        return Decimal(amount)
    if pricing_type == PricingType.PER_SESSIONS.value and sessions_count:
        return Decimal(amount) / Decimal(sessions_count)
    return None


def hong_kong_day_expression(day_of_week_utc: Any, start_minutes_utc: Any) -> Any:
    """Day of the week (0 = Sunday) on which a UTC entry starts in Hong Kong."""
    minutes = (
        day_of_week_utc * MINUTES_PER_DAY
        + start_minutes_utc
        + HONG_KONG_UTC_OFFSET_MINUTES
    )
    return sa.cast(
        func.mod(func.div(minutes, MINUTES_PER_DAY), 7),
        sa.Integer,
    )


def hong_kong_day(day_of_week_utc: int, start_minutes_utc: int) -> int:
    """Python twin of ``hong_kong_day_expression``."""
    minutes = (
        day_of_week_utc * MINUTES_PER_DAY
        + start_minutes_utc
        + HONG_KONG_UTC_OFFSET_MINUTES
    )
    return (minutes // MINUTES_PER_DAY) % 7


def needs_entry_filters(filters: ActivitySearchFilters) -> bool:
    """True when a filter reads schedule entries."""
    return (
        filters.day_of_week_utc is not None
        or filters.start_minutes_utc is not None
        or filters.end_minutes_utc is not None
        or bool(filters.days_of_week_hkt)
    )


def needs_price_filters(filters: ActivitySearchFilters) -> bool:
    """True when a filter reads the price row."""
    return (
        filters.pricing_type is not None
        or filters.price_min is not None
        or filters.price_max is not None
        or filters.free_trial
        or filters.class_price_max is not None
    )


def price_conditions(
    filters: ActivitySearchFilters, pricing: Any = ActivityPricing
) -> list:
    """Every price filter, applied to ``pricing``."""
    conditions: list = []
    if filters.pricing_type is not None:
        conditions.append(pricing.pricing_type == filters.pricing_type)
    if filters.price_min is not None:
        conditions.append(pricing.amount >= filters.price_min)
    if filters.price_max is not None:
        conditions.append(pricing.amount <= filters.price_max)
    if filters.free_trial:
        conditions.append(pricing.free_trial_class_offered.is_(True))
    if filters.class_price_max is not None:
        conditions.append(class_price_expression(pricing) <= filters.class_price_max)
    return conditions


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
            _price_sort_key().label("order_price"),
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
        language_conditions = _build_language_conditions(filters.languages)
        conditions.append(or_(*language_conditions))

    if filters.text_query:
        conditions.append(_text_query_condition(filters.text_query))

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
    _apply_entry_filters(filters, conditions)
    if conditions:
        entry_query = entry_query.where(and_(*conditions))
    return entry_query.subquery()


def _text_query_condition(text_query: str) -> Any:
    """Case-insensitive match on names and name translation values."""
    pattern = ilike_pattern(text_query)
    return or_(
        Activity.name.ilike(pattern, escape="\\"),
        Organization.name.ilike(pattern, escape="\\"),
        _translation_values_ilike(Activity.name_translations, pattern),
        _translation_values_ilike(Organization.name_translations, pattern),
    )


def _translation_values_ilike(column: Any, pattern: str) -> Any:
    """True when any jsonb object of name translations matches the pattern.

    ``jsonb_each_text`` errors on null, scalars, and arrays. The match is
    evaluated only when the column is an object.
    """
    translations = sa.func.jsonb_each_text(column).table_valued("key", "value")
    matches = sa.exists(
        sa.select(sa.literal(1))
        .select_from(translations)
        .where(translations.c.value.ilike(pattern, escape="\\"))
    )
    return sa.case(
        (sa.func.jsonb_typeof(column) == "object", matches),
        else_=sa.false(),
    )


def _apply_entry_filters(filters: ActivitySearchFilters, conditions: list) -> None:
    """Apply entry-level schedule filters."""
    if filters.day_of_week_utc is not None:
        conditions.append(
            ActivityScheduleEntry.day_of_week_utc == filters.day_of_week_utc
        )

    if filters.days_of_week_hkt:
        conditions.append(
            hong_kong_day_expression(
                ActivityScheduleEntry.day_of_week_utc,
                ActivityScheduleEntry.start_minutes_utc,
            ).in_(tuple(filters.days_of_week_hkt))
        )

    if filters.start_minutes_utc is not None and filters.end_minutes_utc is not None:
        normal_overlap = and_(
            ActivityScheduleEntry.start_minutes_utc < filters.end_minutes_utc,
            ActivityScheduleEntry.end_minutes_utc > filters.start_minutes_utc,
        )
        wrap_overlap = or_(
            filters.end_minutes_utc > ActivityScheduleEntry.start_minutes_utc,
            filters.start_minutes_utc < ActivityScheduleEntry.end_minutes_utc,
        )
        conditions.append(
            or_(
                and_(
                    ActivityScheduleEntry.start_minutes_utc
                    < ActivityScheduleEntry.end_minutes_utc,
                    normal_overlap,
                ),
                and_(
                    ActivityScheduleEntry.start_minutes_utc
                    > ActivityScheduleEntry.end_minutes_utc,
                    wrap_overlap,
                ),
            )
        )
    elif filters.start_minutes_utc is not None:
        conditions.append(
            or_(
                ActivityScheduleEntry.start_minutes_utc
                > ActivityScheduleEntry.end_minutes_utc,
                ActivityScheduleEntry.end_minutes_utc >= filters.start_minutes_utc,
            )
        )
    elif filters.end_minutes_utc is not None:
        conditions.append(
            or_(
                ActivityScheduleEntry.start_minutes_utc
                > ActivityScheduleEntry.end_minutes_utc,
                ActivityScheduleEntry.start_minutes_utc <= filters.end_minutes_utc,
            )
        )


def _build_language_conditions(languages: Iterable[str]) -> list:
    """Build language conditions for session-specific languages."""

    return [any_(ActivitySchedule.languages) == language for language in languages]


def _price_sort_key() -> Any:
    """Per-class price with unpriced rows last, so keyset tuples have no NULL."""
    return func.coalesce(class_price_expression(), UNPRICED_SORT_KEY)


def _order_columns(entry_subquery: sa.Subquery, sort: str = "time") -> list:
    """Return ordering columns for pagination."""
    columns = [
        entry_subquery.c.day_of_week_utc,
        entry_subquery.c.start_minutes_utc,
        ActivitySchedule.id,
    ]
    if sort == "price":
        return [_price_sort_key(), *columns]
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
