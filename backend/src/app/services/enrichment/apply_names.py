"""Apply an organization name from enrichment while it is under review."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_validators import MAX_NAME_LENGTH, _validate_string_length
from app.db.models.organization import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal
from app.db.repositories.organization import OrganizationRepository
from app.exceptions import ValidationError
from app.services.name_sanitizer import sanitize_name

_REVIEW = "name can change only while the organization is under review"


def apply_name(
    session: Session,
    org: Organization,
    proposal: OrgEnrichmentProposal,
    proposed: dict[str, Any],
) -> None:
    if org.review_status != "pending_review":
        raise ValidationError(_REVIEW, field="name")
    if "name" not in proposed:
        raise ValidationError("proposal has no value", field="name")
    if not _same(org.name, _current(proposal.current_value, "name")):
        raise ValidationError("name changed since the crawl", field="name")
    sanitized = sanitize_name(
        str(proposed.get("name") or ""), org.name_translations
    ).name
    cleaned = _validate_string_length(sanitized, "name", MAX_NAME_LENGTH, required=True)
    if not cleaned:
        raise ValidationError("name is required", field="name")
    other = OrganizationRepository(session).find_by_name_case_insensitive(cleaned)
    if other is not None and str(other.id) != str(org.id):
        raise ValidationError(
            "an organization with this name already exists",
            field="name",
        )
    org.name = cleaned


def apply_name_translation(
    org: Organization,
    proposal: OrgEnrichmentProposal,
    proposed: dict[str, Any],
) -> None:
    if org.review_status != "pending_review":
        raise ValidationError(_REVIEW, field="name")
    if not _same_zh(org, proposal.current_value):
        raise ValidationError("name changed since the crawl", field="name")
    incoming = proposed.get("name_translations")
    zh = incoming.get("zh") if isinstance(incoming, dict) else None
    cleaned = _validate_string_length(zh, "name", MAX_NAME_LENGTH, required=True)
    if not cleaned:
        raise ValidationError("name is required", field="name")
    merged = dict(org.name_translations or {})
    merged["zh"] = cleaned
    org.name_translations = merged


def _current(current: object, field: str) -> object:
    if not isinstance(current, dict):
        return None
    return current.get(field) or None


def _same(stored: object, expected: object) -> bool:
    return (stored or None) == (expected or None)


def _same_zh(org: Organization, current: object) -> bool:
    stored_map = org.name_translations or {}
    stored = stored_map.get("zh") if isinstance(stored_map, dict) else None
    expected = None
    if isinstance(current, dict):
        block = current.get("name_translations") or {}
        if isinstance(block, dict):
            expected = block.get("zh") or None
    return _same(stored, expected)
