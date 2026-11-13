"""Dates on a schedule: parsing, pairing, and weekday checks.

A dated schedule is one session of a camp or workshop. Both dates are
Hong Kong calendar days and both are set or both are empty.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.db.search_conditions import hong_kong_day
from app.exceptions import ValidationError

HONG_KONG = ZoneInfo("Asia/Hong_Kong")
SCHEDULE_DATE_FIELDS = ("starts_on", "ends_on")


def hong_kong_today() -> date:
    """Today's date on the Hong Kong calendar."""
    return datetime.now(HONG_KONG).date()


def parse_schedule_date(value: Any, field: str) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` date, or None for an empty value."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a YYYY-MM-DD date", field=field)
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValidationError(
            f"{field} must be a YYYY-MM-DD date", field=field
        ) from exc


def hong_kong_weekdays_between(starts_on: date, ends_on: date) -> set[int]:
    """Weekdays (0 = Sunday) that fall between two dates, inclusive."""
    days: set[int] = set()
    current = starts_on
    while current <= ends_on and len(days) < 7:
        days.add((current.weekday() + 1) % 7)
        current += timedelta(days=1)
    return days


def validate_schedule_dates(
    starts_on: date | None,
    ends_on: date | None,
    entries: Iterable[Any],
    *,
    field_prefix: str = "",
) -> None:
    """Check the date pair and that every entry's weekday occurs in it."""
    if starts_on is None and ends_on is None:
        return
    if starts_on is None:
        raise ValidationError(
            "starts_on is required when ends_on is set",
            field=f"{field_prefix}starts_on",
        )
    if ends_on is None:
        raise ValidationError(
            "ends_on is required when starts_on is set",
            field=f"{field_prefix}ends_on",
        )
    if ends_on < starts_on:
        raise ValidationError(
            "ends_on must not be before starts_on",
            field=f"{field_prefix}ends_on",
        )
    weekdays = hong_kong_weekdays_between(starts_on, ends_on)
    for index, entry in enumerate(entries):
        day = hong_kong_day(entry.day_of_week_utc, entry.start_minutes_utc)
        if day not in weekdays:
            raise ValidationError(
                "weekly_entries has a day that does not occur between "
                "starts_on and ends_on",
                field=f"{field_prefix}weekly_entries[{index}]",
            )


def format_schedule_date(value: date | None) -> str | None:
    """ISO date string, or None."""
    return value.isoformat() if value is not None else None
