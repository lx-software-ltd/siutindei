"""Idempotent import-job storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import ImportJob
from app.services.org_delete import stored_deletion_skips_still_match

IMPORT_JOB_SOURCES = frozenset({"ui", "board"})


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


def begin_import_retry(session: Session, job: ImportJob) -> ImportJob:
    """Mark a completed job running without dropping its stored results."""
    job.status = "running"
    job.dry_run = False
    job.updated_at = datetime.now(timezone.utc)
    session.flush()
    return job


def caller_import_source(*, is_admin: bool, is_importer: bool) -> str:
    """Map the caller to the history Source column.

    The importer group is the board catalog API. An admin session is
    the Imports page. An admin who is also an importer stays ``ui``,
    matching the path that clears the board catalog manager.
    """
    if is_importer and not is_admin:
        return "board"
    return "ui"


def summary_source(summary: Any) -> str | None:
    """Return a known source stored on a job summary."""
    if not isinstance(summary, dict):
        return None
    source = summary.get("source")
    if isinstance(source, str) and source in IMPORT_JOB_SOURCES:
        return source
    return None


def source_for_import_run(
    caller: str,
    previous_summary: Any,
    *,
    retry: bool,
) -> str:
    """Source written on this run.

    A retry keeps the source already stored on the job. A first run
    uses the caller. An unknown caller value is recorded as ``ui``.
    """
    if caller not in IMPORT_JOB_SOURCES:
        caller = "ui"
    if retry:
        stored = summary_source(previous_summary)
        if stored:
            return stored
    return caller


def _summary_with_source(source: str | None) -> dict[str, Any]:
    if source in IMPORT_JOB_SOURCES:
        return {"source": source}
    return {}


def begin_import_job(
    session: Session,
    object_key: str,
    *,
    source: str | None = None,
) -> ImportJob:
    """Create or reuse a live job row before organizations are written."""
    existing = find_import_job_by_key(session, object_key)
    now = datetime.now(timezone.utc)
    summary = _summary_with_source(source)
    if existing is not None:
        existing.dry_run = False
        existing.status = "running"
        existing.summary = summary
        existing.results = []
        existing.file_warnings = []
        existing.updated_at = now
        session.flush()
        return existing
    job = ImportJob(
        object_key=object_key,
        dry_run=False,
        status="running",
        summary=summary,
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


def fail_import_job(
    session: Session,
    job_id: Any,
    error_type: str,
    *,
    keep_completed: bool = False,
) -> None:
    """Mark a committed live import as failed after the work rolled back.

    A retry keeps the completed summary and results. The retry itself
    rolled back, so the previous history is still the job record.
    """
    job = session.get(ImportJob, job_id)
    if job is None:
        return
    now = datetime.now(timezone.utc)
    if keep_completed:
        job.status = "completed"
        warnings = list(job.file_warnings or [])
        note = f"Retry failed: {error_type[:80]}"
        if note not in warnings:
            warnings.append(note)
        job.file_warnings = warnings
        job.updated_at = now
        session.flush()
        return
    source = summary_source(job.summary)
    job.status = "failed"
    job.summary = {"error": error_type[:80]}
    if source:
        job.summary["source"] = source
    job.updated_at = now
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


def job_source(job: Any) -> str | None:
    """Source shown in import history. Missing on older jobs."""
    return summary_source(getattr(job, "summary", None))


def job_allow_updates(job: ImportJob) -> bool:
    """Whether the stored run updated existing rows.

    Jobs saved before the flag existed updated existing rows.
    """
    summary = job.summary if isinstance(job.summary, dict) else {}
    if "allow_updates" not in summary:
        return True
    return bool(summary.get("allow_updates"))


def stored_job_answers_request(
    job: Any,
    dry_run: bool,
    allow_updates: bool,
) -> bool:
    """Return True when the stored job should be returned as-is.

    A dry run does not block a later live import. A failed live import
    can be retried with the same object key. A different
    ``allow_updates`` value runs the file again.
    """
    if job.dry_run and not dry_run:
        return False
    if not dry_run and getattr(job, "status", None) == "failed":
        return False
    return job_allow_updates(job) == allow_updates


def reuse_stored_import_job(
    session: Session,
    job: Any,
    dry_run: bool,
    allow_updates: bool,
) -> bool:
    """Return True when the stored job is still the right response.

    A job that skipped an organization because an admin deleted it is
    stale once that identity is forgotten. The same file then runs again.
    """
    if not stored_job_answers_request(job, dry_run, allow_updates):
        return False
    return stored_deletion_skips_still_match(session, getattr(job, "results", None))


def serialize_import_job(job: ImportJob) -> dict[str, Any]:
    """Serialize a stored import job for the owner UI."""
    return {
        "id": str(job.id),
        "object_key": job.object_key,
        "dry_run": job.dry_run,
        "allow_updates": job_allow_updates(job),
        "status": job.status,
        "summary": job.summary,
        "results": job.results,
        "file_warnings": job.file_warnings,
        "source": job_source(job),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def serialize_import_job_summary(job: ImportJob) -> dict[str, Any]:
    """Serialize a job for the history list without per-row results."""
    payload = serialize_import_job(job)
    payload.pop("results", None)
    payload["result_count"] = len(job.results or [])
    return payload
