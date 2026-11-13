"""Review rules that depend on the listing kind, with their SQL mirrors.

``collect_issues`` in ``org_review.py`` calls the Python rules and
``org_review_sql.py`` counts and filters with the SQL predicates. Each
rule and its predicate must flag the same rows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.age_bounds import inclusive_age_bounds
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    Organization,
)
from app.db.models.enums import PricingType

PRICE_BLOCKER_KINDS = ("class", "camp")
PRICE_WARNING_KINDS = ("preschool",)
SCHEDULE_BLOCKER_KINDS = ("class", "camp")
AGE_CHECKED_KINDS = ("class", "camp")
CATCH_ALL_AGE_MAX = 18
OPENING_HOURS_MIN_DAYS = 6
OPENING_HOURS_MIN_MINUTES = 6 * 60
CLASS_PRICE_TYPES = (PricingType.PER_CLASS, PricingType.PER_HOUR)
CLASS_PRICE_OUTLIER_HKD = Decimal("1500")
VERIFICATION_STALE_DAYS = 365

HOURS_AS_CLASS_TIMES = "hours_as_class_times"
CLASS_PRICE_OUTLIER = "class_price_outlier"
_MINUTES_PER_DAY = 24 * 60

Add = Callable[[str, str, str, str, str], None]
Note = Callable[[], None]


def pricing_severity(kind: str) -> str | None:
    """Severity of a missing price for this kind, or None when not raised."""
    if kind in PRICE_BLOCKER_KINDS:
        return "blocker"
    if kind in PRICE_WARNING_KINDS:
        return "warning"
    return None


def is_catch_all_age(lower: int | None, upper: int | None) -> bool:
    """From birth to adulthood, except the import default, which has its own code."""
    from_birth = lower is None or lower <= 0
    to_adult = upper is None or upper >= CATCH_ALL_AGE_MAX
    import_default = lower == 0 and upper == CATCH_ALL_AGE_MAX
    return from_birth and to_adult and not import_default


def looks_like_opening_hours(entries: Iterable[tuple[int, int, int]]) -> bool:
    """Long sessions on most days of the week are a venue's hours, not classes."""
    long_days = {
        day
        for day, start, end in entries
        if (end - start) % _MINUTES_PER_DAY >= OPENING_HOURS_MIN_MINUTES
    }
    return len(long_days) >= OPENING_HOURS_MIN_DAYS


def is_class_price_outlier(pricing: ActivityPricing) -> bool:
    """A per-class or hourly price this high is usually a term fee."""
    return (
        PricingType(pricing.pricing_type) in CLASS_PRICE_TYPES
        and str(pricing.currency).upper() == "HKD"
        and Decimal(pricing.amount) > CLASS_PRICE_OUTLIER_HKD
    )


def verification_is_stale(organization: Organization, now: datetime) -> bool:
    if not organization.parent_verified:
        return False
    checked = organization.parent_verified_at
    if checked is None:
        return True
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return checked < now - timedelta(days=VERIFICATION_STALE_DAYS)


def load_activity_signals(
    session: Session, activity_ids: list[Any]
) -> dict[str, set[str]]:
    """Per activity, the schedule and price signals the kind rules read."""
    signals: dict[str, set[str]] = defaultdict(set)
    if not activity_ids:
        return signals
    entries: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    rows = session.execute(
        select(
            ActivitySchedule.activity_id,
            ActivityScheduleEntry.day_of_week_utc,
            ActivityScheduleEntry.start_minutes_utc,
            ActivityScheduleEntry.end_minutes_utc,
        )
        .join(
            ActivitySchedule, ActivitySchedule.id == ActivityScheduleEntry.schedule_id
        )
        .where(ActivitySchedule.activity_id.in_(activity_ids))
    ).all()
    for activity_id, day, start, end in rows:
        entries[str(activity_id)].append((day, start, end))
    for activity_id, activity_entries in entries.items():
        if looks_like_opening_hours(activity_entries):
            signals[activity_id].add(HOURS_AS_CLASS_TIMES)
    prices = session.scalars(
        select(ActivityPricing).where(ActivityPricing.activity_id.in_(activity_ids))
    ).all()
    for pricing in prices:
        if is_class_price_outlier(pricing):
            signals[str(pricing.activity_id)].add(CLASS_PRICE_OUTLIER)
    return signals


