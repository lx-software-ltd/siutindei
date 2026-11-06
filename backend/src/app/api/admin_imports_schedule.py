"""Upsert a weekly schedule during an admin import."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import coerce_uuid
from app.api.admin_imports_lookups import parse_weekly_entries_local
from app.api.admin_imports_utils import parse_timezone, persist_import_change
from app.api.admin_imports_version import (
    hold_existing,
    remember_created,
    restrict_import_body,
    schedule_terminal,
)
from app.api.admin_resource_schedule import _create_schedule, _update_schedule
from app.api.admin_validators import schedule_languages
from app.db.models import Activity, ActivitySchedule, Location
from app.db.repositories import ActivityScheduleRepository
from app.exceptions import ValidationError
from app.services.catalog_version_payload import schedule_payload


def upsert_schedule(
    session: Session,
    activity: Activity,
    location: Location,
    raw_schedule: dict[str, Any],
    warnings: list[str],
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> tuple[ActivitySchedule, str]:
    tzinfo = parse_timezone(raw_schedule.get("timezone"), "timezone")
    languages = schedule_languages(raw_schedule.get("languages"))
    repo = ActivityScheduleRepository(session)
    existing = repo.find_by_activity_location_languages(
        coerce_uuid(activity.id),
        coerce_uuid(location.id),
        languages,
    )
    entries = parse_weekly_entries_local(
        raw_schedule.get("weekly_entries"),
        tzinfo,
        warnings,
    )
    if not entries:
        raise ValidationError(
            "weekly_entries must include at least one entry",
            field="weekly_entries",
        )
    plan = schedule_terminal(
        session,
        activity,
        location,
        existing,
        languages,
        entries,
        allow_updates,
        warnings,
    )
    held = hold_existing(existing, plan, allow_updates)
    if held:
        return held

    body = {
        "activity_id": str(activity.id),
        "location_id": str(location.id),
        "schedule_type": "weekly",
        "languages": languages,
        "weekly_entries": entries,
    }
    restrict_import_body(body, plan)
    if existing:
        updated = _update_schedule(repo, existing, body)
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    created = _create_schedule(repo, body)
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    remember_created(
        session,
        "schedule",
        created.id,
        activity.org_id,
        schedule_payload(created, location),
    )
    return created, "created"
