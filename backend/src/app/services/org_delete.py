"""Remember an admin-deleted organization so import does not create it."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, bindparam, or_, select, text
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name, parse_place_id
from app.db.models import AuditLog, Organization, OrganizationMerge
from app.exceptions import NotFoundError, ValidationError

ORGANIZATION_DELETED = "organization was deleted"
_IMPORTED_NAME = re.compile(r"Imported name:\s*(.+)")


def remember_deleted_organization(
    session: Session,
    org: Organization,
    deleted_by: str | None,
) -> None:
    """Store the identity, then leave no survivor for import to update.

    Rows that already forwarded to this organization become deletions
    too, so a merged-away place id is not imported as a new organization
    after the survivor is removed. Contact fields are not kept.
    """
    forwarded = session.scalars(
        select(OrganizationMerge).where(OrganizationMerge.survivor_org_id == org.id)
    ).all()
    for row in forwarded:
        row.survivor_org_id = None
        row.kind = "delete"
        row.snapshot = _identity_snapshot(_names_from_snapshot(row.snapshot))
    session.add(
        OrganizationMerge(
            merged_org_id=org.id,
            survivor_org_id=None,
            kind="delete",
            source=_optional(org.source),
            source_id=_optional(org.source_id),
            place_id=_optional(org.place_id),
            snapshot=_identity_snapshot(_remembered_names(session, org)),
            moved_counts={},
            merged_by=deleted_by,
        )
    )
    session.flush()


def import_matches_deleted_organization(
    session: Session,
    raw_org: dict[str, Any],
    cleaned_name: Any,
) -> bool:
    """True when the file matches an organization an admin deleted.

    Place id matches that place id. Source id matches only the same
    catalog source. A name matches only when the file has no place id
    and no source id, or the deleted organization had neither.
    """
    place_id = parse_place_id(raw_org.get("place_id"))
    source = _source(raw_org.get("source"))
    source_id = _text(raw_org.get("source_id"))
    names = {
        normalize_org_name(value)
        for value in (raw_org.get("name"), cleaned_name)
        if isinstance(value, str) and value.strip()
    }
    clauses: list[Any] = []
    if place_id:
        clauses.append(OrganizationMerge.place_id == place_id)
    if source_id:
        clauses.append(
            and_(
                OrganizationMerge.source_id == source_id,
                _source_equals(source),
            )
        )
    name_clause = _names_match_sql(names)
    if name_clause is not None:
        if place_id or source_id:
            clauses.append(
                and_(
                    OrganizationMerge.place_id.is_(None),
                    OrganizationMerge.source_id.is_(None),
                    name_clause,
                )
            )
        else:
            clauses.append(name_clause)
    if not clauses:
        return False
    rows = session.scalars(
        select(OrganizationMerge).where(
            OrganizationMerge.kind == "delete",
            or_(*clauses),
        )
    ).all()
    return any(_row_matches(row, place_id, source, source_id, names) for row in rows)


def list_deleted_organizations(
    session: Session,
    *,
    query: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Return remembered identities, newest first, without contact fields."""
    statement = select(OrganizationMerge).where(OrganizationMerge.kind == "delete")
    needle = _text(query).casefold()
    if needle:
        statement = statement.where(_name_search_sql(needle))
    if cursor:
        when, row_id = _parse_cursor(cursor)
        statement = statement.where(
            or_(
                OrganizationMerge.merged_at < when,
                and_(
                    OrganizationMerge.merged_at == when,
                    OrganizationMerge.id < row_id,
                ),
            )
        )
    rows = session.scalars(
        statement.order_by(
            OrganizationMerge.merged_at.desc(),
            OrganizationMerge.id.desc(),
        ).limit(limit + 1)
    ).all()
    page = rows[:limit]
    next_cursor = _cursor_value(page[-1]) if len(rows) > limit and page else None
    return {
        "items": [_public_deletion(row) for row in page],
        "next_cursor": next_cursor,
    }


def forget_deleted_organization(session: Session, deletion_id: UUID) -> None:
    """Drop one remembered identity so a later import can create it."""
    row = session.get(OrganizationMerge, deletion_id)
    if row is None or row.kind != "delete":
        raise NotFoundError("deleted organization", str(deletion_id))
    session.delete(row)
    session.flush()


