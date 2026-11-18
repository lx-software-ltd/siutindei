"""Enum definitions for database models."""

from __future__ import annotations

import enum


class PricingType(enum.StrEnum):
    """Supported pricing types for activities."""

    PER_CLASS = "per_class"
    PER_SESSIONS = "per_sessions"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"
    FREE = "free"
    PER_MONTH = "per_month"
    PER_YEAR = "per_year"


# A free trial class is offered before a class, a term, or a monthly fee.
# Hourly, daily, yearly, and free prices do not store the tick.
FREE_TRIAL_PRICING_TYPES = frozenset(
    {
        PricingType.PER_CLASS,
        PricingType.PER_SESSIONS,
        PricingType.PER_MONTH,
    }
)


class ScheduleType(enum.StrEnum):
    """Supported schedule types for activities."""

    WEEKLY = "weekly"


class TicketType(enum.StrEnum):
    """Discriminator for ticket types."""

    ACCESS_REQUEST = "access_request"
    ORGANIZATION_SUGGESTION = "organization_suggestion"
    ORGANIZATION_FEEDBACK = "organization_feedback"


class TicketStatus(enum.StrEnum):
    """Lifecycle status for tickets."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
