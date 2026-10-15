"""Organizations a catalog import created or updated."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import CatalogVersion, ImportJob, Organization

_IMPORT_WRITE_STATUSES = frozenset({"created", "updated"})


def import_job_clause(session: Session, job_id: UUID):
    """Organizations this import created or updated.

    ``organizations.import_job_id`` stays on the creating job. A later
    import is recorded on the organization catalog version and on the
    job's organization results.
    """
    version_ids = select(CatalogVersion.entity_id).where(
        CatalogVersion.entity_type == "organization",
        CatalogVersion.import_job_id == job_id,
        CatalogVersion.action.in_(tuple(_IMPORT_WRITE_STATUSES)),
    )
    clauses = [
        Organization.import_job_id == job_id,
        Organization.id.in_(version_ids),
    ]
    result_ids = _organization_ids_in_import_results(session, job_id)
    if result_ids:
        clauses.append(Organization.id.in_(result_ids))
    return or_(*clauses)


def _organization_ids_in_import_results(session: Session, job_id: UUID) -> list[UUID]:
    job = session.get(ImportJob, job_id)
    if job is None:
        return []
    found: list[UUID] = []
    for row in job.results or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") != "organizations":
            continue
        if row.get("status") not in _IMPORT_WRITE_STATUSES:
            continue
        parsed = _optional_uuid(row.get("id"))
        if parsed is not None:
            found.append(parsed)
    return found


def _optional_uuid(value: object) -> UUID | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
