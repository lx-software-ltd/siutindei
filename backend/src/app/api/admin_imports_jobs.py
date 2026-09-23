"""Idempotent import-job storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
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
        status="completed",
        summary=summary,
        results=results,
        file_warnings=file_warnings,
    )
    session.add(job)
    session.flush()
    return job


def begin_import_job(session: Session, object_key: str) -> ImportJob:
    """Create or reuse a live job row before organizations are written."""
    existing = find_import_job_by_key(session, object_key)
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.dry_run = False
        existing.status = "running"
        existing.summary = {}
        existing.results = []
        existing.file_warnings = []
        existing.updated_at = now
        session.flush()
        return existing
    job = ImportJob(
        object_key=object_key,
        dry_run=False,
        status="running",
        summary={},
        results=[],
        file_warnings=[],
    )
    session.add(job)
    session.flush()
    return job


def finish_import_job(
    session: Session,
    job_id: Any,
    *,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    file_warnings: list[str],
) -> ImportJob:
    """Mark a live import job completed inside the same transaction."""
    job = session.get(ImportJob, job_id)
    if job is None:
        raise RuntimeError("import job missing")
    job.status = "completed"
    job.dry_run = False
    job.summary = summary
    job.results = results
    job.file_warnings = file_warnings
    job.updated_at = datetime.now(timezone.utc)
    session.flush()
    return job


def fail_import_job(session: Session, job_id: Any, error_type: str) -> None:
    """Mark a committed live import as failed after the work rolled back."""
    job = session.get(ImportJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.summary = {"error": error_type[:80]}
    job.updated_at = datetime.now(timezone.utc)
    session.flush()


def list_import_jobs(
    session: Session,
    *,
    limit: int,
    cursor: UUID | None,
) -> list[ImportJob]:
    """Return import jobs newest first."""
    query = select(ImportJob).order_by(
        ImportJob.created_at.desc(),
        ImportJob.id.desc(),
    )
    if cursor is not None:
        cursor_job = session.get(ImportJob, cursor)
        if cursor_job is not None:
            query = query.where(
                or_(
                    ImportJob.created_at < cursor_job.created_at,
                    and_(
                        ImportJob.created_at == cursor_job.created_at,
                        ImportJob.id < cursor_job.id,
                    ),
                )
            )
    return list(session.scalars(query.limit(limit)).all())


def serialize_import_job(job: ImportJob) -> dict[str, Any]:
    """Serialize a stored import job for the owner UI."""
    return {
        "id": str(job.id),
        "object_key": job.object_key,
        "dry_run": job.dry_run,
        "status": job.status,
        "summary": job.summary,
        "results": job.results,
        "file_warnings": job.file_warnings,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def serialize_import_job_summary(job: ImportJob) -> dict[str, Any]:
    """Serialize a job for the history list without per-row results."""
    payload = serialize_import_job(job)
    payload.pop("results", None)
    payload["result_count"] = len(job.results or [])
    return payload
