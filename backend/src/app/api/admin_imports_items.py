"""Processing helpers for pricing and schedule imports."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_imports_results import format_error, record_result
from app.api.admin_imports_lookups import resolve_location
from app.api.admin_imports_upsert import (
    ALLOWED_PRICING_FIELDS,
    ALLOWED_SCHEDULE_FIELDS,
    upsert_pricing,
    upsert_schedule,
)
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    rollback_import_change,
    run_import_upsert,
)
from app.api.admin_validators import MAX_ADDRESS_LENGTH, _validate_string_length
from app.db.models import Activity, Location, Organization
from app.exceptions import ValidationError


def process_pricing(
    session: Session,
    org: Organization,
    activity: Activity,
    raw_pricing: Any,
    index: int,
    location_cache: dict[str, Location],
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    base_path: str,
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> None:
    path = f"{base_path}[{index}]"
    if not isinstance(raw_pricing, dict):
        record_result(
            results,
            summary,
            "pricing",
            path,
            "failed",
            errors=[{"message": "Pricing entry must be an object"}],
            path=path,
        )
        return

    warnings: list[str] = []
    collect_unknown_fields(raw_pricing, ALLOWED_PRICING_FIELDS, path, warnings)
    location_name = _validate_string_length(
        raw_pricing.get("location_name"),
        "location_name",
        MAX_ADDRESS_LENGTH,
        required=True,
    )
    if location_name is None:
        raise ValidationError("location_name is required", field="location_name")

    location = resolve_location(session, org, location_name, location_cache)
    if location is None:
        record_result(
            results,
            summary,
            "pricing",
            f"{activity.name} / {location_name}",
            "failed",
            warnings=warnings,
            errors=[
                {
                    "message": "location_name not found",
                    "field": "location_name",
                }
            ],
            path=path,
        )
        return

    try:
        pricing, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_pricing(
                session,
                activity,
                location,
                raw_pricing,
                dry_run=dry_run,
                allow_updates=allow_updates,
            ),
        )
    except ValidationError as exc:
        record_result(
            results,
            summary,
            "pricing",
            f"{activity.name} / {location_name}",
            "failed",
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        rollback_import_change(session, dry_run=dry_run)
        return

    record_result(
        results,
        summary,
        "pricing",
        f"{activity.name} / {location_name} / {pricing.pricing_type.value}",
        status,
        entity_id=str(pricing.id),
        warnings=warnings,
        path=path,
    )


def process_schedule(
    session: Session,
    org: Organization,
    activity: Activity,
    raw_schedule: Any,
    index: int,
    location_cache: dict[str, Location],
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    base_path: str,
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> None:
    path = f"{base_path}[{index}]"
    if not isinstance(raw_schedule, dict):
        record_result(
            results,
            summary,
            "schedules",
            path,
            "failed",
            errors=[{"message": "Schedule entry must be an object"}],
            path=path,
        )
        return

    warnings: list[str] = []
    collect_unknown_fields(
        raw_schedule,
        ALLOWED_SCHEDULE_FIELDS,
        path,
        warnings,
    )
    location_name = _validate_string_length(
        raw_schedule.get("location_name"),
        "location_name",
        MAX_ADDRESS_LENGTH,
        required=True,
    )
    if location_name is None:
        raise ValidationError("location_name is required", field="location_name")
    location = resolve_location(session, org, location_name, location_cache)
    if location is None:
        record_result(
            results,
            summary,
            "schedules",
            f"{activity.name} / {location_name}",
            "failed",
            warnings=warnings,
            errors=[
                {
                    "message": "location_name not found",
                    "field": "location_name",
                }
            ],
            path=path,
        )
        return

    try:
        schedule, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_schedule(
                session,
                activity,
                location,
                raw_schedule,
                warnings,
                dry_run=dry_run,
                allow_updates=allow_updates,
            ),
        )
    except ValidationError as exc:
        record_result(
            results,
            summary,
            "schedules",
            f"{activity.name} / {location_name}",
            "failed",
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        rollback_import_change(session, dry_run=dry_run)
        return

    record_result(
        results,
        summary,
        "schedules",
        f"{activity.name} / {location_name}",
        status,
        entity_id=str(schedule.id),
        warnings=warnings,
        path=path,
    )
