"""Search rows for approved activities that lack a price or a schedule."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on  # type: ignore[attr-defined]
from sqlalchemy.sql import Select

from app.db.category_visibility import public_category_clause
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
    ActivitySearchCursor,
    ActivitySearchFilters,
    _category_descendant_ids_subquery,
    applied_search_area_scope,
    area_descendant_ids_subquery,
    validate_filters,
)
from app.db.search_conditions import (
    apply_entry_filters,
    build_language_conditions,
    listing_conditions,
    needs_entry_filters,
    needs_price_filters,
    price_conditions,
    text_query_condition,
)


def incomplete_activity_ids_query(filters: ActivitySearchFilters) -> Select:
    """Ids of every approved incomplete activity that matches, unpaged."""

    picked = _picked_incomplete_subquery(filters)
    return select(picked.c.activity_id)


def build_incomplete_search_query(
    filters: ActivitySearchFilters,
    *,
    after: ActivitySearchCursor | None = None,
) -> Select:
    """Approved activities that search would otherwise drop.

    A complete row has a schedule, an entry, an open venue, and a price
    at that venue. This query returns one row per remaining activity of
    an approved organization. The venue is a schedule venue, then a
    priced venue, then a linked venue. ``pricing`` and ``schedule`` are
    null when that piece is missing at the chosen venue.
    """

    picked = _picked_incomplete_subquery(filters)
    paged = select(picked)
    if (
        after is not None
        and after.phase == "incomplete"
        and after.activity_id is not None
        and after.org_name is not None
        and after.activity_name is not None
    ):
        paged = paged.where(
            sa.tuple_(picked.c.org_sort, picked.c.activity_sort, picked.c.activity_id)
            > sa.tuple_(
                func.lower(after.org_name),
                func.lower(after.activity_name),
                sa.literal(after.activity_id),
            )
        )
    paged = paged.order_by(
        picked.c.org_sort, picked.c.activity_sort, picked.c.activity_id
    ).limit(filters.limit)
    page = paged.subquery("incomplete_page")
    return (
        select(Activity, Organization, Location, ActivityPricing, ActivitySchedule)
        .select_from(page)
        .join(Activity, Activity.id == page.c.activity_id)
        .join(Organization, Organization.id == page.c.organization_id)
        .join(Location, Location.id == page.c.location_id)
        .outerjoin(ActivitySchedule, ActivitySchedule.id == page.c.schedule_id)
        .outerjoin(ActivityPricing, ActivityPricing.id == page.c.pricing_id)
        .order_by(page.c.org_sort, page.c.activity_sort, page.c.activity_id)
    )


def _picked_incomplete_subquery(filters: ActivitySearchFilters) -> sa.Subquery:
    """One row per matching incomplete activity at its chosen venue."""

    validate_filters(filters)
    area_scope = applied_search_area_scope(filters)
    chosen = _chosen_venue_subquery(filters, area_scope)
    query = (
        select(
            Activity.id.label("activity_id"),
            Organization.id.label("organization_id"),
            Location.id.label("location_id"),
            ActivitySchedule.id.label("schedule_id"),
            ActivityPricing.id.label("pricing_id"),
            func.lower(Organization.name).label("org_sort"),
            func.lower(Activity.name).label("activity_sort"),
        )
        .select_from(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .join(chosen, chosen.c.activity_id == Activity.id)
        .join(Location, Location.id == chosen.c.location_id)
        .outerjoin(ActivitySchedule, _schedule_at_venue(filters))
        .outerjoin(ActivityPricing, _price_at_venue(filters))
        .where(Organization.review_status == "approved")
        .where(Organization.status.in_(("operational", "closed_temporarily")))
        .where(Location.status.in_(("open", "temporarily_closed")))
        .where(Activity.category_id != PENDING_CATEGORY_ID)
        .where(public_category_clause(Activity.category_id))
        .where(~_complete_listing_exists())
    )
    needs_entries = needs_entry_filters(filters)
    if needs_entries:
        query = query.join(
            ActivityScheduleEntry,
            ActivityScheduleEntry.schedule_id == ActivitySchedule.id,
        )

    conditions: list = listing_conditions(filters)
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
    conditions.extend(price_conditions(filters))
    if filters.schedule_type is not None:
        conditions.append(ActivitySchedule.schedule_type == filters.schedule_type)
    if filters.languages:
        conditions.append(or_(*build_language_conditions(filters.languages)))
    if filters.text_query:
        conditions.append(text_query_condition(filters.text_query))
    if needs_entries:
        apply_entry_filters(filters, conditions)
    if area_scope is not None:
        if area_scope:
            conditions.append(Location.area_id.in_(tuple(area_scope)))
        else:
            conditions.append(sa.false())
    if conditions:
        query = query.where(and_(*conditions))
    return (
        query.ext(distinct_on(Activity.id))  # type: ignore[attr-defined]
        .order_by(
            Activity.id,
            ActivitySchedule.id.nulls_last(),
            ActivityPricing.id.nulls_last(),
        )
        .subquery("one_incomplete")
    )


def _price_at_venue(filters: ActivitySearchFilters):
    """Price row at the chosen venue, limited to an active price filter."""

    match = and_(
        ActivityPricing.activity_id == Activity.id,
        ActivityPricing.location_id == Location.id,
    )
    conditions = price_conditions(filters)
    if conditions:
        match = and_(match, *conditions)
    return match


def _schedule_at_venue(filters: ActivitySearchFilters):
    """Schedule at the chosen venue, limited to an active schedule filter."""

    match = and_(
        ActivitySchedule.activity_id == Activity.id,
        ActivitySchedule.location_id == Location.id,
    )
    if filters.schedule_type is not None:
        match = and_(match, ActivitySchedule.schedule_type == filters.schedule_type)
    if filters.languages:
        match = and_(match, or_(*build_language_conditions(filters.languages)))
    return match


def _chosen_venue_subquery(
    filters: ActivitySearchFilters,
    area_scope: frozenset[UUID] | None,
) -> sa.Subquery:
    """One open venue per activity: schedule, then price, then a link.

    Area, price, and schedule filters apply before the rank, and only
    approved organizations are ranked.
    """

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
        .join(Activity, Activity.id == venues.c.activity_id)
        .join(Organization, Organization.id == Activity.org_id)
        .where(Location.status.in_(("open", "temporarily_closed")))
        .where(Organization.review_status == "approved")
        .where(Organization.status.in_(("operational", "closed_temporarily")))
        .where(Activity.category_id != PENDING_CATEGORY_ID)
        .where(public_category_clause(Activity.category_id))
    )
    ranked = _limit_ranked_venues(ranked, filters, area_scope, venues).subquery(
        "ranked_venue"
    )
    return (
        select(ranked.c.activity_id, ranked.c.location_id)
        .where(ranked.c.venue_rank == 1)
        .subquery("chosen_venue")
    )


def _limit_ranked_venues(ranked, filters, area_scope, venues):
    """Keep venues that can satisfy this request before ranking them."""

    if filters.area_id is not None:
        ranked = ranked.where(
            Location.area_id.in_(area_descendant_ids_subquery(filters.area_id))
        )
    if area_scope is not None:
        if area_scope:
            ranked = ranked.where(Location.area_id.in_(tuple(area_scope)))
        else:
            ranked = ranked.where(sa.false())
    for condition in listing_conditions(filters):
        ranked = ranked.where(condition)
    if filters.category_ids:
        ranked = ranked.where(
            Activity.category_id.in_(
                _category_descendant_ids_subquery(filters.category_ids, area_scope)
            )
        )
    if filters.activity_id is not None:
        ranked = ranked.where(Activity.id == filters.activity_id)
    if filters.org_ids:
        ranked = ranked.where(Activity.org_id.in_(tuple(filters.org_ids)))
    if filters.text_query:
        ranked = ranked.where(text_query_condition(filters.text_query))
    if needs_price_filters(filters):
        ranked = ranked.join(
            ActivityPricing,
            and_(
                ActivityPricing.activity_id == venues.c.activity_id,
                ActivityPricing.location_id == venues.c.location_id,
            ),
        )
        conditions = price_conditions(filters)
        if conditions:
            ranked = ranked.where(and_(*conditions))
    needs_entries = needs_entry_filters(filters)
    needs_schedule = (
        filters.schedule_type is not None or bool(filters.languages) or needs_entries
    )
    if needs_schedule:
        ranked = ranked.join(
            ActivitySchedule,
            and_(
                ActivitySchedule.activity_id == venues.c.activity_id,
                ActivitySchedule.location_id == venues.c.location_id,
            ),
        )
        if filters.schedule_type is not None:
            ranked = ranked.where(
                ActivitySchedule.schedule_type == filters.schedule_type
            )
        if filters.languages:
            ranked = ranked.where(or_(*build_language_conditions(filters.languages)))
        if needs_entries:
            ranked = ranked.join(
                ActivityScheduleEntry,
                ActivityScheduleEntry.schedule_id == ActivitySchedule.id,
            )
            entry_conditions: list = []
            apply_entry_filters(filters, entry_conditions)
            if entry_conditions:
                ranked = ranked.where(and_(*entry_conditions))
    return ranked


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
