"""Idempotent import-job storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ImportJob


def find_import_job_by_key(
    session: Session,
    object_key: str,
) -> ImportJob | None:
    """Return the stored job for an object_key, if any."""
    return session.execute(
        select(ImportJob).where(ImportJob.object_key == object_key)
    ).scalar_one_or_none()


def find_import_job_by_id(
    session: Session,
    job_id: UUID,
) -> ImportJob | None:
    """Return a stored import job by id."""
    return session.get(ImportJob, job_id)


def store_import_job(
    session: Session,
    object_key: str,
    *,
    dry_run: bool,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    file_warnings: list[str],
) -> ImportJob:
    """Persist the import result for later GET and retries.

    A stored dry-run job is replaced when the same object_key is
    processed live. A stored live job is never overwritten by a
    later dry-run.
    """
    existing = find_import_job_by_key(session, object_key)
    if existing is not None:
        if existing.dry_run == dry_run:
            return existing
        if not existing.dry_run:
            return existing
        existing.dry_run = dry_run
        existing.summary = summary
        existing.results = results
        existing.file_warnings = file_warnings
        existing.updated_at = datetime.now(timezone.utc)
        session.flush()
        return existing
    job = ImportJob(
        object_key=object_key,
        dry_run=dry_run,
        summary=summary,
        results=results,
        file_warnings=file_warnings,
    )
    session.add(job)
    session.flush()
    return job


def serialize_import_job(job: ImportJob) -> dict[str, Any]:
    """Serialize a stored import job for the owner UI."""
    return {
        "id": str(job.id),
        "object_key": job.object_key,
        "dry_run": job.dry_run,
        "summary": job.summary,
        "results": job.results,
        "file_warnings": job.file_warnings,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
