"""Apply deterministic name cleanup while an import is written."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import (
    MAX_VETTING_NOTE_LENGTH,
    coerce_uuid,
    find_import_organization,
)
from app.db.models import Organization
from app.db.repositories import ActivityRepository, OrganizationRepository
from app.exceptions import ValidationError
from app.services.name_fixes import load_name_fix_config
from app.services.name_sanitizer import sanitize_name

_IMPORTED_NAME = "Imported name: "


def prepare_imported_organization(
    session: Session,
    repo: OrganizationRepository,
    raw_org: dict[str, Any],
    name: str,
    body: dict[str, Any],
    warnings: list[str] | None,
) -> Organization | None:
    """Find the organization and store a cleaned name on the upsert body."""
    try:
        existing = find_import_organization(session, raw_org)
        if existing is None:
            existing = repo.find_by_name_case_insensitive(name)
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple organizations found",
            field="name",
        ) from exc
    return _store_cleaned_name(
        session,
        existing,
        name,
        body,
        warnings,
        lambda candidate: repo.find_by_name_case_insensitive(candidate),
    )


def find_cleaned_activity(
    session: Session,
    repo: ActivityRepository,
    org: Organization,
    name: str,
):
    """Find an activity by its cleaned name when the raw name missed.

    Used only when the import is leaving existing rows unchanged. An
    approved organization does not clean activity names on the way in,
    so a later file can still carry the spelling from before a name fix.
    """
    if org.review_status == "pending_review":
        return None
    result = sanitize_name(name, {}, load_name_fix_config(session))
    if result.name.casefold() == name.casefold():
        return None
    return repo.find_by_org_and_name_case_insensitive(coerce_uuid(org.id), result.name)


def prepare_imported_activity(
    session: Session,
    repo: ActivityRepository,
    org: Organization,
    name: str,
    body: dict[str, Any],
    warnings: list[str] | None,
):
    """Clean an activity name when its organization is still pending review."""

    def find(candidate: str):
        return repo.find_by_org_and_name_case_insensitive(
            coerce_uuid(org.id), candidate
        )

    try:
        existing = find(name)
    except MultipleResultsFound as exc:
        raise ValidationError("Multiple activities found", field="name") from exc
    if org.review_status != "pending_review":
        body["name"] = name
        return existing
    return _store_cleaned_name(session, existing, name, body, warnings, find)


def _store_cleaned_name(session, existing, name, body, warnings, find_name):
    result = sanitize_name(
        name,
        body.get("name_translations") or {},
        load_name_fix_config(session),
    )
    chosen = result.name
    matched = None
    if chosen.casefold() != name.casefold():
        try:
            matched = find_name(chosen)
        except MultipleResultsFound as exc:
            raise ValidationError("Multiple records found", field="name") from exc
    if matched is not None and (
        existing is None or str(matched.id) != str(existing.id)
    ):
        if existing is None:
            existing = matched
        else:
            if warnings is not None:
                warnings.append(
                    "Sanitized name matches another record; original name kept"
                )
            body["name"] = name
            return existing
    body["name"] = chosen
    if chosen != name or result.translation_patch:
        _merge_translations(body, result.translation_patch)
        if chosen != name:
            body["source_note"] = append_imported_name(body.get("source_note"), name)
    return existing


def append_imported_name(note: str | None, original: str) -> str:
    """Keep the imported spelling in the vetting note."""
    marker = f"{_IMPORTED_NAME}{original.strip()}"
    current = (note or "").strip()
    if marker in current:
        return current[:MAX_VETTING_NOTE_LENGTH]
    if not current:
        return marker[:MAX_VETTING_NOTE_LENGTH]
    combined = f"{current}\n{marker}"
    if len(combined) <= MAX_VETTING_NOTE_LENGTH:
        return combined
    room = MAX_VETTING_NOTE_LENGTH - len(marker) - 1
    if room <= 0:
        return marker[:MAX_VETTING_NOTE_LENGTH]
    return f"{current[:room].rstrip()}\n{marker}"


def _merge_translations(body: dict[str, Any], patch: dict[str, str]) -> None:
    if not patch:
        return
    current = dict(body.get("name_translations") or {})
    for key, value in patch.items():
        if not str(current.get(key) or "").strip():
            current[key] = value
    body["name_translations"] = current
