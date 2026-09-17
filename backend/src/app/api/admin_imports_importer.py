"""Import processing for admin import/export."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_imports_items import process_pricing, process_schedule
from app.api.admin_imports_results import (
    format_error,
    init_summary,
    record_result,
    record_skipped_children,
)
from app.api.admin_imports_fields import (
    apply_default_manager_id,
    apply_source_attribution,
    collect_flat_org_warnings,
    expand_board_flat_org,
)
from app.api.admin_imports_upsert import (
    ALLOWED_ACTIVITY_FIELDS,
    ALLOWED_LOCATION_FIELDS,
    ALLOWED_ORG_FIELDS,
    upsert_activity,
    upsert_location,
    upsert_organization,
)
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    rollback_import_change,
    run_import_upsert,
)
from app.api.admin_validators import (
    MAX_ADDRESS_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
)
from app.db.models import Location, Organization
from app.exceptions import ValidationError

ALLOWED_ROOT_FIELDS = {"organizations", "default_manager_id"}


def process_import_payload(
    session: Session,
    payload: dict[str, Any],
    file_warnings: list[str],
    dry_run: bool = False,
    allow_org_updates: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    collect_unknown_fields(payload, ALLOWED_ROOT_FIELDS, "root", file_warnings)
    apply_default_manager_id(payload)

    orgs_raw = payload.get("organizations")
    if not isinstance(orgs_raw, list):
        raise ValidationError(
            "organizations must be a list",
            field="organizations",
        )

    results: list[dict[str, Any]] = []
    summary = init_summary()
    summary["warnings"] += len(file_warnings)

    for index, raw_org in enumerate(orgs_raw):
        process_organization(
            session,
            raw_org,
            index,
            results,
            summary,
            dry_run=dry_run,
            allow_updates=allow_org_updates,
        )

    return summary, results


def process_organization(
    session: Session,
    raw_org: Any,
    index: int,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_updates: bool = False,
) -> None:
    path = f"organizations[{index}]"
    if not isinstance(raw_org, dict):
        record_result(
            results,
            summary,
            "organizations",
            path,
            "failed",
            errors=[{"message": "Organization entry must be an object"}],
            path=path,
        )
        return

    warnings: list[str] = []
    collect_flat_org_warnings(raw_org, path, warnings)
    expand_board_flat_org(raw_org)
    collect_unknown_fields(raw_org, ALLOWED_ORG_FIELDS, path, warnings)
    apply_source_attribution(raw_org)
    org_name = _validate_string_length(
        raw_org.get("name"),
        "name",
        MAX_NAME_LENGTH,
        required=True,
    )
    if org_name is None:
        record_result(
            results,
            summary,
            "organizations",
            path,
            "failed",
            warnings=warnings,
            errors=[{"message": "name is required", "field": "name"}],
            path=path,
        )
        record_skipped_children(raw_org, path, results, summary)
        return

    try:
        org, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_organization(
                session,
                raw_org,
                dry_run=dry_run,
                allow_updates=allow_updates,
            ),
        )
    except ValidationError as exc:
        record_result(
            results,
            summary,
            "organizations",
            org_name or path,
            "failed",
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        record_skipped_children(raw_org, org_name or path, results, summary)
        rollback_import_change(session, dry_run=dry_run)
        return

    record_result(
        results,
        summary,
        "organizations",
        org_name,
        status,
        entity_id=str(org.id),
        warnings=warnings,
        path=path,
    )

    location_cache: dict[str, Location] = {}
    raw_locations = raw_org.get("locations", [])
    if raw_locations is not None and not isinstance(raw_locations, list):
        record_result(
            results,
            summary,
            "locations",
            org_name,
            "failed",
            errors=[{"message": "locations must be a list"}],
            path=f"{path}.locations",
        )
    else:
        for loc_index, raw_location in enumerate(raw_locations or []):
            process_location(
                session,
                org,
                raw_location,
                loc_index,
                location_cache,
                results,
                summary,
                f"{path}.locations",
                dry_run=dry_run,
            )

    raw_activities = raw_org.get("activities", [])
    if raw_activities is not None and not isinstance(raw_activities, list):
        record_result(
            results,
            summary,
            "activities",
            org_name,
            "failed",
            errors=[{"message": "activities must be a list"}],
            path=f"{path}.activities",
        )
    else:
        for act_index, raw_activity in enumerate(raw_activities or []):
            process_activity(
                session,
                org,
                raw_activity,
                act_index,
                location_cache,
                results,
                summary,
                f"{path}.activities",
                dry_run=dry_run,
            )


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
        address_value = _validate_string_length(address, "address", MAX_ADDRESS_LENGTH)
        if address_value is None:
            address_value = location_name
        if address_value and address_value != location_name:
            raise ValidationError(
                "address must match name for imports", field="address"
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
        rollback_import_change(session, dry_run=dry_run)
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
        rollback_import_change(session, dry_run=dry_run)
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
            )
