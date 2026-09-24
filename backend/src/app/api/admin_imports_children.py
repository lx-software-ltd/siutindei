"""Location and activity import processors."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import (
    ACTIVITY_TRUNCATE_LIMITS,
    truncate_import_fields,
)
from app.api.admin_imports_fields import apply_source_attribution
from app.api.admin_imports_items import process_pricing, process_schedule
from app.api.admin_imports_results import (
    format_error,
    record_result,
    record_skipped_children,
)
from app.api.admin_imports_upsert import (
    ALLOWED_ACTIVITY_FIELDS,
    ALLOWED_LOCATION_FIELDS,
    upsert_activity,
    upsert_location,
)
from app.api.admin_imports_venues import resolve_single_imported_venue
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    run_import_upsert,
)
from app.api.admin_validators import (
    MAX_ADDRESS_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
)
from app.db.models import Location, Organization
from app.exceptions import ValidationError


def process_location(
    session: Session,
    org: Organization,
    raw_location: Any,
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
    if not isinstance(raw_location, dict):
        record_result(
            results,
            summary,
            "locations",
            path,
            "failed",
            errors=[{"message": "Location entry must be an object"}],
            path=path,
        )
        return

    warnings: list[str] = []
    collect_unknown_fields(
        raw_location,
        ALLOWED_LOCATION_FIELDS,
        path,
        warnings,
    )

    location_name = _validate_string_length(
        raw_location.get("name") or raw_location.get("address"),
        "name",
        MAX_ADDRESS_LENGTH,
        required=True,
    )
    if location_name is None:
        record_result(
            results,
            summary,
            "locations",
            path,
            "failed",
            warnings=warnings,
            errors=[{"message": "name is required", "field": "name"}],
            path=path,
        )
        return
    address = raw_location.get("address")
    if address is not None:
        address_value = _validate_string_length(
            address,
            "address",
            MAX_ADDRESS_LENGTH,
        )
        if address_value is None:
            address_value = location_name
        if address_value and address_value != location_name:
            raise ValidationError(
                "address must match name for imports",
                field="address",
            )
    else:
        address_value = location_name

    try:
        location, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_location(
                session,
                org,
                raw_location,
                address_value,
                dry_run=dry_run,
                allow_updates=allow_updates,
                warnings=warnings,
            ),
        )
    except ValidationError as exc:
        record_result(
            results,
            summary,
            "locations",
            f"{org.name} / {location_name}",
            "failed",
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        return

    location_cache[location_name] = location
    record_result(
        results,
        summary,
        "locations",
        f"{org.name} / {location_name}",
        status,
        entity_id=str(location.id),
        warnings=warnings,
        path=path,
    )


def process_activity(
    session: Session,
    org: Organization,
    raw_activity: Any,
    index: int,
    location_cache: dict[str, Location],
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    base_path: str,
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
    import_job_id: Any = None,
) -> None:
    path = f"{base_path}[{index}]"
    if not isinstance(raw_activity, dict):
        record_result(
            results,
            summary,
            "activities",
            path,
            "failed",
            errors=[{"message": "Activity entry must be an object"}],
            path=path,
        )
        return

    warnings: list[str] = []
    collect_unknown_fields(
        raw_activity,
        ALLOWED_ACTIVITY_FIELDS,
        path,
        warnings,
    )
    apply_source_attribution(raw_activity)
    truncate_import_fields(
        raw_activity,
        path,
        warnings,
        ACTIVITY_TRUNCATE_LIMITS,
    )
    activity_name = _validate_string_length(
        raw_activity.get("name"),
        "name",
        MAX_NAME_LENGTH,
        required=True,
    )
    if activity_name is None:
        record_result(
            results,
            summary,
            "activities",
            path,
            "failed",
            warnings=warnings,
            errors=[{"message": "name is required", "field": "name"}],
            path=path,
        )
        record_skipped_children(raw_activity, path, results, summary)
        return

    try:
        activity, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_activity(
                session,
                org,
                raw_activity,
                dry_run=dry_run,
                allow_updates=allow_updates,
                venue=resolve_single_imported_venue(location_cache),
                warnings=warnings,
                import_job_id=import_job_id,
            ),
        )
    except ValidationError as exc:
        record_result(
            results,
            summary,
            "activities",
            f"{org.name} / {activity_name}",
            "failed",
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        record_skipped_children(raw_activity, activity_name, results, summary)
        return

    record_result(
        results,
        summary,
        "activities",
        f"{org.name} / {activity_name}",
        status,
        entity_id=str(activity.id),
        warnings=warnings,
        path=path,
    )

    raw_pricing = raw_activity.get("pricing", [])
    if raw_pricing is not None and not isinstance(raw_pricing, list):
        record_result(
            results,
            summary,
            "pricing",
            activity_name,
            "failed",
            errors=[{"message": "pricing must be a list"}],
            path=f"{path}.pricing",
        )
    else:
        for price_index, raw_price in enumerate(raw_pricing or []):
            process_pricing(
                session,
                org,
                activity,
                raw_price,
                price_index,
                location_cache,
                results,
                summary,
                f"{path}.pricing",
                dry_run=dry_run,
                allow_updates=allow_updates,
            )

    raw_schedules = raw_activity.get("schedules", [])
    if raw_schedules is not None and not isinstance(raw_schedules, list):
        record_result(
            results,
            summary,
            "schedules",
            activity_name,
            "failed",
            errors=[{"message": "schedules must be a list"}],
            path=f"{path}.schedules",
        )
    else:
        for sched_index, raw_schedule in enumerate(raw_schedules or []):
            process_schedule(
                session,
                org,
                activity,
                raw_schedule,
                sched_index,
                location_cache,
                results,
                summary,
                f"{path}.schedules",
                dry_run=dry_run,
                allow_updates=allow_updates,
            )
