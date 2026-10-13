"""Find catalog version 1 without loading every history row."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name, parse_place_id
from app.db.models import CatalogVersion, OrganizationMerge


def _find_removed(
    session: Session,
    entity_type: str,
    org_id: Any,
    incoming: dict[str, Any],
    names: set[str] | None,
) -> CatalogVersion | None:
    statement = select(CatalogVersion).where(
        CatalogVersion.entity_type == entity_type,
        CatalogVersion.version == 1,
        CatalogVersion.org_id == org_id,
        _visible(),
    )
    if _is_postgres(session):
        statement = _narrow_removed(statement, entity_type, incoming, names)
    rows = session.scalars(statement).all()
    matched = [
        row
        for row in rows
        if _identity_matches(entity_type, row.snapshot or {}, incoming, names)
        and session.get(_model_for(entity_type), row.entity_id) is None
    ]
    if len(matched) != 1:
        return None
    return matched[0]


def _find_org_version1(
    session: Session,
    raw_org: dict[str, Any],
    incoming: dict[str, Any],
) -> CatalogVersion | None:
    if not _is_postgres(session):
        return _find_org_version1_scan(session, raw_org, incoming)
    place_id = parse_place_id(raw_org.get("place_id"))
    source = _text(raw_org.get("source"))
    source_id = _text(raw_org.get("source_id"))
    name = normalize_org_name(str(incoming.get("name") or ""))
    file_has_strong_id = bool(place_id or source_id)

    def _one(rows: list[CatalogVersion], predicate: Any) -> CatalogVersion | None:
        found = [row for row in rows if predicate(row.snapshot or {})]
        if len(found) == 1:
            return found[0]
        return None

    if place_id:
        matched = _one(
            _org_version1(
                session,
                CatalogVersion.snapshot["place_id"].astext == place_id,
            ),
            lambda snap: _text(snap.get("place_id")) == place_id,
        )
        if matched is not None:
            return matched
    if source_id:
        matched = _one(
            _org_version1(
                session,
                CatalogVersion.snapshot["source_id"].astext == source_id,
                CatalogVersion.snapshot["source"].astext == source,
            ),
            lambda snap: (
                _text(snap.get("source_id")) == source_id
                and _text(snap.get("source")) == source
            ),
        )
        if matched is not None:
            return matched
    if not name:
        return None

    def _name_matches(snap: dict[str, Any]) -> bool:
        # A name matches only when the file has no place id and no
        # source id, or version 1 had neither.
        if normalize_org_name(_text(snap.get("name"))) != name:
            return False
        snapshot_has_strong_id = bool(
            _text(snap.get("place_id")) or _text(snap.get("source_id"))
        )
        return not (file_has_strong_id and snapshot_has_strong_id)

    return _one(
        _org_version1(session, _folded(CatalogVersion.snapshot["name"].astext) == name),
        _name_matches,
    )


def _find_org_version1_scan(
    session: Session,
    raw_org: dict[str, Any],
    incoming: dict[str, Any],
) -> CatalogVersion | None:
    """SQLite tests have no expression indexes. Scan version 1 in Python."""
    rows = _org_version1(session)
    place_id = parse_place_id(raw_org.get("place_id"))
    source = _text(raw_org.get("source"))
    source_id = _text(raw_org.get("source_id"))
    name = normalize_org_name(str(incoming.get("name") or ""))
    file_has_strong_id = bool(place_id or source_id)

    def _name_matches(snap: dict[str, Any]) -> bool:
        if not name or normalize_org_name(_text(snap.get("name"))) != name:
            return False
        snapshot_has_strong_id = bool(
            _text(snap.get("place_id")) or _text(snap.get("source_id"))
        )
        return not (file_has_strong_id and snapshot_has_strong_id)

    for predicate in (
        lambda snap: bool(place_id) and _text(snap.get("place_id")) == place_id,
        lambda snap: (
            bool(source_id)
            and _text(snap.get("source_id")) == source_id
            and _text(snap.get("source")) == source
        ),
        _name_matches,
    ):
        found = [row for row in rows if predicate(row.snapshot or {})]
        if len(found) == 1:
            return found[0]
    return None


def _merge_by_name(session: Session, name: str) -> OrganizationMerge | None:
    wanted = normalize_org_name(name)
    if not wanted:
        return None
    if not _is_postgres(session):
        rows = session.scalars(
            select(OrganizationMerge).where(OrganizationMerge.kind == "merge")
        ).all()
        found = [row for row in rows if _merge_name_matches(row.snapshot, wanted)]
        if len(found) != 1:
            return None
        return found[0]
    rows = session.scalars(
        select(OrganizationMerge)
        .where(OrganizationMerge.kind == "merge")
        .where(
            or_(
                text(
                    "lower(regexp_replace(btrim(snapshot->>'name'), "
                    "'\\s+', ' ', 'g')) = :wanted"
                ),
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements_text("
                    "COALESCE(snapshot->'names', '[]'::jsonb)) "
                    "AS merge_name(value) "
                    "WHERE lower(regexp_replace(btrim(merge_name.value), "
                    "'\\s+', ' ', 'g')) = :wanted)"
                ),
            )
        )
        .params(wanted=wanted)
    ).all()
    found = [row for row in rows if _merge_name_matches(row.snapshot, wanted)]
    if len(found) != 1:
        return None
    return found[0]


def _org_version1(session: Session, *predicates: Any) -> list[CatalogVersion]:
    return list(
        session.scalars(
            select(CatalogVersion).where(
                CatalogVersion.entity_type == "organization",
                CatalogVersion.version == 1,
                _visible(),
                *predicates,
            )
        ).all()
    )


def _narrow_removed(
    statement: Any,
    entity_type: str,
    incoming: dict[str, Any],
    names: set[str] | None,
) -> Any:
    if entity_type == "activity":
        wanted = {normalize_org_name(name) for name in names or set() if name}
        wanted.add(normalize_org_name(_text(incoming.get("name"))))
        wanted.discard("")
        if wanted:
            return statement.where(
                _folded(CatalogVersion.snapshot["name"].astext).in_(sorted(wanted))
            )
    if entity_type == "location":
        clauses = []
        place_id = parse_place_id(incoming.get("place_id"))
        if place_id:
            clauses.append(CatalogVersion.snapshot["place_id"].astext == place_id)
        address = normalize_org_name(_text(incoming.get("address")))
        if address:
            clauses.append(
                _folded(CatalogVersion.snapshot["address"].astext) == address
            )
        if clauses:
            return statement.where(or_(*clauses))
    return statement


def _folded(expression: Any) -> Any:
    return func.lower(func.regexp_replace(func.btrim(expression), r"\s+", " ", "g"))


def _identity_matches(
    entity_type: str,
    snapshot: dict[str, Any],
    incoming: dict[str, Any],
    names: set[str] | None,
) -> bool:
    if entity_type == "activity":
        wanted = {normalize_org_name(name) for name in names or set() if name}
        wanted.add(normalize_org_name(_text(incoming.get("name"))))
        wanted.discard("")
        return normalize_org_name(_text(snapshot.get("name"))) in wanted
    if entity_type == "location":
        place_id = parse_place_id(incoming.get("place_id"))
        if place_id and _text(snapshot.get("place_id")) == place_id:
            return True
        address = normalize_org_name(_text(incoming.get("address")))
        return (
            bool(address)
            and normalize_org_name(_text(snapshot.get("address"))) == address
        )
    if entity_type == "pricing":
        return (
            _text(snapshot.get("activity_id")) == _text(incoming.get("activity_id"))
            and _text(snapshot.get("location_id")) == _text(incoming.get("location_id"))
            and _text(snapshot.get("pricing_type"))
            == _text(incoming.get("pricing_type"))
        )
    if entity_type == "schedule":
        left = sorted(_text(item) for item in snapshot.get("languages") or [])
        right = sorted(_text(item) for item in incoming.get("languages") or [])
        return (
            _text(snapshot.get("activity_id")) == _text(incoming.get("activity_id"))
            and _text(snapshot.get("location_id")) == _text(incoming.get("location_id"))
            and left == right
        )
    return False


def _model_for(entity_type: str) -> type[Any]:
    from app.db.models import Activity, ActivityPricing, ActivitySchedule, Location

    return {
        "activity": Activity,
        "location": Location,
        "pricing": ActivityPricing,
        "schedule": ActivitySchedule,
    }[entity_type]


def _visible() -> Any:
    return or_(
        CatalogVersion.reason.is_(None),
        CatalogVersion.reason != "forgotten",
    )


def _merge_name_matches(snapshot: Any, wanted: str) -> bool:
    if not isinstance(snapshot, dict):
        return False
    values = [snapshot.get("name")]
    names = snapshot.get("names")
    if isinstance(names, list):
        values.extend(names)
    return any(
        isinstance(value, str) and normalize_org_name(value) == wanted
        for value in values
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_postgres(session: Session) -> bool:
    bind = getattr(session, "bind", None)
    if bind is None:
        getter = getattr(session, "get_bind", None)
        if not callable(getter):
            return False
        bind = getter()
    dialect = getattr(getattr(bind, "dialect", None), "name", "")
    return dialect == "postgresql"
