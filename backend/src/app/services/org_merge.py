"""Move one organization's records onto another and delete the source."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.audit import AuditService
from app.db.models import Activity, Location, Organization, OrganizationMerge
from app.exceptions import NotFoundError, ValidationError
from app.services.org_merge_checks import assert_identity_unique
from app.services.org_merge_children import fold_merged_records
from app.services.org_merge_media import copy_merged_media
from app.services.org_merge_plan import (
    FILL_FIELDS,
    REPARENT_TARGETS,
    TRANSLATION_FIELDS,
    build_merge_plan,
    suggest_survivor_id,
    text_value,
)

__all__ = ["merge_organizations", "suggest_survivor_id"]

_OVERRIDE_FIELDS = (
    set(FILL_FIELDS) | {"name", "manager_id"} | {item[0] for item in TRANSLATION_FIELDS}
)


def merge_organizations(
    session: Session,
    survivor_id: UUID,
    source_ids: list[UUID],
    overrides: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
    merged_by: str | None = None,
) -> dict[str, Any]:
    """Fill blanks on the survivor, reparent children, and delete sources.

    A request whose sources were already merged into this survivor returns
    ``already_merged`` and writes nothing. A source or survivor that now
    belongs to a different organization is rejected.
    """
    chosen = dict(overrides or {})
    unknown = sorted(set(chosen) - _OVERRIDE_FIELDS)
    if unknown:
        raise ValidationError(f"Unknown field {unknown[0]}", field=unknown[0])
    if survivor_id in source_ids:
        raise ValidationError("survivor_id is also a source", field="survivor_id")
    if not source_ids:
        raise ValidationError("source_ids is required", field="source_ids")

    orgs = _lock_orgs(session, [survivor_id, *source_ids])
    by_id = {str(org.id): org for org in orgs}
    survivor = by_id.get(str(survivor_id))
    if survivor is None:
        if _forwarded_survivor(session, survivor_id) is not None:
            raise ValidationError(
                "survivor was already merged",
                field="survivor_id",
            )
        raise NotFoundError("organizations", str(survivor_id))
    sources, already = _partition_sources(session, survivor, source_ids, by_id)
    if not sources:
        return _replay_plan(survivor, source_ids, dry_run)
    plan = build_merge_plan(session, survivor, sources, chosen)
    plan["dry_run"] = dry_run
    if already:
        plan["already_merged_source_ids"] = [str(source_id) for source_id in already]
    if dry_run:
        return plan
    _apply(session, survivor, sources, plan, merged_by)
    plan["merged"] = True
    return plan


def _partition_sources(
    session: Session,
    survivor: Organization,
    source_ids: list[UUID],
    by_id: dict[str, Organization],
) -> tuple[list[Organization], list[UUID]]:
    """Split sources into rows still present and rows already merged here."""
    pending: list[Organization] = []
    already: list[UUID] = []
    for source_id in source_ids:
        source = by_id.get(str(source_id))
        if source is not None:
            pending.append(source)
            continue
        target = _forwarded_survivor(session, source_id)
        if target is None:
            raise NotFoundError("organizations", str(source_id))
        if str(target) != str(survivor.id):
            raise ValidationError(
                "source was already merged into another organization",
                field="source_ids",
            )
        already.append(source_id)
    return pending, already


def _forwarded_survivor(session: Session, org_id: UUID) -> UUID | None:
    """Live organization a removed id currently forwards to."""
    seen: set[str] = set()
    current: UUID | None = org_id
    while current is not None and str(current) not in seen:
        seen.add(str(current))
        row = session.scalar(
            select(OrganizationMerge)
            .where(
                OrganizationMerge.merged_org_id == current,
                OrganizationMerge.kind == "merge",
            )
            .order_by(OrganizationMerge.merged_at.desc())
        )
        if row is None or row.survivor_org_id is None:
            return None
        survivor = session.get(Organization, row.survivor_org_id)
        if survivor is not None:
            return survivor.id
        current = row.survivor_org_id
    return None


def _replay_plan(
    survivor: Organization,
    source_ids: list[UUID],
    dry_run: bool,
) -> dict[str, Any]:
    ids = [str(source_id) for source_id in source_ids]
    return {
        "survivor_id": str(survivor.id),
        "source_ids": ids,
        "suggested_survivor_id": str(survivor.id),
        "fields": [],
        "moved": {},
        "warnings": [],
        "media_urls": list(survivor.media_urls or []),
        "values": {},
        "pending_deletes": [],
        "dry_run": dry_run,
        "already_merged": True,
        "already_merged_source_ids": ids,
        "merged": not dry_run,
    }


def _lock_orgs(session: Session, ids: list[UUID]) -> list[Organization]:
    stmt = select(Organization).where(Organization.id.in_(ids))
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return list(session.scalars(stmt).all())


def _apply(session, survivor, sources, plan, merged_by: str | None) -> None:
    values = plan["values"]
    filled = [
        field
        for field, value in values.items()
        if text_value(value) and _changed(survivor, field, value)
    ]
    originals = [
        {
            "snapshot": _snapshot(source),
            "source": source.source,
            "source_id": source.source_id,
            "place_id": source.place_id,
        }
        for source in sources
    ]
    for source in sources:
        source.name = f"merged-{source.id}"
        source.place_id = None
        source.source_id = None
    session.flush()
    assert_identity_unique(
        session,
        survivor,
        text_value(values.get("name", survivor.name)),
        text_value(values.get("place_id", survivor.place_id)),
    )
    _write_scalars(survivor, values)
    _write_translations(survivor, values)
    pending: list[str] = []
    media = []
    for source in sources:
        for url in source.media_urls or []:
            rewritten, delete_key = copy_merged_media(
                url,
                str(source.id),
                str(survivor.id),
            )
            if delete_key:
                pending.append(delete_key)
            if rewritten not in media and rewritten not in (survivor.media_urls or []):
                media.append(rewritten)
    survivor.media_urls = [*(survivor.media_urls or []), *media]
    if not text_value(survivor.logo_media_url):
        for source in sources:
            if text_value(source.logo_media_url):
                rewritten, delete_key = copy_merged_media(
                    source.logo_media_url,
                    str(source.id),
                    str(survivor.id),
                )
                survivor.logo_media_url = rewritten or None
                if delete_key:
                    pending.append(delete_key)
                break
    plan["pending_deletes"] = pending
    source_ids = [source.id for source in sources]
    session.execute(
        update(OrganizationMerge)
        .where(OrganizationMerge.survivor_org_id.in_(source_ids))
        .values(survivor_org_id=survivor.id)
    )
    for source, original in zip(sources, originals, strict=True):
        session.add(
            OrganizationMerge(
                merged_org_id=source.id,
                survivor_org_id=survivor.id,
                source=original["source"],
                source_id=original["source_id"],
                place_id=original["place_id"],
                snapshot=original["snapshot"],
                moved_counts=plan["moved"],
                merged_by=merged_by,
            )
        )
    session.flush()
    fold_merged_records(session, survivor, sources)
    for model, column, _key in REPARENT_TARGETS:
        if model in (Location, Activity):
            continue
        rows = session.scalars(select(model).where(column.in_(source_ids))).all()
        for row in rows:
            setattr(row, column.key, survivor.id)
    session.flush()
    for source in sources:
        session.expire(source, ["locations", "activities"])
    AuditService(session, user_id=merged_by).log_custom(
        "organizations",
        survivor.id,
        "MERGE",
        new_values={
            "source_ids": [str(source.id) for source in sources],
            "moved": plan["moved"],
            "filled_fields": filled,
        },
    )
    for source in sources:
        session.delete(source)
    session.flush()
    from app.services.catalog_version_match import annotate_merged_tombstones

    for source in sources:
        annotate_merged_tombstones(session, source.id, survivor.id)
    session.flush()
    from app.services.org_duplicates import invalidate_duplicate_cache

    invalidate_duplicate_cache()


def _changed(survivor, field: str, value: str) -> bool:
    if field in {item[0] for item in TRANSLATION_FIELDS}:
        return True
    return text_value(getattr(survivor, field, "")) != value


def _write_scalars(survivor: Organization, values: dict[str, Any]) -> None:
    for field in ("name", "manager_id", *FILL_FIELDS):
        if field not in values:
            continue
        result = values[field]
        if field == "name" and not result:
            raise ValidationError("name is required", field="name")
        if field == "manager_id" and not result:
            raise ValidationError("manager_id is required", field="manager_id")
        setattr(survivor, field, result or None)


def _write_translations(survivor: Organization, values: dict[str, Any]) -> None:
    for field, column, key, _label in TRANSLATION_FIELDS:
        if field not in values:
            continue
        current = dict(getattr(survivor, column) or {})
        result = values[field]
        if result:
            current[key] = result
        else:
            current.pop(key, None)
        setattr(survivor, column, current)


def _snapshot(org: Organization) -> dict[str, Any]:
    return {
        "id": str(org.id),
        "name": org.name,
        "description": org.description,
        "manager_id": org.manager_id,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "email": org.email,
        "website": org.website,
        "place_id": org.place_id,
        "source": org.source,
        "source_id": org.source_id,
        "source_url": org.source_url,
        "review_status": org.review_status,
        "status": org.status,
        "media_urls": list(org.media_urls or []),
    }
