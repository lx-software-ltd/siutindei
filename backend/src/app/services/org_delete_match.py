"""Match an import row to an organization an admin deleted."""

from __future__ import annotations

from typing import Any

from sqlalchemy import cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name, parse_place_id
from app.db.models import OrganizationMerge

ORGANIZATION_DELETED = "organization was deleted"


def import_matches_deleted_organization(
    session: Session,
    raw_org: dict[str, Any],
    cleaned_name: Any,
) -> bool:
    """True when the file matches an organization an admin deleted.

    Place id matches that place id. Source id matches only the same
    catalog source. A name matches when the place id and the catalog
    source id do not contradict. Names are compared after case-folding
    and collapsed whitespace. Place id and source id are separate
    queries so their indexes can be used.
    """
    place_id = parse_place_id(raw_org.get("place_id"))
    source = _source(raw_org.get("source"))
    source_id = _text(raw_org.get("source_id"))
    names = {
        normalize_org_name(value)
        for value in (raw_org.get("name"), cleaned_name)
        if isinstance(value, str) and value.strip()
    }
    if place_id and _any_match(
        session,
        place_id,
        source,
        source_id,
        names,
        only_place_id=place_id,
    ):
        return True
    if source_id and _any_match(
        session,
        place_id,
        source,
        source_id,
        names,
        source_id_filter=source_id,
        source_filter=source,
    ):
        return True
    name_clause = _names_match_sql(names)
    if name_clause is None:
        return False
    return _any_match(
        session,
        place_id,
        source,
        source_id,
        names,
        extra=name_clause,
    )


def results_skipped_deleted(results: Any) -> bool:
    """True when a stored import skipped an organization as deleted."""
    if not isinstance(results, list):
        return False
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "organizations" and item.get("status") == "skipped":
            if _result_says_deleted(item):
                return True
    return False


def stored_deletion_skips_still_match(session: Session, results: Any) -> bool:
    """False when a stored skip no longer matches a deletion.

    A completed import can be returned again only while every
    organization it skipped as deleted is still remembered.
    """
    if not isinstance(results, list):
        return True
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "organizations" or item.get("status") != "skipped":
            continue
        if not _result_says_deleted(item):
            continue
        raw = {
            "name": item.get("key"),
            "place_id": item.get("place_id"),
            "source": item.get("source"),
            "source_id": item.get("source_id"),
        }
        if not import_matches_deleted_organization(session, raw, item.get("key")):
            return False
    return True


def _any_match(
    session: Session,
    place_id: str | None,
    source: str,
    source_id: str,
    names: set[str],
    only_place_id: str | None = None,
    source_id_filter: str | None = None,
    source_filter: str | None = None,
    extra: Any | None = None,
) -> bool:
    clauses: list[Any] = [OrganizationMerge.kind == "delete"]
    if only_place_id:
        clauses.append(OrganizationMerge.place_id == only_place_id)
    if source_id_filter:
        clauses.append(OrganizationMerge.source_id == source_id_filter)
        clauses.append(_source_equals(source_filter or ""))
    if extra is not None:
        clauses.append(extra)
    rows = session.scalars(select(OrganizationMerge).where(*clauses)).all()
    return any(_row_matches(row, place_id, source, source_id, names) for row in rows)


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
    if not (names & _normalized_names(row)):
        return False
    return not _name_contradicts(row, place_id, source, source_id)


def _name_contradicts(
    row: OrganizationMerge,
    place_id: str | None,
    source: str,
    source_id: str,
) -> bool:
    row_place = _optional(row.place_id)
    row_source_id = _optional(row.source_id)
    if place_id and row_place and place_id != row_place:
        return True
    if (
        source_id
        and row_source_id
        and (_source(row.source) != source or source_id != row_source_id)
    ):
        return True
    return False


def _normalized_names(row: OrganizationMerge) -> set[str]:
    snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
    stored = snapshot.get("normalized_names")
    if isinstance(stored, list):
        return {item for item in stored if isinstance(item, str) and item}
    return {normalize_org_name(name) for name in _names_from_snapshot(snapshot)}


def _names_match_sql(names: set[str]) -> Any | None:
    if not names:
        return None
    elements = _normalized_name_elements()
    return (
        select(literal(1))
        .select_from(elements)
        .where(elements.c.value.in_(sorted(names)))
        .exists()
    )


def _name_search_sql(needle: str) -> Any:
    pattern = f"%{_like_escape(needle)}%"
    elements = _normalized_name_elements()
    return (
        select(literal(1))
        .select_from(elements)
        .where(elements.c.value.like(pattern, escape="\\"))
        .exists()
    )


def _normalized_name_elements():
    payload = func.coalesce(
        OrganizationMerge.snapshot["normalized_names"],
        cast(literal("[]"), JSONB),
    )
    return func.jsonb_array_elements_text(payload).table_valued("value")


def _source_equals(source: str) -> Any:
    if source:
        return func.lower(func.coalesce(OrganizationMerge.source, "")) == source
    return OrganizationMerge.source.is_(None)


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


def _result_says_deleted(item: dict[str, Any]) -> bool:
    if item.get("error") == ORGANIZATION_DELETED:
        return True
    errors = item.get("errors")
    if not isinstance(errors, list) or not errors:
        return False
    first = errors[0]
    return isinstance(first, dict) and first.get("message") == ORGANIZATION_DELETED


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
