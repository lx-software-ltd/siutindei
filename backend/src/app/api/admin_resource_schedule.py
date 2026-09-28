"""Schedule resource handlers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_request import _parse_uuid
from app.api.admin_validators import _parse_languages
from app.db.models import (
    ActivitySchedule,
    ActivityScheduleEntry,
    ScheduleType,
)
from app.db.repositories import ActivityScheduleRepository
from app.exceptions import ValidationError


def _create_schedule(
    repo: ActivityScheduleRepository, body: dict[str, Any]
) -> ActivitySchedule:
    """Create activity schedule."""
    activity_id = body.get("activity_id")
    location_id = body.get("location_id")
    schedule_type = body.get("schedule_type", ScheduleType.WEEKLY.value)
    if not activity_id or not location_id:
        raise ValidationError("activity_id and location_id are required")
    if schedule_type != ScheduleType.WEEKLY.value:
        raise ValidationError("schedule_type must be weekly", field="schedule_type")

    schedule = ActivitySchedule(
        activity_id=_parse_uuid(activity_id),
        location_id=_parse_uuid(location_id),
        schedule_type=ScheduleType.WEEKLY,
        languages=_parse_languages(body.get("languages")),
        entries=_parse_weekly_entries(body.get("weekly_entries")),
    )
    _validate_schedule(schedule)
    _ensure_unique_schedule(repo, schedule, current_id=None)
    return schedule


def _update_schedule(
    repo: ActivityScheduleRepository,
    entity: ActivitySchedule,
    body: dict[str, Any],
) -> ActivitySchedule:
    """Update activity schedule."""
    if "schedule_type" in body:
        schedule_type = body["schedule_type"]
        if schedule_type != ScheduleType.WEEKLY.value:
            raise ValidationError(
                "schedule_type must be weekly",
                field="schedule_type",
            )
        entity.schedule_type = ScheduleType.WEEKLY
    if "languages" in body:
        entity.languages = _parse_languages(body["languages"])
    if "weekly_entries" in body:
        parsed_entries = _parse_weekly_entries(body.get("weekly_entries"))
        _sync_weekly_entries(repo.session, entity, parsed_entries)
    _validate_schedule(entity)
    _ensure_unique_schedule(repo, entity, current_id=entity.id)
    return entity


def _serialize_schedule(entity: ActivitySchedule) -> dict[str, Any]:
    """Serialize schedule."""
    entries = sorted(entity.entries, key=_entry_sort_key)
    return {
        "id": str(entity.id),
        "activity_id": str(entity.activity_id),
        "location_id": str(entity.location_id),
        "schedule_type": entity.schedule_type.value,
        "weekly_entries": [
            {
                "day_of_week_utc": entry.day_of_week_utc,
                "start_minutes_utc": entry.start_minutes_utc,
                "end_minutes_utc": entry.end_minutes_utc,
            }
            for entry in entries
        ],
        "languages": entity.languages,
    }


def _parse_weekly_entries(value: Any) -> list[ActivityScheduleEntry]:
    """Parse weekly entries from request body."""
    if value is None:
        raise ValidationError(
            "weekly_entries is required",
            field="weekly_entries",
        )
    if not isinstance(value, list):
        raise ValidationError(
            "weekly_entries must be a list",
            field="weekly_entries",
        )
    if not value:
        raise ValidationError(
            "weekly_entries must include at least one entry",
            field="weekly_entries",
        )

    entries: list[ActivityScheduleEntry] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValidationError(
                "weekly_entries must be objects",
                field=f"weekly_entries[{index}]",
            )
        day_of_week = _parse_int_field(
            raw.get("day_of_week_utc"),
            f"weekly_entries[{index}].day_of_week_utc",
        )
        start_minutes = _parse_int_field(
            raw.get("start_minutes_utc"),
            f"weekly_entries[{index}].start_minutes_utc",
        )
        end_minutes = _parse_int_field(
            raw.get("end_minutes_utc"),
            f"weekly_entries[{index}].end_minutes_utc",
        )
        entries.append(
            ActivityScheduleEntry(
                day_of_week_utc=day_of_week,
                start_minutes_utc=start_minutes,
                end_minutes_utc=end_minutes,
            )
        )
    return entries


def _parse_int_field(value: Any, field_name: str) -> int:
    """Parse required integer fields."""
    if value is None:
        raise ValidationError(f"{field_name} is required", field=field_name)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
        ) from exc


def _validate_schedule(schedule: ActivitySchedule) -> None:
    """Validate schedule fields for weekly schedules."""
    if schedule.schedule_type != ScheduleType.WEEKLY:
        raise ValidationError("schedule_type must be weekly", field="schedule_type")

    if not schedule.entries:
        raise ValidationError(
            "weekly_entries are required",
            field="weekly_entries",
        )

    seen: set[tuple[int, int, int]] = set()
    for index, entry in enumerate(schedule.entries):
        field_prefix = f"weekly_entries[{index}]"
        _validate_entry(entry, field_prefix)
        key = (
            entry.day_of_week_utc,
            entry.start_minutes_utc,
            entry.end_minutes_utc,
        )
        if key in seen:
            raise ValidationError(
                "weekly_entries must not contain duplicates",
                field=field_prefix,
            )
        seen.add(key)


def _validate_entry(entry: ActivityScheduleEntry, field_prefix: str) -> None:
    """Validate a weekly entry."""
    day_of_week = entry.day_of_week_utc
    if not 0 <= day_of_week <= 6:
        raise ValidationError(
            "day_of_week_utc must be between 0 and 6",
            field=f"{field_prefix}.day_of_week_utc",
        )

    start_minutes = entry.start_minutes_utc
    if not 0 <= start_minutes <= 1439:
        raise ValidationError(
            "start_minutes_utc must be between 0 and 1439",
            field=f"{field_prefix}.start_minutes_utc",
        )

    end_minutes = entry.end_minutes_utc
    if not 0 <= end_minutes <= 1439:
        raise ValidationError(
            "end_minutes_utc must be between 0 and 1439",
            field=f"{field_prefix}.end_minutes_utc",
        )

    if start_minutes == end_minutes:
        raise ValidationError(
            "start_minutes_utc must not equal end_minutes_utc",
            field=f"{field_prefix}.start_minutes_utc",
        )


def _entry_sort_key(entry: ActivityScheduleEntry) -> tuple[int, int, int]:
    """Sort key for schedule entries."""
    return (
        entry.day_of_week_utc,
        entry.start_minutes_utc,
        entry.end_minutes_utc,
    )


def _weekly_entry_key(
    entry: ActivityScheduleEntry,
) -> tuple[int, int, int]:
    """Unique slot key for a weekly entry."""
    return (
        entry.day_of_week_utc,
        entry.start_minutes_utc,
        entry.end_minutes_utc,
    )


def _sync_weekly_entries(
    session: Session,
    schedule: ActivitySchedule,
    desired: list[ActivityScheduleEntry],
) -> None:
    """Replace weekly entries while preserving ids for unchanged slots."""
    desired_keys = {_weekly_entry_key(entry) for entry in desired}
    existing_by_key = {
        _weekly_entry_key(entry): entry for entry in list(schedule.entries or [])
    }

    for entry in list(schedule.entries or []):
        if _weekly_entry_key(entry) not in desired_keys:
            schedule.entries.remove(entry)

    session.flush()

    synced: list[ActivityScheduleEntry] = []
    for entry in desired:
        key = _weekly_entry_key(entry)
        if key in existing_by_key:
            synced.append(existing_by_key[key])
        else:
            synced.append(entry)
    schedule.entries[:] = synced


def _ensure_unique_schedule(
    repo: ActivityScheduleRepository,
    schedule: ActivitySchedule,
    current_id: str | None,
) -> None:
    """Ensure schedule uniqueness by activity, location, and languages."""
    existing = repo.find_by_activity_location_languages(
        _coerce_uuid(schedule.activity_id),
        _coerce_uuid(schedule.location_id),
        schedule.languages,
    )
    if existing is None:
        return
    if current_id is not None and str(existing.id) == str(current_id):
        return
    raise ValidationError(
        "Schedule already exists for activity, location, and languages",
        field="languages",
    )


def _coerce_uuid(value: str | UUID) -> UUID:
    """Return a UUID instance from a string or UUID value."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
