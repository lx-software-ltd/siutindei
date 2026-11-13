"""Filter conditions and sort keys shared by the search queries."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import and_, any_, func, or_

from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    Organization,
    PricingType,
)
from app.services.data_quality.list_params import ilike_pattern

if TYPE_CHECKING:
    from app.db.queries import ActivitySearchFilters

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


def listing_conditions(filters: ActivitySearchFilters) -> list:
    """Age, kind, and parent-verified filters on the activity and its organiser.

    ``age_min`` and ``age_max`` match any activity whose age range
    overlaps theirs. A missing bound is open.
    """
    conditions: list = []
    if filters.age is not None:
        conditions.append(Activity.age_range.contains(filters.age))
    if filters.age_min is not None or filters.age_max is not None:
        wanted = func.int4range(
            sa.literal(filters.age_min, sa.Integer),
            sa.literal(filters.age_max, sa.Integer),
            "[]",
        )
        conditions.append(Activity.age_range.op("&&")(wanted))
    if filters.kinds:
        conditions.append(Activity.kind.in_(tuple(filters.kinds)))
    if filters.verified_only:
        conditions.append(Organization.parent_verified.is_(True))
    return conditions


def text_query_condition(text_query: str) -> Any:
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


def apply_entry_filters(filters: ActivitySearchFilters, conditions: list) -> None:
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


def build_language_conditions(languages: Iterable[str]) -> list:
    """Build language conditions for session-specific languages."""

    return [any_(ActivitySchedule.languages) == language for language in languages]


def price_sort_key() -> Any:
    """Per-class price with unpriced rows last, so keyset tuples have no NULL."""
    return func.coalesce(class_price_expression(), UNPRICED_SORT_KEY)
