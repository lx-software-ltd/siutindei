"""Saved Import Settings and post-import Data quality sweeps."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.aws_clients import get_s3_client
from app.services.category_suggestions.events import (
    enqueue_location_batches,
    enqueue_scan_batches,
)
from app.services.category_suggestions.scan import CategoryScanBusy, start_scan
from app.services.location_fix_scan import LocationScanBusy, start_location_scan
from app.services.name_fix_scan import scan_names
from app.services.org_duplicates import (
    invalidate_duplicate_cache,
    list_duplicate_groups,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

QUALITY_KEYS = ("duplicates", "names", "locations", "categories")
SETTINGS_OBJECT_KEY = "admin/settings/import-data-quality.json"


def default_settings() -> dict[str, bool]:
    """All four checks off, matching today's import timing."""
    return {key: False for key in QUALITY_KEYS}


def parse_settings(body: Any) -> dict[str, bool]:
    """Accept a flat object or ``{"data_quality": {...}}``."""
    if not isinstance(body, dict):
        raise ValidationError("Settings must be an object")
    raw = (
        body.get("data_quality") if isinstance(body.get("data_quality"), dict) else body
    )
    parsed = default_settings()
    for key in QUALITY_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, bool):
            raise ValidationError(f"{key} must be a boolean", field=key)
        parsed[key] = value
    return parsed


def load_settings() -> dict[str, bool]:
    """Read saved flags. A missing object or bucket keeps every flag off."""
    bucket = os.getenv("ADMIN_IMPORT_EXPORT_BUCKET", "").strip()
    if not bucket:
        return default_settings()
    try:
        response = get_s3_client().get_object(Bucket=bucket, Key=SETTINGS_OBJECT_KEY)
        payload = json.loads(response["Body"].read().decode("utf-8"))
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return default_settings()
        logger.exception("Import data-quality settings could not be read")
        return default_settings()
    except Exception:
        logger.exception("Import data-quality settings could not be read")
        return default_settings()
    try:
        return parse_settings(payload)
    except ValidationError:
        logger.exception("Import data-quality settings were invalid")
        return default_settings()


def save_settings(body: Any) -> dict[str, bool]:
    """Replace the saved flags on the import/export bucket."""
    parsed = parse_settings(body)
    bucket = os.getenv("ADMIN_IMPORT_EXPORT_BUCKET", "").strip()
    if not bucket:
        raise ValidationError("Import storage is not configured")
    get_s3_client().put_object(
        Bucket=bucket,
        Key=SETTINGS_OBJECT_KEY,
        Body=json.dumps(parsed, ensure_ascii=True).encode("utf-8"),
        ContentType="application/json",
    )
    return parsed


def imported_org_ids(results: list[dict[str, Any]] | None) -> list[str]:
    """Organization ids this import created or updated."""
    ids: list[str] = []
    seen: set[str] = set()
    for row in results or []:
        if row.get("type") != "organizations":
            continue
        if row.get("status") not in {"created", "updated"}:
            continue
        org_id = row.get("id")
        if not org_id or org_id in seen:
            continue
        seen.add(str(org_id))
        ids.append(str(org_id))
    return ids


def run_import_data_quality(
    *,
    results: list[dict[str, Any]] | None,
    requested_by: str | None,
) -> dict[str, Any]:
    """Run the ticked checks. Never raises to the import caller."""
    settings = load_settings()
    skipped = [key for key in QUALITY_KEYS if not settings[key]]
    org_ids = imported_org_ids(results)
    if not any(settings.values()) or not org_ids:
        return {"ran": [], "skipped": list(QUALITY_KEYS), "errors": []}

    ran: list[str] = []
    errors: list[dict[str, str]] = []
    location_batches: list[tuple[str, list]] = []
    category_batches: list[tuple[str, list]] = []
    single_org = _single_org_id(org_ids)

    if settings["duplicates"]:
        _run_check(
            "duplicates",
            ran,
            errors,
            lambda: _with_session(_run_duplicates),
        )
    if settings["names"]:
        _run_check(
            "names",
            ran,
            errors,
            lambda: _with_session(lambda session: _run_names(session, org_ids)),
        )
    if settings["locations"]:
        _run_check(
            "locations",
            ran,
            errors,
            lambda: location_batches.append(
                _with_session(
                    lambda session: _run_locations(session, single_org, requested_by)
                )
            ),
            busy=LocationScanBusy,
        )
    if settings["categories"]:
        _run_check(
            "categories",
            ran,
            errors,
            lambda: category_batches.append(
                _with_session(
                    lambda session: _run_categories(session, single_org, requested_by)
                )
            ),
            busy=CategoryScanBusy,
        )

    for run_id, batches in location_batches:
        if not batches:
            continue
        try:
            enqueue_location_batches(run_id, batches)
        except Exception:
            logger.exception("Import location sweep enqueue failed")
            errors.append({"check": "locations", "error": "enqueue_failed"})
            if "locations" in ran:
                ran.remove("locations")
    for run_id, batches in category_batches:
        if not batches:
            continue
        try:
            enqueue_scan_batches(run_id, batches)
        except Exception:
            logger.exception("Import category check enqueue failed")
            errors.append({"check": "categories", "error": "enqueue_failed"})
            if "categories" in ran:
                ran.remove("categories")

    return {"ran": ran, "skipped": skipped, "errors": errors}


def _with_session(work):
    with Session(get_engine()) as session:
        result = work(session)
        session.commit()
        return result


def _single_org_id(org_ids: list[str]) -> UUID | None:
    if len(org_ids) != 1:
        return None
    try:
        return UUID(org_ids[0])
    except ValueError:
        return None


def _run_check(
    name: str,
    ran: list[str],
    errors: list[dict[str, str]],
    work,
    *,
    busy: type[BaseException] | None = None,
) -> None:
    try:
        work()
    except Exception as exc:
        if busy is not None and isinstance(exc, busy):
            errors.append({"check": name, "error": "busy"})
            return
        logger.exception("Import data-quality %s failed", name)
        errors.append({"check": name, "error": type(exc).__name__})
        return
    ran.append(name)


def _run_duplicates(session: Session) -> None:
    invalidate_duplicate_cache()
    list_duplicate_groups(session)


def _run_names(session: Session, org_ids: list[str]) -> None:
    for raw in org_ids:
        try:
            org_id = UUID(raw)
        except ValueError:
            continue
        scan_names(session, org_id=org_id, review_scope="pending_review")


def _run_locations(
    session: Session,
    org_id: UUID | None,
    requested_by: str | None,
) -> tuple[str, list]:
    payload, batches = start_location_scan(
        session,
        review_scope="pending_review",
        org_id=org_id,
        requested_by=requested_by,
    )
    return payload["scan_run_id"], batches


def _run_categories(
    session: Session,
    org_id: UUID | None,
    requested_by: str | None,
) -> tuple[str, list]:
    body: dict[str, Any] = {"review_scope": "pending_review"}
    if org_id is not None:
        body["org_id"] = str(org_id)
    run, batches = start_scan(session, body, requested_by=requested_by)
    return str(run.id), batches
