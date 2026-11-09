"""Repository for ActivitySchedule entities."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import any_, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ActivitySchedule,
    ActivityScheduleEntry,
    ScheduleType,
)
from app.db.repositories.base import BaseRepository


class ActivityScheduleRepository(BaseRepository[ActivitySchedule]):
    """Repository for ActivitySchedule CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, ActivitySchedule)

    def find_by_activity(
        self,
        activity_id: UUID,
        limit: int = 50,
    ) -> Sequence[ActivitySchedule]:
        """Find all schedules for an activity.

        Args:
            activity_id: The activity UUID.
            limit: Maximum results to return.

        Returns:
            Schedules for the activity.
        """
        query = (
            select(ActivitySchedule)
            .where(ActivitySchedule.activity_id == activity_id)
            .order_by(ActivitySchedule.id)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def find_by_location(
        self,
        location_id: UUID,
        limit: int = 50,
    ) -> Sequence[ActivitySchedule]:
        """Find all schedules at a location.

        Args:
            location_id: The location UUID.
            limit: Maximum results to return.

        Returns:
            Schedules at the location.
        """
        query = (
            select(ActivitySchedule)
            .where(ActivitySchedule.location_id == location_id)
            .order_by(ActivitySchedule.id)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def find_weekly_by_day(
        self,
        day_of_week_utc: int,
        limit: int = 50,
    ) -> Sequence[ActivitySchedule]:
        """Find weekly schedules for a specific day.

        Args:
            day_of_week_utc: Day of week (0=Sunday, 6=Saturday).
            limit: Maximum results to return.

        Returns:
            Weekly schedules on the specified day.
        """
        query = (
            select(ActivitySchedule)
            .join(
                ActivityScheduleEntry,
                ActivityScheduleEntry.schedule_id == ActivitySchedule.id,
            )
            .where(ActivityScheduleEntry.day_of_week_utc == day_of_week_utc)
            .group_by(ActivitySchedule.id)
            .order_by(func.min(ActivityScheduleEntry.start_minutes_utc))
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def find_by_language(
        self,
        language: str,
        limit: int = 50,
    ) -> Sequence[ActivitySchedule]:
        """Find schedules offering a specific language.

        Args:
            language: Language code.
            limit: Maximum results to return.

        Returns:
            Schedules offering the language.
        """
        query = (
            select(ActivitySchedule)
            .where(any_(ActivitySchedule.languages) == language)
            .order_by(ActivitySchedule.id)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def create_weekly_schedule(
        self,
        activity_id: UUID,
        location_id: UUID,
        day_of_week_utc: int,
        start_minutes_utc: int,
        end_minutes_utc: int,
        languages: list[str] | None = None,
    ) -> ActivitySchedule:
        """Create a weekly schedule with a single entry.

        Args:
            activity_id: Activity UUID.
            location_id: Location UUID.
            day_of_week_utc: Day of week (0=Sunday, 6=Saturday).
            start_minutes_utc: Start time in minutes from midnight UTC.
            end_minutes_utc: End time in minutes from midnight UTC.
            languages: Optional list of language codes.

        Returns:
            The created schedule.
        """
        schedule = ActivitySchedule(
            activity_id=activity_id,
            location_id=location_id,
            schedule_type=ScheduleType.WEEKLY,
            languages=languages or [],
        )
        schedule.entries.append(
            ActivityScheduleEntry(
                day_of_week_utc=day_of_week_utc,
                start_minutes_utc=start_minutes_utc,
                end_minutes_utc=end_minutes_utc,
            )
        )
        return self.create(schedule)

    def find_by_activity_location_languages(
        self,
        activity_id: UUID,
        location_id: UUID,
        languages: list[str],
    ) -> ActivitySchedule | None:
        """Find a schedule by activity, location, and language set."""
        query = (
            select(ActivitySchedule)
            .where(ActivitySchedule.activity_id == activity_id)
            .where(ActivitySchedule.location_id == location_id)
            .where(ActivitySchedule.languages == languages)
        )
        return self._session.execute(query).scalars().first()
