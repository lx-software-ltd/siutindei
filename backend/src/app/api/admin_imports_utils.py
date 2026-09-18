"""Shared helpers for admin import/export."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import TypeVar
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.exceptions import ValidationError

T = TypeVar("T")


def persist_import_change(session: Session, *, dry_run: bool) -> None:
    """Flush an upsert; live imports commit once per batch.

    Dry-run flush fires AFTER INSERT/UPDATE audit triggers in the same
    transaction. Those rows are deleted here so a missed rollback cannot
    persist dry-run noise. The handler still rolls back the session.
    """
    session.flush()
    if dry_run:
        _discard_dry_run_audit_rows(session)


def _discard_dry_run_audit_rows(session: Session) -> None:
    """Drop audit_log rows inserted by this dry-run transaction."""
    bind = session.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect != "postgresql":
        return
    session.execute(
        text("DELETE FROM audit_log " "WHERE xmin = pg_current_xact_id()::xid")
    )


def rollback_import_change(session: Session, *, dry_run: bool) -> None:
    """No-op: upserts run inside a SAVEPOINT for both live and dry-run."""
    del session, dry_run


def finish_import_batch(session: Session, *, dry_run: bool) -> None:
    """Commit a live batch after per-row savepoints have succeeded."""
    if not dry_run:
        session.commit()


def run_import_upsert(
    session: Session,
    dry_run: bool,
    fn: Callable[[], T],
) -> T:
    """Run an upsert inside a SAVEPOINT so one bad row stays isolated."""
    del dry_run
    with session.begin_nested():
        return fn()


_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def collect_unknown_fields(
    payload: dict[str, object],
    allowed: set[str],
    path: str,
    warnings: list[str],
) -> None:
    unknown = sorted({key for key in payload.keys() if key not in allowed})
    if unknown:
        warnings.append(f"{path} has unknown fields: {', '.join(unknown)}")


def parse_timezone(value: object, field_name: str) -> ZoneInfo:
    if not value or not isinstance(value, str):
        raise ValidationError("timezone is required", field=field_name)
    name = value.strip()
    if not name:
        raise ValidationError("timezone is required", field=field_name)
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            "timezone must be a valid IANA identifier",
            field=field_name,
        ) from exc


def parse_day_of_week(value: object, field_name: str) -> int:
    if value is None:
        raise ValidationError(f"{field_name} is required", field=field_name)
    try:
        if not isinstance(value, (int, float, str)):
            raise TypeError("invalid day_of_week type")
        day = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
        ) from exc
    if day < 0 or day > 6:
        raise ValidationError(
            f"{field_name} must be between 0 and 6",
            field=field_name,
        )
    return day


def parse_time_minutes(value: object, field_name: str) -> int:
    if value is None:
        raise ValidationError(f"{field_name} is required", field=field_name)
    if isinstance(value, (int, float)):
        minutes = int(value)
    elif isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isdigit():
            minutes = int(trimmed)
        else:
            match = _TIME_RE.match(trimmed)
            if not match:
                raise ValidationError(
                    f"{field_name} must be HH:MM",
                    field=field_name,
                )
            hours = int(match.group(1))
            mins = int(match.group(2))
            minutes = hours * 60 + mins
    else:
        raise ValidationError(
            f"{field_name} must be a string",
            field=field_name,
        )

    if minutes < 0 or minutes > 1439:
        raise ValidationError(
            f"{field_name} must be between 00:00 and 23:59",
            field=field_name,
        )
    return minutes


def to_utc_weekly(
    local_day: int,
    local_start_minutes: int,
    local_end_minutes: int,
    tzinfo: ZoneInfo,
) -> tuple[int, int, int]:
    base = _local_weekday_base(local_day, tzinfo)
    wraps = local_start_minutes > local_end_minutes
    start_local = base + timedelta(minutes=local_start_minutes)
    end_local = base + timedelta(
        days=1 if wraps else 0,
        minutes=local_end_minutes,
    )
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    day_utc = _weekday_to_sunday_index(start_utc.weekday())
    return (
        day_utc,
        start_utc.hour * 60 + start_utc.minute,
        end_utc.hour * 60 + end_utc.minute,
    )


def from_utc_weekly(
    utc_day: int,
    utc_start_minutes: int,
    utc_end_minutes: int,
    tzinfo: ZoneInfo,
) -> tuple[int, int, int]:
    base = _utc_weekday_base(utc_day)
    wraps = utc_start_minutes > utc_end_minutes
    start_utc = base + timedelta(minutes=utc_start_minutes)
    end_utc = base + timedelta(
        days=1 if wraps else 0,
        minutes=utc_end_minutes,
    )
    start_local = start_utc.astimezone(tzinfo)
    end_local = end_utc.astimezone(tzinfo)
    local_day = _weekday_to_sunday_index(start_local.weekday())
    return (
        local_day,
        start_local.hour * 60 + start_local.minute,
        end_local.hour * 60 + end_local.minute,
    )


def format_minutes(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def build_object_key(prefix: str, file_name: str) -> str:
    cleaned = sanitize_filename(file_name)
    base, ext = os.path.splitext(cleaned)
    trimmed_base = base[:40].strip("_") or "file"
    suffix = ext.lower() if ext else ".json"
    unique = uuid4().hex
    return f"{prefix}/{unique}-{trimmed_base}{suffix}"


def sanitize_filename(file_name: str) -> str:
    trimmed = file_name.strip() or "import.json"
    return re.sub(r"[^A-Za-z0-9._-]", "_", trimmed)


def validate_object_key(object_key: str, prefix: str) -> None:
    if not object_key.startswith(f"{prefix}/"):
        raise ValidationError(
            f"object_key must start with {prefix}/",
            field="object_key",
        )
    if object_key.startswith("/") or ".." in object_key:
        raise ValidationError("Invalid object_key path", field="object_key")


def _local_weekday_base(day_of_week: int, tzinfo: ZoneInfo) -> datetime:
    now = datetime.now(tzinfo)
    current_day = _weekday_to_sunday_index(now.weekday())
    delta = day_of_week - current_day
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=delta
    )


def _utc_weekday_base(day_of_week: int) -> datetime:
    now = datetime.now(timezone.utc)
    current_day = _weekday_to_sunday_index(now.weekday())
    delta = day_of_week - current_day
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=delta
    )


def _weekday_to_sunday_index(weekday: int) -> int:
    return (weekday + 1) % 7
