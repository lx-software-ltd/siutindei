"""Import processing for admin import/export."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import (
    MANAGED_BY_PROVIDER,
    NO_MATCH_TO_CLOSE,
    ORG_TRUNCATE_LIMITS,
    apply_vetting_columns,
    prevalidate_activity_categories,
    truncate_import_fields,
)
from app.api.admin_imports_children import process_activity, process_location
from app.api.admin_imports_fields import (
    apply_default_manager_id,
    apply_source_attribution,
    collect_flat_org_warnings,
    expand_board_flat_org,
)
from app.api.admin_imports_results import (
    format_error,
    init_summary,
    record_result,
    record_skipped_children,
)
from app.api.admin_imports_upsert import (
    ALLOWED_ORG_FIELDS,
    upsert_organization,
)
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    finish_import_batch,
    run_import_upsert,
)
from app.api.admin_validators import (
    MAX_NAME_LENGTH,
    _validate_string_length,
)
from app.db.models import Location
from app.exceptions import ValidationError

ALLOWED_ROOT_FIELDS = {"organizations", "default_manager_id"}


def process_import_payload(
    session: Session,
    payload: dict[str, Any],
    file_warnings: list[str],
    dry_run: bool = False,
    allow_org_updates: bool = False,
    catalog_manager_id: str | None = None,
    import_job_id: Any = None,
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
            file_warnings,
            dry_run=dry_run,
            allow_updates=allow_org_updates,
            catalog_manager_id=catalog_manager_id,
            import_job_id=import_job_id,
        )

    finish_import_batch(session, dry_run=dry_run)
    return summary, results


def process_organization(
    session: Session,
    raw_org: Any,
    index: int,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    file_warnings: list[str] | None = None,
    *,
    dry_run: bool = False,
    allow_updates: bool = False,
    catalog_manager_id: str | None = None,
    import_job_id: Any = None,
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
    ignored_review = raw_org.pop("review_status", None)
    if ignored_review not in (None, ""):
        warnings.append(
            f"{path}: review_status is ignored; "
            "release state is managed in the review queue"
        )
    apply_vetting_columns(raw_org)
    truncate_import_fields(raw_org, path, warnings, ORG_TRUNCATE_LIMITS)
    collect_flat_org_warnings(raw_org, path, warnings)
    expand_board_flat_org(raw_org)
    collect_unknown_fields(raw_org, ALLOWED_ORG_FIELDS, path, warnings)
    apply_source_attribution(raw_org)
    if file_warnings is not None:
        file_warnings.extend(warnings)
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
        prevalidate_activity_categories(session, raw_org)
        org, status = run_import_upsert(
            session,
            dry_run,
            lambda: upsert_organization(
                session,
                raw_org,
                dry_run=dry_run,
                allow_updates=allow_updates,
                catalog_manager_id=catalog_manager_id,
                warnings=warnings,
                import_job_id=import_job_id,
            ),
        )
    except ValidationError as exc:
        result_status = (
            "skipped"
            if exc.message in {MANAGED_BY_PROVIDER, NO_MATCH_TO_CLOSE}
            else "failed"
        )
        record_result(
            results,
            summary,
            "organizations",
            org_name or path,
            result_status,
            warnings=warnings,
            errors=[format_error(exc)],
            path=path,
        )
        record_skipped_children(raw_org, org_name or path, results, summary)
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
    if raw_org.get("place_id"):
        results[-1]["place_id"] = raw_org["place_id"]

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
                allow_updates=allow_updates,
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
                allow_updates=allow_updates,
            )
