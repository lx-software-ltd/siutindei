"""Search rows for approved activities that lack a price or a schedule."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on  # type: ignore[attr-defined]
from sqlalchemy.sql import Select

from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    Location,
    Organization,
)
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.queries import (
    ActivitySearchFilters,
    _apply_entry_filters,
    _build_language_conditions,
    _category_descendant_ids_subquery,
    _text_query_condition,
    applied_search_area_scope,
    area_descendant_ids_subquery,
    validate_filters,
)


def build_incomplete_search_query(
    filters: ActivitySearchFilters,
    *,
    after_activity_id: UUID | None = None,
) -> Select:
    """Approved activities that search would otherwise drop.

    A complete row has a schedule, an entry, an open venue, and a price
    at that venue. This query returns one row per remaining activity of
    an approved organization. The venue is a schedule venue, then a
    priced venue, then a linked venue. ``pricing`` and ``schedule`` are
    null when that piece is missing at the chosen venue.
    """

    validate_filters(filters)
    area_scope = applied_search_area_scope(filters)
    chosen = _chosen_venue_subquery()
    query = (
        select(
            Activity,
            Organization,
            Location,
            ActivityPricing,
            ActivitySchedule,
        )
        .select_from(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .join(chosen, chosen.c.activity_id == Activity.id)
        .join(Location, Location.id == chosen.c.location_id)
        .outerjoin(
            ActivitySchedule,
            and_(
                ActivitySchedule.activity_id == Activity.id,
                ActivitySchedule.location_id == Location.id,
            ),
        )
        .outerjoin(
            ActivityPricing,
            and_(
                ActivityPricing.activity_id == Activity.id,
                ActivityPricing.location_id == Location.id,
            ),
        )
        .where(Organization.review_status == "approved")
        .where(Organization.status.in_(("operational", "closed_temporarily")))
        .where(Location.status.in_(("open", "temporarily_closed")))
        .where(Activity.category_id != PENDING_CATEGORY_ID)
        .where(~_complete_listing_exists())
    )
    needs_entries = (
        filters.day_of_week_utc is not None
        or filters.start_minutes_utc is not None
        or filters.end_minutes_utc is not None
    )
    if needs_entries:
        query = query.join(
            ActivityScheduleEntry,
            ActivityScheduleEntry.schedule_id == ActivitySchedule.id,
        )

    conditions: list = []
    if filters.age is not None:
        conditions.append(Activity.age_range.contains(filters.age))
    if filters.area_id is not None:
        conditions.append(
            Location.area_id.in_(area_descendant_ids_subquery(filters.area_id))
        )
    if filters.category_ids:
        conditions.append(
            Activity.category_id.in_(
                _category_descendant_ids_subquery(filters.category_ids, area_scope)
            )
        )
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
        conditions.append(or_(*_build_language_conditions(filters.languages)))
    if filters.text_query:
        conditions.append(_text_query_condition(filters.text_query))
    if needs_entries:
        _apply_entry_filters(filters, conditions)
    if area_scope is not None:
        if area_scope:
            conditions.append(Location.area_id.in_(tuple(area_scope)))
        else:
            conditions.append(sa.false())
    if after_activity_id is not None:
        conditions.append(Activity.id > after_activity_id)
    if conditions:
        query = query.where(and_(*conditions))
    return (
        query.ext(distinct_on(Activity.id))  # type: ignore[attr-defined]
        .order_by(
            Activity.id,
            ActivitySchedule.id.nulls_last(),
            ActivityPricing.id.nulls_last(),
        )
        .limit(filters.limit)
    )


def _chosen_venue_subquery() -> sa.Subquery:
    """One open venue per activity: schedule, then price, then a link."""

    venues = sa.union_all(
        select(
            ActivitySchedule.activity_id.label("activity_id"),
            ActivitySchedule.location_id.label("location_id"),
            sa.literal(0).label("preference"),
        ),
        select(
            ActivityPricing.activity_id.label("activity_id"),
            ActivityPricing.location_id.label("location_id"),
            sa.literal(1).label("preference"),
        ),
        select(
            ActivityLocation.activity_id.label("activity_id"),
            ActivityLocation.location_id.label("location_id"),
            sa.literal(2).label("preference"),
        ),
    ).subquery("venue_source")
    ranked = (
        select(
            venues.c.activity_id.label("activity_id"),
            venues.c.location_id.label("location_id"),
            func.row_number()
            .over(
                partition_by=venues.c.activity_id,
                order_by=(venues.c.preference, venues.c.location_id),
            )
            .label("venue_rank"),
        )
        .join(Location, Location.id == venues.c.location_id)
        .where(Location.status.in_(("open", "temporarily_closed")))
        .subquery("ranked_venue")
    )
    return (
        select(ranked.c.activity_id, ranked.c.location_id)
        .where(ranked.c.venue_rank == 1)
        .subquery("chosen_venue")
    )


def _complete_listing_exists() -> sa.Exists:
    """True when the activity already has a searchable schedule and price."""

    schedule = sa.orm.aliased(ActivitySchedule)
    entry = sa.orm.aliased(ActivityScheduleEntry)
    venue = sa.orm.aliased(Location)
    price = sa.orm.aliased(ActivityPricing)
    return (
        select(schedule.id)
        .join(entry, entry.schedule_id == schedule.id)
        .join(venue, venue.id == schedule.location_id)
        .join(
            price,
            and_(
                price.activity_id == schedule.activity_id,
                price.location_id == venue.id,
            ),
        )
        .where(schedule.activity_id == Activity.id)
        .where(venue.status.in_(("open", "temporarily_closed")))
        .exists()
    )
