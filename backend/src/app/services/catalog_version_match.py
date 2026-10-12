"""Decide whether an import row matches catalog version 1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name, parse_place_id
from app.db.models import CatalogVersion, Organization, OrganizationMerge
from app.exceptions import ValidationError
from app.services.catalog_version_payload import organization_payload
from app.services.catalog_version_shape import (
    ACTIVITY_SHAPE_KEYS,
    LOCATION_SHAPE_KEYS,
    ORG_SHAPE_KEYS,
    PRICING_SHAPE_KEYS,
    SCHEDULE_SHAPE_KEYS,
    file_matches_snapshot,
    payload_differs,
)
from app.services.org_delete import (
    ORGANIZATION_DELETED,
    import_matches_deleted_organization,
)

REMOVED_MATCH = "Removed record matches version 1; not imported again"
REMOVED_DIFFERS = "Removed record differs from version 1; not imported again"
ADMIN_EDITS_OVERWRITTEN = "This import overwrites admin edits made since version 1"

_PRESENT_KEYS = {
    "organization": set(ORG_SHAPE_KEYS),
    "activity": set(ACTIVITY_SHAPE_KEYS),
    "location": set(LOCATION_SHAPE_KEYS),
    "pricing": set(PRICING_SHAPE_KEYS),
    "schedule": set(SCHEDULE_SHAPE_KEYS) | {"weekly_entries"},
}


class ImportRowOutcome(Exception):
    """A row the importer must record without writing a catalog record."""

    def __init__(
        self,
        status: str,
        warnings: list[str] | None = None,
        *,
        entity_id: str | None = None,
        skip_children: bool = False,
    ) -> None:
        super().__init__(status)
        self.status = status
        self.warnings = list(warnings or [])
        self.entity_id = entity_id
        self.skip_children = skip_children


def set_import_job_context(session: Session, import_job_id: Any) -> None:
    """Tell the version trigger which import job is writing."""
    if import_job_id is None or not _is_postgres(session):
        return
    session.execute(
        text("SELECT set_config('app.current_import_job_id', :job_id, true)"),
        {"job_id": str(import_job_id)},
    )


def forget_catalog_tombstones(session: Session, org_id: UUID) -> None:
    """Stop version-1 lookup from blocking an organization an admin forgot."""
    session.execute(
        update(CatalogVersion)
        .where(
            CatalogVersion.entity_type == "organization",
            CatalogVersion.entity_id == org_id,
        )
        .values(reason="forgotten")
    )


def annotate_merged_tombstones(
    session: Session,
    source_id: Any,
    survivor_id: Any,
) -> None:
    """Mark the source tombstone as merged into the survivor."""
    session.execute(
        update(CatalogVersion)
        .where(
            CatalogVersion.entity_type == "organization",
            CatalogVersion.entity_id == source_id,
            CatalogVersion.action == "deleted",
        )
        .values(reason="merged", related_id=survivor_id)
    )


def apply_org_gate(
    session: Session,
    raw_org: dict[str, Any],
    body: dict[str, Any],
    existing: Organization | None,
    allow_updates: bool,
    warnings: list[str] | None,
) -> tuple[Organization | None, str | None]:
    """Return a terminal status, or None when the caller should write."""
    if existing is None:
        return _absent_organization(session, raw_org, body, allow_updates, warnings)
    incoming = {**body, "name": body.get("name") or raw_org.get("name")}
    if raw_org.get("status") not in (None, ""):
        incoming["status"] = raw_org.get("status")
    status = _live_status(
        session,
        "organization",
        existing.id,
        incoming,
        _present(raw_org, body, "organization"),
        organization_payload(existing),
        allow_updates,
        warnings,
    )
    return existing, status


def apply_child_gate(
    session: Session,
    *,
    entity_type: str,
    org_id: Any,
    live: Any,
    incoming: dict[str, Any],
    present: set[str],
    current: dict[str, Any] | None,
    allow_updates: bool,
    warnings: list[str] | None,
    names: set[str] | None = None,
) -> Any:
    """Return the live row when the caller should continue, else a status.

    A removed version-1 row raises ``ImportRowOutcome`` instead.
    """
    if live is not None:
        return _live_status(
            session,
            entity_type,
            live.id,
            incoming,
            present,
            current or {},
            allow_updates,
            warnings,
        )
    baseline = _find_removed(session, entity_type, org_id, incoming, names)
    if baseline is None:
        return None
    _raise_removed(entity_type, incoming, baseline.snapshot or {}, present)


def _absent_organization(
    session: Session,
    raw_org: dict[str, Any],
    body: dict[str, Any],
    allow_updates: bool,
    warnings: list[str] | None,
) -> tuple[Organization | None, str | None]:
    incoming = {**body, "name": body.get("name") or raw_org.get("name")}
    if raw_org.get("status") not in (None, ""):
        incoming["status"] = raw_org.get("status")
    present = _present(raw_org, body, "organization")
    baseline = _find_org_version1(session, raw_org, incoming)
    if baseline is not None:
        live = session.get(Organization, baseline.entity_id)
        if live is not None:
            status = _status_for_snapshot(
                "organization",
                incoming,
                baseline.snapshot or {},
                present,
                organization_payload(live),
                allow_updates,
                warnings,
                partial=False,
            )
            return live, status
        merge = session.scalars(
            select(OrganizationMerge).where(
                OrganizationMerge.merged_org_id == baseline.entity_id,
                OrganizationMerge.kind == "merge",
            )
        ).first()
        if merge is not None and merge.survivor_org_id is not None:
            survivor = session.get(Organization, merge.survivor_org_id)
            if survivor is not None:
                status = _status_for_snapshot(
                    "organization",
                    incoming,
                    baseline.snapshot or {},
                    present,
                    organization_payload(survivor),
                    allow_updates,
                    warnings,
                    partial=False,
                )
                return survivor, status
        _raise_removed("organization", incoming, baseline.snapshot or {}, present)
    if import_matches_deleted_organization(session, raw_org, body.get("name")):
        raise ValidationError(ORGANIZATION_DELETED, field="name")
    named = _merge_by_name(session, str(incoming.get("name") or ""))
    if named is None or named.survivor_org_id is None:
        return None, None
    survivor = session.get(Organization, named.survivor_org_id)
    if survivor is None:
        return None, None
    snapshot = named.snapshot if isinstance(named.snapshot, dict) else {}
    status = _status_for_snapshot(
        "organization",
        incoming,
        snapshot,
        present,
        organization_payload(survivor),
        allow_updates,
        warnings,
        partial=True,
    )
    return survivor, status


def _live_status(
    session: Session,
    entity_type: str,
    entity_id: Any,
    incoming: dict[str, Any],
    present: set[str],
    current: dict[str, Any],
    allow_updates: bool,
    warnings: list[str] | None,
) -> str | None:
    baseline = _version1(session, entity_type, entity_id)
    if baseline is None:
        return None
    return _status_for_snapshot(
        entity_type,
        incoming,
        baseline.snapshot or {},
        present,
        current,
        allow_updates,
        warnings,
        partial=False,
    )


def _status_for_snapshot(
    entity_type: str,
    incoming: dict[str, Any],
    snapshot: dict[str, Any],
    present: set[str],
    current: dict[str, Any],
    allow_updates: bool,
    warnings: list[str] | None,
    *,
    partial: bool,
) -> str | None:
    if file_matches_snapshot(
        entity_type,
        incoming,
        snapshot,
        present,
        partial=partial,
    ):
        return "unchanged"
    if not allow_updates:
        return "skipped"
    if payload_differs(entity_type, current, snapshot, partial=partial):
        _warn(warnings, ADMIN_EDITS_OVERWRITTEN)
    return None


def _raise_removed(
    entity_type: str,
    incoming: dict[str, Any],
    snapshot: dict[str, Any],
    present: set[str],
) -> None:
    matched = file_matches_snapshot(entity_type, incoming, snapshot, present)
    raise ImportRowOutcome(
        "unchanged" if matched else "skipped",
        [REMOVED_MATCH if matched else REMOVED_DIFFERS],
        skip_children=True,
    )


def _find_removed(
    session: Session,
    entity_type: str,
    org_id: Any,
    incoming: dict[str, Any],
    names: set[str] | None,
) -> CatalogVersion | None:
    rows = session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == entity_type,
            CatalogVersion.version == 1,
            CatalogVersion.org_id == org_id,
            _visible(),
        )
    ).all()
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
    rows = session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == "organization",
            CatalogVersion.version == 1,
            _visible(),
        )
    ).all()
    place_id = parse_place_id(raw_org.get("place_id"))
    source = _text(raw_org.get("source"))
    source_id = _text(raw_org.get("source_id"))
    name = normalize_org_name(str(incoming.get("name") or ""))
    file_has_strong_id = bool(place_id or source_id)

    def _name_matches(snap: dict[str, Any]) -> bool:
        # Same rule as a remembered deletion: a name matches only when
        # the file has no place id and no source id, or version 1 had
        # neither. A different place id is a different organization.
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
    rows = session.scalars(
        select(OrganizationMerge).where(OrganizationMerge.kind == "merge")
    ).all()
    found = [row for row in rows if _merge_name_matches(row.snapshot, wanted)]
    if len(found) != 1:
        return None
    return found[0]


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


def _version1(
    session: Session, entity_type: str, entity_id: Any
) -> CatalogVersion | None:
    return session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == entity_type,
            CatalogVersion.entity_id == entity_id,
            CatalogVersion.version == 1,
            _visible(),
        )
    ).first()


def _visible() -> Any:
    return or_(
        CatalogVersion.reason.is_(None),
        CatalogVersion.reason != "forgotten",
    )


def _present(
    raw: dict[str, Any],
    body: dict[str, Any],
    entity_type: str,
) -> set[str]:
    allowed = _PRESENT_KEYS[entity_type]
    return {key for key in allowed if key in raw or key in body}


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


def _warn(warnings: list[str] | None, message: str) -> None:
    if warnings is not None and message not in warnings:
        warnings.append(message)


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
