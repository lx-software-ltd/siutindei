"""Tests for activity schedule validation logic."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.api.admin_resource_schedule import _validate_schedule  # noqa: E402
from app.db.models import (  # noqa: E402
    ActivitySchedule,
    ActivityScheduleEntry,
    ScheduleType,
)
from app.exceptions import ValidationError  # noqa: E402


def make_weekly_schedule(
    day_of_week_utc: int = 1,
    start_minutes_utc: int = 600,
    end_minutes_utc: int = 660,
) -> ActivitySchedule:
    """Create a weekly schedule for testing."""
    schedule = ActivitySchedule(
        activity_id=uuid4(),
        location_id=uuid4(),
        schedule_type=ScheduleType.WEEKLY,
        languages=["en"],
    )
    schedule.entries = [
        ActivityScheduleEntry(
            day_of_week_utc=day_of_week_utc,
            start_minutes_utc=start_minutes_utc,
            end_minutes_utc=end_minutes_utc,
        )
    ]
    return schedule


class TestValidateScheduleWeekly:
    """Tests for weekly schedule validation."""

    def test_valid_weekly_schedule(self) -> None:
        """Valid weekly schedule should pass validation."""
        schedule = make_weekly_schedule(
            day_of_week_utc=0,  # Sunday
            start_minutes_utc=0,
            end_minutes_utc=1439,
        )
        _validate_schedule(schedule)  # Should not raise

    def test_day_of_week_utc_below_range(self) -> None:
        """day_of_week_utc below 0 should raise ValidationError."""
        schedule = make_weekly_schedule(day_of_week_utc=-1)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "day_of_week_utc must be between 0 and 6" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].day_of_week_utc"

    def test_day_of_week_utc_above_range(self) -> None:
        """day_of_week_utc above 6 should raise ValidationError."""
        schedule = make_weekly_schedule(day_of_week_utc=7)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "day_of_week_utc must be between 0 and 6" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].day_of_week_utc"

    def test_start_minutes_utc_below_range(self) -> None:
        """start_minutes_utc below 0 should raise ValidationError."""
        schedule = make_weekly_schedule(start_minutes_utc=-1)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "start_minutes_utc must be between 0 and 1439" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].start_minutes_utc"

    def test_start_minutes_utc_above_range(self) -> None:
        """start_minutes_utc above 1439 should raise ValidationError."""
        schedule = make_weekly_schedule(start_minutes_utc=1440)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "start_minutes_utc must be between 0 and 1439" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].start_minutes_utc"

    def test_end_minutes_utc_below_range(self) -> None:
        """end_minutes_utc below 0 should raise ValidationError."""
        schedule = make_weekly_schedule(end_minutes_utc=-1)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "end_minutes_utc must be between 0 and 1439" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].end_minutes_utc"

    def test_end_minutes_utc_above_range(self) -> None:
        """end_minutes_utc above 1439 should raise ValidationError."""
        schedule = make_weekly_schedule(end_minutes_utc=2000)
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "end_minutes_utc must be between 0 and 1439" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].end_minutes_utc"

    def test_start_minutes_utc_equals_end_minutes_utc(self) -> None:
        """start_minutes_utc equal to end_minutes_utc should raise ValidationError."""
        schedule = make_weekly_schedule(
            start_minutes_utc=600,
            end_minutes_utc=600,
        )
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "start_minutes_utc must not equal end_minutes_utc" in str(exc_info.value)
        assert exc_info.value.field == "weekly_entries[0].start_minutes_utc"

    def test_start_minutes_utc_greater_than_end_minutes_utc(self) -> None:
        """start_minutes_utc greater than end_minutes_utc should be valid."""
        schedule = make_weekly_schedule(
            start_minutes_utc=700,
            end_minutes_utc=600,
        )
        _validate_schedule(schedule)  # Should not raise


class TestValidateScheduleBoundaryValues:
    """Tests for boundary values."""

    @pytest.mark.parametrize("day_of_week", [0, 1, 2, 3, 4, 5, 6])
    def test_all_valid_days_of_week(self, day_of_week: int) -> None:
        """All days 0-6 should be valid."""
        schedule = make_weekly_schedule(day_of_week_utc=day_of_week)
        _validate_schedule(schedule)  # Should not raise

    def test_minimum_minutes_values(self) -> None:
        """Minimum minute values (0, 1) should be valid."""
        schedule = make_weekly_schedule(start_minutes_utc=0, end_minutes_utc=1)
        _validate_schedule(schedule)  # Should not raise

    def test_maximum_minutes_values(self) -> None:
        """Maximum minute values (1438, 1439) should be valid."""
        schedule = make_weekly_schedule(start_minutes_utc=1438, end_minutes_utc=1439)
        _validate_schedule(schedule)  # Should not raise


class TestValidateScheduleEntries:
    """Tests for weekly entry validation."""

    def test_missing_entries(self) -> None:
        """Missing entries should raise ValidationError."""
        schedule = ActivitySchedule(
            activity_id=uuid4(),
            location_id=uuid4(),
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
        )
        schedule.entries = []
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "weekly_entries are required" in str(exc_info.value)

    def test_duplicate_entries(self) -> None:
        """Duplicate entries should raise ValidationError."""
        schedule = ActivitySchedule(
            activity_id=uuid4(),
            location_id=uuid4(),
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
        )
        schedule.entries = [
            ActivityScheduleEntry(
                day_of_week_utc=1,
                start_minutes_utc=600,
                end_minutes_utc=660,
            ),
            ActivityScheduleEntry(
                day_of_week_utc=1,
                start_minutes_utc=600,
                end_minutes_utc=660,
            ),
        ]
        with pytest.raises(ValidationError) as exc_info:
            _validate_schedule(schedule)
        assert "must not contain duplicates" in str(exc_info.value)
