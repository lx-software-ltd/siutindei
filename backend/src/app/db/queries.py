"""Query builders for search."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from typing import Iterable
from typing import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.sql import Select

from app.db.models import Activity
from app.db.models import ActivityPricing
from app.db.models import ActivitySchedule
from app.db.models import ActivityScheduleEntry
from app.db.models import GeographicArea
from app.db.models import Location
from app.db.models import Organization
from app.db.models import PricingType
from app.db.models import ScheduleType


@dataclass(frozen=True)
class ActivitySearchCursor:
    """Cursor for activity search pagination."""

    day_of_week_utc: int
    start_minutes_utc: int
    schedule_id: UUID


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


def validate_filters(filters: ActivitySearchFilters) -> None:
    """Validate filter combinations for search."""

    if filters.start_minutes_utc is not None and filters.end_minutes_utc is not None:
        if filters.start_minutes_utc >= filters.end_minutes_utc:
            raise ValueError("start_minutes_utc must be less than end_minutes_utc.")

    if filters.limit <= 0 or filters.limit > 200:
        raise ValueError("limit must be between 1 and 200.")


def build_search_query(filters: ActivitySearchFilters) -> Select:
    """Build a SQLAlchemy query for search."""

    validate_filters(filters)

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
        .where(entry_subquery.c.entry_rank == 1)
        .where(Organization.status.in_(("operational", "closed_temporarily")))
    )

    conditions: list = []

    if filters.age is not None:
        conditions.append(Activity.age_range.contains(filters.age))

    if filters.area_id is not None:
        area_ids = _area_descendant_ids_subquery(filters.area_id)
        conditions.append(Location.area_id.in_(area_ids))

    if filters.category_ids:
        conditions.append(Activity.category_id.in_(filters.category_ids))

    if filters.activity_id is not None:
        conditions.append(Activity.id == filters.activity_id)

    if filters.org_ids:
        conditions.append(Activity.org_id.in_(filters.org_ids))

    if filters.pricing_type is not None:
        conditions.append(ActivityPricing.pricing_type == filters.pricing_type)

    if filters.price_min is not None:
        conditions.append(ActivityPricing.amount >= filters.price_min)

    if filters.price_max is not None:
        conditions.append(ActivityPricing.amount <= filters.price_max)

    if filters.schedule_type is not None:
        conditions.append(ActivitySchedule.schedule_type == filters.schedule_type)

    if filters.languages:
        language_conditions = _build_language_conditions(filters.languages)
        conditions.append(or_(*language_conditions))

    order_columns = _order_columns(entry_subquery)
    if filters.cursor is not None:
        cursor_values = _cursor_values(filters.cursor)
        conditions.append(sa.tuple_(*order_columns) > sa.tuple_(*cursor_values))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(*order_columns)
    return query.limit(filters.limit)


def _entry_order_subquery(filters: ActivitySearchFilters) -> sa.Subquery:
    """Build a subquery to order entries per schedule."""
    entry_query = select(
        ActivityScheduleEntry.schedule_id.label("schedule_id"),
        ActivityScheduleEntry.day_of_week_utc.label("day_of_week_utc"),
        ActivityScheduleEntry.start_minutes_utc.label("start_minutes_utc"),
        ActivityScheduleEntry.id.label("entry_id"),
        sa.func.row_number()
        .over(
            partition_by=ActivityScheduleEntry.schedule_id,
            order_by=[
                ActivityScheduleEntry.day_of_week_utc,
                ActivityScheduleEntry.start_minutes_utc,
                ActivityScheduleEntry.id,
            ],
        )
        .label("entry_rank"),
    )
    conditions: list = []
    _apply_entry_filters(filters, conditions)
    if conditions:
        entry_query = entry_query.where(and_(*conditions))
    return entry_query.subquery()


def _apply_entry_filters(filters: ActivitySearchFilters, conditions: list) -> None:
    """Apply entry-level schedule filters."""
    if filters.day_of_week_utc is not None:
        conditions.append(
            ActivityScheduleEntry.day_of_week_utc == filters.day_of_week_utc
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

    return [
        ActivitySchedule.languages.any(language)  # type: ignore[arg-type]
        for language in languages
    ]


def _order_columns(entry_subquery: sa.Subquery) -> list:
    """Return ordering columns for pagination."""
    return [
        entry_subquery.c.day_of_week_utc,
        entry_subquery.c.start_minutes_utc,
        ActivitySchedule.id,
    ]


def _cursor_values(cursor: ActivitySearchCursor) -> list:
    """Return ordering values for the cursor comparison."""
    return [
        cursor.day_of_week_utc,
        cursor.start_minutes_utc,
        cursor.schedule_id,
    ]


def _area_descendant_ids_subquery(area_id: UUID) -> Select[Any]:
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
