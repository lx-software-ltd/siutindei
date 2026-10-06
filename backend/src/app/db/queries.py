"""Query builders for search."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from typing import Iterable
from typing import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import CompoundSelect

from app.db.models import Activity
from app.db.models import ActivityCategory
from app.db.models import ActivityPricing
from app.db.models import ActivitySchedule
from app.db.models import ActivityScheduleEntry
from app.db.models import GeographicArea
from app.db.models import Location
from app.db.models import Organization
from app.db.models import PricingType
from app.db.models import ScheduleType
from app.db.models.category_suggestion import (
    LEGACY_CATEGORY_IDS,
    PENDING_CATEGORY_ID,
    WIZARD_GROUP_IDS,
)


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
    if review_gate_enabled():
        query = query.where(Organization.review_status == "approved")
    query = query.where(Activity.category_id != PENDING_CATEGORY_ID)

    conditions: list = []

    if filters.age is not None:
        conditions.append(Activity.age_range.contains(filters.age))

    if filters.area_id is not None:
        area_ids = _area_descendant_ids_subquery(filters.area_id)
        conditions.append(Location.area_id.in_(area_ids))

    if filters.category_ids:
        category_ids = _category_descendant_ids_subquery(filters.category_ids)
        conditions.append(Activity.category_id.in_(category_ids))

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


def _wizard_group_filter(category_ids: Sequence[UUID]) -> bool:
    """True when every requested id is one of the seven wizard groups."""
    return bool(category_ids) and all(item in WIZARD_GROUP_IDS for item in category_ids)


def category_match_mode(session: Session, category_ids: Sequence[UUID]) -> str:
    """Return exact, or legacy_fallback while a wizard group is still empty.

    An empty group would otherwise hide every activity that is still on
    Workshop, Class, Outdoor activity, Indoor fun, or Sport.
    """
    if not _wizard_group_filter(category_ids):
        return "exact"
    tree = _category_tree(category_ids)
    assigned = session.scalar(
        select(func.count())
        .select_from(Activity)
        .where(Activity.category_id.in_(select(tree.c.id)))
        .where(Activity.category_id.notin_(tuple(LEGACY_CATEGORY_IDS)))
    )
    return "legacy_fallback" if not assigned else "exact"


def _category_descendant_ids_subquery(
    category_ids: Sequence[UUID],
) -> Select[Any] | CompoundSelect[Any]:
    """Return category ids, including descendants.

    A wizard-group search with no activities on that subtree also
    includes the legacy roots. The union drops out once any activity
    sits on the group or one of its leaves.
    """
    tree = _category_tree(category_ids)
    descendants = select(tree.c.id)
    if not _wizard_group_filter(category_ids):
        return descendants
    assigned = (
        select(Activity.id)
        .where(Activity.category_id.in_(select(tree.c.id)))
        .where(Activity.category_id.notin_(tuple(LEGACY_CATEGORY_IDS)))
        .exists()
    )
    legacy = select(ActivityCategory.id).where(
        ActivityCategory.id.in_(tuple(LEGACY_CATEGORY_IDS)),
        ~assigned,
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


def review_gate_enabled() -> bool:
    """Public search hides unapproved orgs only when this flag is on."""
    raw = os.getenv("ORG_REVIEW_GATE_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}
