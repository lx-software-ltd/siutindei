"""Decide whether an import row matches catalog version 1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from app.db.models import CatalogVersion, Organization, OrganizationMerge
from app.exceptions import ValidationError
from app.services.catalog_version_payload import organization_payload
from app.services.catalog_version_lookup import (
    _find_org_version1,
    _find_removed,
    _is_postgres,
    _merge_by_name,
    _visible,
)
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
IMPORT_EDITS_OVERWRITTEN = "This import overwrites changes from an earlier import"
SYSTEM_EDITS_OVERWRITTEN = "This import overwrites catalog changes made since version 1"
MIXED_EDITS_OVERWRITTEN = (
    "This import overwrites admin edits and an earlier import made since version 1"
)
KEPT_LATER = "File matches version 1; later catalog edits were kept"

_CONTACT_KEYS = frozenset(
    {
        "phone_country_code",
        "phone_number",
        "email",
        "whatsapp",
        "facebook",
        "instagram",
        "tiktok",
        "twitter",
        "xiaohongshu",
        "wechat",
    }
)

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
    """Stop version-1 lookup from blocking an organization an admin forgot.

    A merged organization keeps its reason. Contact fields are removed
    from the stored snapshots.
    """
    if _is_postgres(session):
        session.execute(
            text("SELECT catalog_forget_entity('organization', :org_id)"),
            {"org_id": org_id},
        )
        return
    _forget_rows(session, "organization", org_id, include_children=True)


def forget_removed_baseline(session: Session, entity_type: str, entity_id: Any) -> None:
    """Let a later import create a removed child again."""
    if _is_postgres(session):
        session.execute(
            text("SELECT catalog_forget_entity(:entity_type, :entity_id)"),
            {"entity_type": entity_type, "entity_id": entity_id},
        )
        return
    _forget_rows(session, entity_type, entity_id, include_children=False)


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
                session,
                "organization",
                live.id,
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
                    session,
                    "organization",
                    survivor.id,
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
        session,
        "organization",
        survivor.id,
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
        session,
        entity_type,
        entity_id,
        incoming,
        baseline.snapshot or {},
        present,
        current,
        allow_updates,
        warnings,
        partial=False,
    )


def _status_for_snapshot(
    session: Session,
    entity_type: str,
    entity_id: Any,
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
        if payload_differs(entity_type, current, snapshot, partial=partial):
            _warn(warnings, KEPT_LATER)
        return "unchanged"
    if not allow_updates:
        return "skipped"
    if payload_differs(entity_type, current, snapshot, partial=partial):
        _warn(warnings, _overwrite_warning(session, entity_type, entity_id))
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


def _forget_rows(
    session: Session,
    entity_type: str,
    entity_id: Any,
    *,
    include_children: bool,
) -> None:
    """SQLite stand-in for ``catalog_forget_entity``."""
    clauses = [
        (CatalogVersion.entity_type == entity_type)
        & (CatalogVersion.entity_id == entity_id)
    ]
    if include_children and entity_type == "organization":
        clauses.append(CatalogVersion.org_id == entity_id)
    rows = list(session.scalars(select(CatalogVersion).where(or_(*clauses))).all())
    merged = {
        (row.entity_type, row.entity_id) for row in rows if row.reason == "merged"
    }
    for row in rows:
        snapshot = dict(row.snapshot or {})
        row.snapshot = {
            key: value for key, value in snapshot.items() if key not in _CONTACT_KEYS
        }
        if (row.entity_type, row.entity_id) in merged:
            continue
        if row.version == 1 and row.reason != "merged":
            row.reason = "forgotten"


def _overwrite_warning(session: Session, entity_type: str, entity_id: Any) -> str:
    """Name who changed the row after version 1."""
    if entity_id is None or not _is_postgres(session):
        return ADMIN_EDITS_OVERWRITTEN
    rows = session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == entity_type,
            CatalogVersion.entity_id == entity_id,
            CatalogVersion.version > 1,
        )
    ).all()
    if not rows:
        return ADMIN_EDITS_OVERWRITTEN
    saw_admin = False
    saw_import = False
    saw_system = False
    for row in rows:
        if row.import_job_id is not None:
            saw_import = True
        elif row.user_id:
            saw_admin = True
        else:
            saw_system = True
    if saw_admin and saw_import:
        return MIXED_EDITS_OVERWRITTEN
    if saw_admin:
        return ADMIN_EDITS_OVERWRITTEN
    if saw_import and not saw_system:
        return IMPORT_EDITS_OVERWRITTEN
    return SYSTEM_EDITS_OVERWRITTEN


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


def _present(
    raw: dict[str, Any],
    body: dict[str, Any],
    entity_type: str,
) -> set[str]:
    allowed = _PRESENT_KEYS[entity_type]
    return {key for key in allowed if key in raw or key in body}


def _warn(warnings: list[str] | None, message: str) -> None:
    if warnings is not None and message not in warnings:
        warnings.append(message)