def note_activity_kind_issues(
    activity: Activity,
    listed: bool,
    pricing_count: int,
    schedule_count: int,
    signals: set[str],
    add: Add,
    note: Note,
) -> None:
    activity_id = str(activity.id)
    kind = activity.kind or "class"
    price_severity = pricing_severity(kind)
    if listed and price_severity:
        note()
        if pricing_count <= 0:
            add(
                "missing_pricing",
                price_severity,
                "activity",
                activity_id,
                "Activity has no price",
            )
    if listed and kind in SCHEDULE_BLOCKER_KINDS:
        note()
        if schedule_count <= 0:
            add(
                "missing_schedule",
                "blocker",
                "activity",
                activity_id,
                "Activity has no schedule",
            )
    if kind in AGE_CHECKED_KINDS:
        note()
        if is_catch_all_age(*inclusive_age_bounds(activity.age_range)):
            add(
                "catch_all_age",
                "warning",
                "activity",
                activity_id,
                "Age range runs from birth to adulthood; set who it suits",
            )
    if kind == "class":
        note()
        if HOURS_AS_CLASS_TIMES in signals:
            add(
                HOURS_AS_CLASS_TIMES,
                "warning",
                "activity",
                activity_id,
                "Weekly times look like opening hours; check the kind",
            )
    note()
    if CLASS_PRICE_OUTLIER in signals:
        add(
            CLASS_PRICE_OUTLIER,
            "warning",
            "activity",
            activity_id,
            f"Price per class or hour is above HK${CLASS_PRICE_OUTLIER_HKD}; "
            "it may be a term fee",
        )


def note_verification(organization: Organization, add: Add, note: Note) -> None:
    note()
    if verification_is_stale(organization, datetime.now(UTC)):
        add(
            "verification_stale",
            "warning",
            "organization",
            str(organization.id),
            "Parent check is over a year old or undated; check again",
        )


def kind_issue_predicates(
    listed: Callable[[Any], ColumnElement[bool]],
) -> dict[str, ColumnElement[bool]]:
    """SQL mirrors of the rules, keyed by issue code.

    ``listed`` is the public-category clause for a category column.
    """
    no_price = (
        ~select(ActivityPricing.id)
        .where(ActivityPricing.activity_id == Activity.id)
        .exists()
    )
    no_schedule = (
        ~select(ActivitySchedule.id)
        .where(ActivitySchedule.activity_id == Activity.id)
        .exists()
    )
    is_listed = listed(Activity.category_id)
    lower = func.lower(Activity.age_range)
    upper = func.upper(Activity.age_range)
    duration = func.mod(
        ActivityScheduleEntry.end_minutes_utc
        - ActivityScheduleEntry.start_minutes_utc
        + _MINUTES_PER_DAY,
        _MINUTES_PER_DAY,
    )
    long_days = (
        select(func.count(func.distinct(ActivityScheduleEntry.day_of_week_utc)))
        .join(
            ActivitySchedule, ActivitySchedule.id == ActivityScheduleEntry.schedule_id
        )
        .where(
            ActivitySchedule.activity_id == Activity.id,
            duration >= OPENING_HOURS_MIN_MINUTES,
        )
        .scalar_subquery()
    )
    outlier_price = (
        select(ActivityPricing.id)
        .where(
            ActivityPricing.activity_id == Activity.id,
            ActivityPricing.pricing_type.in_(CLASS_PRICE_TYPES),
            func.upper(ActivityPricing.currency) == "HKD",
            ActivityPricing.amount > CLASS_PRICE_OUTLIER_HKD,
        )
        .exists()
    )
    stale_before = func.now() - literal(timedelta(days=VERIFICATION_STALE_DAYS))
    return {
        "missing_pricing": _activity_where(
            is_listed,
            no_price,
            Activity.kind.in_((*PRICE_BLOCKER_KINDS, *PRICE_WARNING_KINDS)),
        ),
        "missing_schedule": _activity_where(
            is_listed, no_schedule, Activity.kind.in_(SCHEDULE_BLOCKER_KINDS)
        ),
        "catch_all_age": _activity_where(
            Activity.kind.in_(AGE_CHECKED_KINDS),
            or_(lower.is_(None), lower <= 0),
            or_(upper.is_(None), upper > CATCH_ALL_AGE_MAX),
            ~and_(lower == 0, upper == CATCH_ALL_AGE_MAX + 1),
        ),
        HOURS_AS_CLASS_TIMES: _activity_where(
            Activity.kind == "class", long_days >= OPENING_HOURS_MIN_DAYS
        ),
        CLASS_PRICE_OUTLIER: _activity_where(outlier_price),
        "verification_stale": and_(
            Organization.parent_verified.is_(True),
            or_(
                Organization.parent_verified_at.is_(None),
                Organization.parent_verified_at < stale_before,
            ),
        ),
    }


def missing_pricing_blocker(
    listed: Callable[[Any], ColumnElement[bool]],
) -> ColumnElement[bool]:
    """Only classes and camps block on a missing price."""
    no_price = (
        ~select(ActivityPricing.id)
        .where(ActivityPricing.activity_id == Activity.id)
        .exists()
    )
    return _activity_where(
        listed(Activity.category_id), no_price, Activity.kind.in_(PRICE_BLOCKER_KINDS)
    )


def _activity_where(*conditions: ColumnElement[bool]) -> ColumnElement[bool]:
    return (
        select(Activity.id)
        .where(Activity.org_id == Organization.id, *conditions)
        .exists()
    )
