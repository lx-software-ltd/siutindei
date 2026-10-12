"""Remember an admin-deleted organization so import does not create it."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name
from app.db.audit import AuditService
from app.db.models import AuditLog, Organization, OrganizationMerge
from app.exceptions import NotFoundError, ValidationError
from app.services.org_delete_match import (
    ORGANIZATION_DELETED,
    _name_search_sql,
    _names_from_snapshot,
    _optional,
    _text,
    _unique_names,
    import_matches_deleted_organization,
    stored_deletion_skips_still_match,
)

_IMPORTED_NAME = re.compile(r"Imported name:\s*(.+)")

__all__ = [
    "ORGANIZATION_DELETED",
    "forget_deleted_organization",
    "import_matches_deleted_organization",
    "list_deleted_organizations",
    "remember_deleted_organization",
    "stored_deletion_skips_still_match",
]


def remember_deleted_organization(
    session: Session,
    org: Organization,
    deleted_by: str | None,
) -> None:
    """Store the identity, then leave no survivor for import to update.

    Rows that already forwarded to this organization become deletions
    too, so a merged-away place id is not imported as a new organization
    after the survivor is removed. They share one deletion group with
    the organization just deleted. Contact fields are not kept.
    """
    group_id = str(uuid4())
    deleted_at = datetime.now(timezone.utc)
    audit = AuditService(session, user_id=deleted_by)
    forwarded = session.scalars(
        select(OrganizationMerge).where(OrganizationMerge.survivor_org_id == org.id)
    ).all()
    for row in forwarded:
        before = _audit_values(row)
        row.survivor_org_id = None
        row.kind = "delete"
        row.snapshot = _identity_snapshot(
            _names_from_snapshot(row.snapshot),
            group_id=group_id,
            was_merge=True,
        )
        row.merged_by = deleted_by
        row.merged_at = deleted_at
        audit.log_update(
            "organization_merges",
            row.id,
            old_values=before,
            new_values=_audit_values(row),
        )
    created = OrganizationMerge(
        merged_org_id=org.id,
        survivor_org_id=None,
        kind="delete",
        source=_optional(org.source),
        source_id=_optional(org.source_id),
        place_id=_optional(org.place_id),
        snapshot=_identity_snapshot(
            _remembered_names(session, org),
            group_id=group_id,
        ),
        moved_counts={},
        merged_by=deleted_by,
        merged_at=deleted_at,
    )
    session.add(created)
    session.flush()
    audit.log_create(
        "organization_merges",
        created.id,
        new_values=_audit_values(created),
    )


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
    page = list(rows[:limit])
    related = _also_forgets(session, page)
    next_cursor = _cursor_value(page[-1]) if len(rows) > limit and page else None
    return {
        "items": [_public_deletion(row, related.get(row.id, [])) for row in page],
        "next_cursor": next_cursor,
    }


def forget_deleted_organization(
    session: Session,
    deletion_id: UUID,
    forgotten_by: str | None = None,
) -> None:
    """Drop a remembered identity so a later import can create it.

    Forgetting the organization that was deleted also forgets identities
    that had been merged into it, and marks each organization's catalog
    versions forgotten. Forgetting one of those merged identities leaves
    the others in place.
    """
    row = session.get(OrganizationMerge, deletion_id)
    if row is None or row.kind != "delete":
        raise NotFoundError("deleted organization", str(deletion_id))
    from app.services.catalog_version_match import forget_catalog_tombstones

    audit = AuditService(session, user_id=forgotten_by)
    for item in _forget_targets(session, row):
        forget_catalog_tombstones(session, item.merged_org_id)
        audit.log_delete(
            "organization_merges",
            item.id,
            old_values=_audit_values(item),
        )
        session.delete(item)
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


def _identity_snapshot(
    names: list[str],
    *,
    group_id: str,
    was_merge: bool = False,
) -> dict[str, Any]:
    cleaned = _unique_names(names)
    snapshot: dict[str, Any] = {
        "name": cleaned[0] if cleaned else "",
        "names": cleaned,
        "normalized_names": [normalize_org_name(name) for name in cleaned],
        "deletion_group": group_id,
    }
    if was_merge:
        snapshot["was_merge"] = True
    return snapshot


def _public_deletion(
    row: OrganizationMerge,
    also_forgets: list[str],
) -> dict[str, Any]:
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
        "was_merge": _was_merge(row.snapshot),
        "also_forgets": also_forgets,
    }


def _also_forgets(
    session: Session,
    page: list[OrganizationMerge],
) -> dict[Any, list[str]]:
    primary_ids: dict[str, Any] = {}
    for row in page:
        group = _group_id(row.snapshot)
        if group and not _was_merge(row.snapshot):
            primary_ids[group] = row.id
    if not primary_ids:
        return {}
    siblings = session.scalars(
        select(OrganizationMerge).where(
            OrganizationMerge.kind == "delete",
            OrganizationMerge.snapshot["deletion_group"].astext.in_(list(primary_ids)),
        )
    ).all()
    names: dict[Any, list[str]] = {row_id: [] for row_id in primary_ids.values()}
    for sibling in siblings:
        group = _group_id(sibling.snapshot)
        if group is None:
            continue
        primary_id = primary_ids.get(group)
        if primary_id is None or sibling.id == primary_id:
            continue
        sibling_names = _names_from_snapshot(sibling.snapshot)
        if sibling_names:
            names[primary_id].append(sibling_names[0])
    return names


def _forget_targets(
    session: Session,
    row: OrganizationMerge,
) -> list[OrganizationMerge]:
    group = _group_id(row.snapshot)
    if not group or _was_merge(row.snapshot):
        return [row]
    rows = session.scalars(
        select(OrganizationMerge).where(
            OrganizationMerge.kind == "delete",
            OrganizationMerge.snapshot["deletion_group"].astext == group,
        )
    ).all()
    return list(rows) or [row]


def _audit_values(row: OrganizationMerge) -> dict[str, Any]:
    return {
        "kind": row.kind,
        "place_id": row.place_id,
        "source": row.source,
        "source_id": row.source_id,
        "names": _names_from_snapshot(row.snapshot),
        "was_merge": _was_merge(row.snapshot),
        "deletion_group": _group_id(row.snapshot),
        "merged_by": row.merged_by,
    }


def _group_id(snapshot: Any) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get("deletion_group")
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _was_merge(snapshot: Any) -> bool:
    return isinstance(snapshot, dict) and snapshot.get("was_merge") is True


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
