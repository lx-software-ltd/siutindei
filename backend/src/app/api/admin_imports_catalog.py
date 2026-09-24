"""Catalog-import field parsing, matching, and truncation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.db.models import Organization
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError

ORG_STATUSES = (
    "operational",
    "closed_temporarily",
    "closed_permanently",
    "hidden",
)
PUBLIC_LISTING_STATUSES = ("operational", "closed_temporarily")
STATUS_SOURCES = ("owner", "provider", "places", "importer")
DESCRIPTION_SOURCES = ("template", "official", "places", "enrich")
ORG_SOURCES = ("lcsd", "edb", "swd", "places", "competitor")

MAX_PLACE_ID_LENGTH = 255
MAX_AREA_NAME_LENGTH = 80
MAX_IMPORT_ADDRESS_LENGTH = 300
MAX_IMPORT_DESCRIPTION_LENGTH = 400
MAX_VETTING_NOTE_LENGTH = 500
MAX_WEBSITE_LENGTH = 400
MAX_IMPORT_PHONE_LENGTH = 40
MAX_SOURCE_ID_LENGTH = 80
MANAGED_BY_PROVIDER = "managed by provider"
NO_MATCH_TO_CLOSE = "no matching organization to close"
CATALOG_MANAGER_REQUIRED = "manager_id is not the catalog manager"

_VETTING_PAIR = re.compile(r"([A-Za-z]+)\s*=\s*([^;]+)")


def normalize_org_name(name: str) -> str:
    """Collapse whitespace and compare names case-insensitively."""
    return " ".join(name.split()).casefold()


def parse_vetting_pairs(vetting_note: Any) -> dict[str, str]:
    """Parse ``key=value; key=value`` pairs from a vetting note."""
    if not isinstance(vetting_note, str) or not vetting_note.strip():
        return {}
    pairs: dict[str, str] = {}
    for match in _VETTING_PAIR.finditer(vetting_note):
        pairs[match.group(1)] = match.group(2).strip()
    return pairs


def apply_vetting_columns(raw_org: dict[str, Any]) -> None:
    """Copy source / sourceId / descriptionSource onto org columns."""
    pairs = parse_vetting_pairs(raw_org.get("vetting_note"))
    source = pairs.get("source")
    if source in ORG_SOURCES:
        raw_org["source"] = source
    source_id = pairs.get("sourceId")
    if source_id:
        raw_org["source_id"] = source_id[:MAX_SOURCE_ID_LENGTH]
    description_source = pairs.get("descriptionSource")
    if description_source in DESCRIPTION_SOURCES:
        raw_org["description_source"] = description_source


def apply_zh_translations(record: dict[str, Any]) -> None:
    """Map blank-safe name_zh / description_zh onto `zh` translation keys."""
    name_zh = _optional_text(record.get("name_zh"))
    if name_zh:
        translations = dict(record.get("name_translations") or {})
        translations.setdefault("zh", name_zh)
        record["name_translations"] = translations
    description_zh = _optional_text(record.get("description_zh"))
    if description_zh:
        translations = dict(record.get("description_translations") or {})
        translations.setdefault("zh", description_zh)
        record["description_translations"] = translations


def truncate_import_fields(
    raw: dict[str, Any],
    path: str,
    warnings: list[str],
    limits: dict[str, int],
) -> None:
    """Truncate over-long import strings and record file warnings."""
    for field, max_length in limits.items():
        value = raw.get(field)
        if not isinstance(value, str):
            continue
        if len(value) <= max_length:
            continue
        warnings.append(f"{path}.{field} truncated from {len(value)} to {max_length}")
        raw[field] = value[:max_length]


ORG_TRUNCATE_LIMITS = {
    "name": 200,
    "name_zh": 200,
    "area_name": MAX_AREA_NAME_LENGTH,
    "address": MAX_IMPORT_ADDRESS_LENGTH,
    "description": MAX_IMPORT_DESCRIPTION_LENGTH,
    "description_zh": MAX_IMPORT_DESCRIPTION_LENGTH,
    "vetting_note": MAX_VETTING_NOTE_LENGTH,
    "website": MAX_WEBSITE_LENGTH,
    "source_url": MAX_WEBSITE_LENGTH,
    "phone": MAX_IMPORT_PHONE_LENGTH,
}

ACTIVITY_TRUNCATE_LIMITS = {
    "name": 200,
    "description": MAX_IMPORT_DESCRIPTION_LENGTH,
    "description_zh": MAX_IMPORT_DESCRIPTION_LENGTH,
    "vetting_note": MAX_VETTING_NOTE_LENGTH,
    "source_url": MAX_WEBSITE_LENGTH,
}


def parse_place_id(value: Any) -> str | None:
    """Return a trimmed place_id or None when blank."""
    text = _optional_text(value)
    if not text:
        return None
    if len(text) > MAX_PLACE_ID_LENGTH:
        raise ValidationError(
            f"place_id exceeds {MAX_PLACE_ID_LENGTH} characters",
            field="place_id",
        )
    return text


def parse_org_status(value: Any) -> str | None:
    """Validate an optional organization status."""
    if value is None or value == "":
        return None
    status = str(value).strip()
    if status not in ORG_STATUSES:
        raise ValidationError("Invalid status", field="status")
    return status


def parse_status_source(value: Any) -> str | None:
    """Validate an optional status_source."""
    if value is None or value == "":
        return None
    source = str(value).strip()
    if source not in STATUS_SOURCES:
        raise ValidationError("Invalid status_source", field="status_source")
    return source


def parse_description_source(value: Any) -> str | None:
    """Validate an optional description_source."""
    if value is None or value == "":
        return None
    source = str(value).strip()
    if source not in DESCRIPTION_SOURCES:
        raise ValidationError(
            "Invalid description_source",
            field="description_source",
        )
    return source


def stamp_imported_organization(
    entity: Organization,
    *,
    created: bool,
    import_job_id: Any,
) -> None:
    """Tag a live import. Updates keep review state and the creating job."""
    if created:
        entity.review_status = "pending_review"
        if import_job_id is not None:
            entity.import_job_id = import_job_id
    entity.last_imported_at = datetime.now(timezone.utc)


def apply_listing_status(
    entity: Organization,
    status: str,
    status_source: str,
) -> None:
    """Set listing status and stamp the change metadata.

    ``status_changed_at`` is only written when the status value changes.
    """
    if entity.status == status:
        if not entity.status_source:
            entity.status_source = status_source
        return
    entity.status = status
    entity.status_source = status_source
    entity.status_changed_at = datetime.now(timezone.utc)


def find_import_organization(
    session: Session,
    raw_org: dict[str, Any],
) -> Organization | None:
    """Match an org by place_id, then manager_id + normalised name."""
    repo = OrganizationRepository(session)
    place_id = parse_place_id(raw_org.get("place_id"))
    if place_id:
        found = repo.find_by_place_id(place_id)
        if found is not None:
            return found

    name = _optional_text(raw_org.get("name"))
    manager_id = raw_org.get("manager_id")
    if not name or manager_id in (None, ""):
        return None
    found = repo.find_by_manager_and_name(str(manager_id), name)
    if found is not None:
        return found
    matches = _fallback_name_matches(session, name, manager_id)
    if len(matches) > 1:
        raise MultipleResultsFound("Multiple organizations found")
    if matches:
        return matches[0]
    return None


def find_org_by_place_id(
    session: Session,
    place_id: str,
) -> Organization | None:
    """Find an organization by exact place_id."""
    return OrganizationRepository(session).find_by_place_id(place_id)


def find_org_by_source_id(
    session: Session,
    source_id: str,
) -> Organization | None:
    """Find an organization by parsed source_id."""
    try:
        return OrganizationRepository(session).find_by_source_id(source_id)
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple organizations found",
            field="source_id",
        ) from exc


def _fallback_name_matches(
    session: Session,
    name: str,
    manager_id: Any,
) -> list[Organization]:
    """Match manager+name without PostgreSQL regexp_replace."""
    wanted = normalize_org_name(name)
    manager = str(manager_id).strip().lower()
    rows = (
        session.execute(
            select(Organization).where(
                func.lower(func.trim(Organization.manager_id)) == manager
            )
        )
        .scalars()
        .all()
    )
    return [row for row in rows if normalize_org_name(row.name) == wanted]


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def coerce_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def prevalidate_activity_categories(
    session: Session,
    raw_org: dict[str, Any],
) -> None:
    """Fail the org before insert when a category_name is unknown.

    When capture is on, unknown names are stored later instead of
    failing the organization here.
    """
    from app.services.category_suggestions.resolve import (
        capture_enabled,
        resolve_category_name,
    )

    if capture_enabled(session):
        return
    activities = raw_org.get("activities")
    if not isinstance(activities, list):
        return
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        if activity.get("category_id") not in (None, ""):
            continue
        category_name = activity.get("category_name")
        if category_name in (None, ""):
            continue
        resolve_category_name(session, str(category_name))
