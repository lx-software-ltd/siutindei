"""Remember a deleted organization so a later import does not create it."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import normalize_org_name, parse_place_id
from app.db.models import Organization, OrganizationMerge
from app.services.org_merge import _snapshot

ORGANIZATION_DELETED = "organization was deleted"


def remember_deleted_organization(
    session: Session,
    org: Organization,
    deleted_by: str | None,
) -> None:
    """Store the identity, then leave no survivor for import to update.

    Rows that already forwarded to this organization become deletions
    too, so a merged-away place id is not imported as a new organization
    after the survivor is removed.
    """
    session.execute(
        update(OrganizationMerge)
        .where(OrganizationMerge.survivor_org_id == org.id)
        .values(survivor_org_id=None)
    )
    session.add(
        OrganizationMerge(
            merged_org_id=org.id,
            survivor_org_id=None,
            source=org.source,
            source_id=org.source_id,
            place_id=org.place_id,
            snapshot=_snapshot(org),
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
    """True when the file matches an organization that was deleted."""
    place_id = parse_place_id(raw_org.get("place_id"))
    source_id = _text(raw_org.get("source_id"))
    names = {
        normalize_org_name(value)
        for value in (raw_org.get("name"), cleaned_name)
        if isinstance(value, str) and value.strip()
    }
    rows = session.scalars(
        select(OrganizationMerge).where(OrganizationMerge.survivor_org_id.is_(None))
    ).all()
    for row in rows:
        if place_id and row.place_id == place_id:
            return True
        if source_id and _text(row.source_id) == source_id:
            return True
        snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
        snap_name = snapshot.get("name")
        if isinstance(snap_name, str) and normalize_org_name(snap_name) in names:
            return True
    return False


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
