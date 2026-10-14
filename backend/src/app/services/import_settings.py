"""Singleton import behaviour, with a fallback for older databases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CategorySuggestionSettings, ImportSettings
from app.exceptions import AppError, ValidationError

_NAME_CLEANUP = frozenset({"off", "propose", "apply"})
_UNKNOWN = frozenset({"capture", "fail"})
_DUPLICATES = frozenset({"off", "report"})
_LOCATIONS = frozenset({"off", "check"})
_CATEGORIES = frozenset({"off", "check"})
_REQUIRED = (
    "updated_at",
    "skip_deleted_organizations",
    "name_cleanup",
    "unknown_categories",
    "duplicates",
    "locations",
    "categories",
)


def load_import_settings(session: Session) -> ImportSettings:
    """Return the singleton. A missing row uses today's import behaviour."""
    getter = getattr(session, "get", None)
    if getter is None:
        return _transient("capture")
    row = getter(ImportSettings, 1)
    if row is not None:
        return row
    return _transient(_legacy_unknown_categories(session))


def _transient(unknown_categories: str) -> ImportSettings:
    return ImportSettings(
        id=1,
        skip_deleted_organizations=True,
        name_cleanup="apply",
        unknown_categories=unknown_categories,
        duplicates="off",
        locations="off",
        categories="off",
        updated_at=datetime.now(timezone.utc),
    )


def skip_deleted_organizations(session: Session) -> bool:
    """True when import should refuse a remembered deletion."""
    return bool(load_import_settings(session).skip_deleted_organizations)


def captures_unknown_categories(session: Session) -> bool:
    """True when an unknown category name is stored instead of rejected."""
    return load_import_settings(session).unknown_categories == "capture"


def serialize_import_settings(row: ImportSettings) -> dict[str, Any]:
    """JSON shape for GET and PUT."""
    return {
        "skip_deleted_organizations": bool(row.skip_deleted_organizations),
        "name_cleanup": row.name_cleanup,
        "unknown_categories": row.unknown_categories,
        "duplicates": row.duplicates,
        "locations": row.locations,
        "categories": row.categories,
        "updated_by": row.updated_by,
        "updated_at": _stamp(row.updated_at) if _is_persisted(row) else None,
    }


def update_import_settings(
    session: Session,
    body: dict[str, Any],
    *,
    updated_by: str | None,
) -> ImportSettings:
    """Replace the singleton. A stale ``updated_at`` is HTTP 409."""
    for field in _REQUIRED:
        if field not in body:
            raise ValidationError(f"{field} is required", field=field)
    current = _locked_settings(session)
    if current is None:
        if body.get("updated_at") not in (None, ""):
            raise AppError("Import settings were updated", status_code=409)
        current = ImportSettings(
            id=1,
            skip_deleted_organizations=True,
            name_cleanup="apply",
            unknown_categories=_legacy_unknown_categories(session),
            duplicates="off",
            locations="off",
            categories="off",
        )
        session.add(current)
    elif not _same_stamp(current.updated_at, body.get("updated_at")):
        raise AppError("Import settings were updated", status_code=409)
    current.skip_deleted_organizations = _parse_bool(
        body.get("skip_deleted_organizations"),
        "skip_deleted_organizations",
    )
    current.name_cleanup = _choice(
        body.get("name_cleanup"),
        _NAME_CLEANUP,
        "name_cleanup",
    )
    current.unknown_categories = _choice(
        body.get("unknown_categories"),
        _UNKNOWN,
        "unknown_categories",
    )
    current.duplicates = _choice(
        body.get("duplicates"),
        _DUPLICATES,
        "duplicates",
    )
    current.locations = _choice(
        body.get("locations"),
        _LOCATIONS,
        "locations",
    )
    current.categories = _choice(
        body.get("categories"),
        _CATEGORIES,
        "categories",
    )
    current.updated_by = updated_by
    current.updated_at = datetime.now(timezone.utc)
    session.flush()
    return current


def _locked_settings(session: Session) -> ImportSettings | None:
    stmt = select(ImportSettings).where(ImportSettings.id == 1)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def _legacy_unknown_categories(session: Session) -> str:
    flags = session.scalars(select(CategorySuggestionSettings.on_import_enabled)).all()
    if any(not flag for flag in flags):
        return "fail"
    return "capture"


def _is_persisted(row: ImportSettings) -> bool:
    state = getattr(row, "_sa_instance_state", None)
    return bool(state is not None and state.persistent)


def _parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValidationError(f"{field} must be a boolean", field=field)


def _choice(value: Any, allowed: frozenset[str], field: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    raise ValidationError(f"{field} is invalid", field=field)


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _same_stamp(stored: datetime | None, raw: Any) -> bool:
    return _stamp(stored) == (None if raw in (None, "") else str(raw))
