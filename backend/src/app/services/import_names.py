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


def activity_name_translations(body: dict[str, Any]) -> dict[str, Any]:
    """Name translations plus a blank-safe Chinese name from the file."""
    translations = dict(body.get("name_translations") or {})
    name_zh = body.get("name_zh")
    if (
        isinstance(name_zh, str)
        and name_zh.strip()
        and not str(translations.get("zh") or "").strip()
    ):
        translations["zh"] = name_zh.strip()
    return translations


def find_cleaned_activity(
    session: Session,
    repo: ActivityRepository,
    org: Organization,
    name: str,
    translations: dict[str, Any] | None = None,
):
    """Find an activity by its cleaned name when the raw name missed.

    Used only when the import is leaving existing rows unchanged. An
    approved organization does not clean activity names on the way in,
    so a later file can still carry the spelling from before a name fix.
    ``translations`` is the file's map, including a Chinese name, so the
    lookup uses the same rules as a normal import.
    """
    if org.review_status == "pending_review":
        return None
    result = sanitize_name(
        name,
        translations or {},
        load_name_fix_config(session),
    )
    if result.name.casefold() == name.casefold():
        return None
    return repo.find_by_org_and_name_case_insensitive(
        coerce_uuid(org.id),
        result.name,
    )


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
    from app.services.import_settings import load_import_settings

    body.pop("_name_change", None)
    mode = load_import_settings(session).name_cleanup
    if mode == "off":
        body["name"] = name
        return existing
    translations = body.get("name_translations") or {}
    result = sanitize_name(name, translations, load_name_fix_config(session))
    chosen = result.name
    matched = None
    if chosen.casefold() != name.casefold():
        try:
            matched = find_name(chosen)
        except MultipleResultsFound as exc:
            raise ValidationError("Multiple records found", field="name") from exc
    collides = matched is not None and (
        existing is None or str(matched.id) != str(existing.id)
    )
    if collides and existing is not None:
        if warnings is not None:
            warnings.append("Sanitized name matches another record; original name kept")
        body["name"] = name
        return existing
    if collides and existing is None:
        existing = matched
        body["name"] = chosen
        return existing
    if mode == "propose":
        return _propose_name(
            session, existing, name, result, translations, body, warnings
        )
    body["name"] = chosen
    if chosen != name or result.translation_patch:
        _merge_translations(body, result.translation_patch)
    if _stored_name_changes(existing, name, result):
        _remember(session, body, _name_change(name, result, translations, "applied"))
        if warnings is not None and chosen != name:
            warnings.append(f"Name cleaned: {name} → {chosen}")
    return existing


def _propose_name(session, existing, name, result, translations, body, warnings):
    """Store the raw name on create. Leave an existing name in place."""
    if existing is not None:
        body["name"] = existing.name
        stored = sanitize_name(
            existing.name or "",
            existing.name_translations or {},
            load_name_fix_config(session),
        )
        if stored.changed:
            _remember(
                session,
                body,
                _name_change(existing.name or "", stored, translations, "pending"),
            )
            if warnings is not None:
                warnings.append(
                    f"Name left for review: {existing.name} → {stored.name}"
                )
        return existing
    body["name"] = name
    if result.changed:
        _remember(session, body, _name_change(name, result, translations, "pending"))
        if warnings is not None:
            warnings.append(f"Name left for review: {name} → {result.name}")
    return existing


def _remember(session, body, change: dict) -> None:
    token = object()
    body["_import_name_token"] = token
    session.info[id(token)] = change


def _stored_name_changes(existing, name, result) -> bool:
    if not result.changed:
        return False
    if existing is None:
        return True
    return existing.name != result.name or bool(result.translation_patch)


def _name_change(name, result, translations, status) -> dict:
    return {
        "original": name,
        "proposed": result.name,
        "rules": list(result.rules),
        "translation_patch": result.translation_patch or None,
        "translations": translations if isinstance(translations, dict) else {},
        "status": status,
    }


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