def _remembered_names(session: Session, org: Organization) -> list[str]:
    values = [org.name or ""]
    note = org.source_note or ""
    values.extend(match.group(1) for match in _IMPORTED_NAME.finditer(note))
    audit_rows = session.execute(
        select(AuditLog.old_values, AuditLog.new_values).where(
            AuditLog.table_name == "organizations",
            AuditLog.record_id == str(org.id),
            AuditLog.action.in_(("INSERT", "UPDATE")),
        )
    )
    for old_values, new_values in audit_rows:
        for payload in (old_values, new_values):
            if isinstance(payload, dict) and isinstance(payload.get("name"), str):
                values.append(payload["name"])
    return _unique_names(values)


def _names_from_snapshot(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, dict):
        return []
    values: list[str] = []
    name = snapshot.get("name")
    if isinstance(name, str):
        values.append(name)
    raw_names = snapshot.get("names")
    if isinstance(raw_names, list):
        values.extend(item for item in raw_names if isinstance(item, str))
    return _unique_names(values)


def _identity_snapshot(names: list[str]) -> dict[str, Any]:
    cleaned = _unique_names(names)
    return {"name": cleaned[0] if cleaned else "", "names": cleaned}


def _public_deletion(row: OrganizationMerge) -> dict[str, Any]:
    names = _names_from_snapshot(row.snapshot)
    return {
        "id": str(row.id),
        "name": names[0] if names else "",
        "names": names,
        "place_id": row.place_id,
        "source": row.source,
        "source_id": row.source_id,
        "deleted_by": row.merged_by,
        "deleted_at": row.merged_at.isoformat() if row.merged_at else None,
    }


def _row_matches(
    row: OrganizationMerge,
    place_id: str | None,
    source: str,
    source_id: str,
    names: set[str],
) -> bool:
    if place_id and row.place_id == place_id:
        return True
    if (
        source_id
        and _text(row.source_id) == source_id
        and _source(row.source) == source
    ):
        return True
    file_has_identifier = bool(place_id or source_id)
    row_has_identifier = bool(_text(row.place_id) or _text(row.source_id))
    if file_has_identifier and row_has_identifier:
        return False
    return bool(names & _normalized_names(row))


def _normalized_names(row: OrganizationMerge) -> set[str]:
    return {normalize_org_name(name) for name in _names_from_snapshot(row.snapshot)}


def _names_match_sql(names: set[str]) -> Any | None:
    if not names:
        return None
    clauses = []
    for index, name in enumerate(sorted(names)):
        clauses.append(
            text(
                "EXISTS ("
                "SELECT 1 FROM ("
                "SELECT jsonb_array_elements_text("
                "COALESCE(organization_merges.snapshot->'names', '[]'::jsonb)"
                ") AS value "
                "UNION ALL SELECT organization_merges.snapshot->>'name'"
                ") AS remembered "
                "WHERE remembered.value IS NOT NULL "
                "AND lower(regexp_replace(btrim(remembered.value), "
                r"'\s+', ' ', 'g')) = :remembered_name_"
                f"{index})"
            ).bindparams(bindparam(f"remembered_name_{index}", value=name))
        )
    return or_(*clauses)


def _name_search_sql(needle: str) -> Any:
    pattern = f"%{_like_escape(needle)}%"
    return text(
        "("
        "lower(COALESCE(organization_merges.snapshot->>'name', '')) "
        "LIKE :deleted_name_pattern ESCAPE '\\' "
        "OR EXISTS ("
        "SELECT 1 FROM jsonb_array_elements_text("
        "COALESCE(organization_merges.snapshot->'names', '[]'::jsonb)"
        ") AS remembered(value) "
        "WHERE lower(remembered.value) LIKE :deleted_name_pattern ESCAPE '\\'"
        ")"
        ")"
    ).bindparams(bindparam("deleted_name_pattern", value=pattern))


def _source_equals(source: str) -> Any:
    if source:
        return text(
            "lower(COALESCE(organization_merges.source, '')) = :deleted_source"
        ).bindparams(bindparam("deleted_source", value=source))
    return text("organization_merges.source IS NULL")


def _cursor_value(row: OrganizationMerge) -> str:
    return f"{row.merged_at.isoformat()}|{row.id}"


def _parse_cursor(value: str) -> tuple[datetime, UUID]:
    stamp, separator, row_id = value.partition("|")
    if not separator:
        raise ValidationError("cursor is invalid", field="cursor")
    try:
        when = datetime.fromisoformat(stamp)
        parsed = UUID(row_id)
    except ValueError as exc:
        raise ValidationError("cursor is invalid", field="cursor") from exc
    return when, parsed


def _unique_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = normalize_org_name(cleaned)
        if key in seen:
            continue
        seen.add(key)
        names.append(cleaned)
    return names


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _optional(value: Any) -> str | None:
    text_value = _text(value)
    return text_value or None


def _source(value: Any) -> str:
    return _text(value).casefold()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
