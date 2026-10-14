"""Create, claim, and finish data-quality runs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, DataQualityRun, ImportJob, Organization
from app.exceptions import NotFoundError, ValidationError
from app.services.aws_clients import get_client
from app.services.data_quality.checks import refresh_check, run_check
from app.services.data_quality.fingerprint import fingerprint
from app.services.import_settings import load_import_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

CHECK_VERSIONS = {
    "names": "names-1",
    "duplicates": "duplicates-1",
    "locations": "locations-1",
    "categories": "categories-1",
}
_MANUAL = ("names", "duplicates", "locations", "categories")
_OPEN = ("queued", "running")
_BUSY_LIMIT = 5
_TERMINAL_OK = frozenset({"done", "unchanged", "skipped"})


def stage_import_run(
    session: Session,
    *,
    import_job_id: UUID,
    results: list[dict[str, Any]] | None,
    requested_by: str | None,
) -> str | None:
    """Insert the post-import run in the import transaction. Names stay inline."""
    settings = load_import_settings(session)
    selected = []
    if settings.duplicates == "report":
        selected.append("duplicates")
    if settings.locations == "check":
        selected.append("locations")
    if settings.categories == "check":
        selected.append("categories")
    scope = scope_from_results(results)
    if not selected or _scope_empty(scope):
        return None
    existing = session.scalars(
        select(DataQualityRun).where(
            DataQualityRun.import_job_id == import_job_id,
            DataQualityRun.attempt == 1,
        )
    ).first()
    if existing is not None:
        return str(existing.id)
    run = _new_run(
        trigger="import",
        import_job_id=import_job_id,
        requested_by=requested_by,
        scope=scope,
        checks=selected,
    )
    try:
        with session.begin_nested():
            session.add(run)
            session.flush()
    except IntegrityError:
        found = session.scalars(
            select(DataQualityRun).where(
                DataQualityRun.import_job_id == import_job_id,
                DataQualityRun.attempt == 1,
            )
        ).first()
        if found is None:
            raise
        return str(found.id)
    return str(run.id)


def enqueue_staged_run(run_id: str | None) -> None:
    """Publish the run after the import commits. A missing queue leaves it queued."""
    if not run_id:
        return
    queue_url = os.getenv("CATEGORY_SUGGESTION_QUEUE_URL", "").strip()
    if not queue_url:
        logger.warning("CATEGORY_SUGGESTION_QUEUE_URL is not configured")
        return
    try:
        get_client("sqs").send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"data_quality_run_id": run_id}),
        )
    except Exception:
        logger.exception("Data quality run was not enqueued")


def create_manual_run(
    session: Session,
    body: dict[str, Any],
    *,
    requested_by: str | None,
) -> DataQualityRun:
    """Start an on-demand run, or return the in-flight run with the same inputs."""
    checks = _manual_checks(body.get("checks"))
    scope = resolve_scope(
        session, body.get("scope") if isinstance(body.get("scope"), dict) else {}
    )
    if _scope_empty(scope):
        raise ValidationError("Nothing to check", field="scope")
    config_hash = _config_hash(checks, scope)
    key = body.get("idempotency_key")
    if isinstance(key, str) and key.strip():
        existing_key = session.scalars(
            select(DataQualityRun).where(DataQualityRun.idempotency_key == key.strip())
        ).first()
        if existing_key is not None:
            return existing_key
    inflight = session.scalars(
        select(DataQualityRun)
        .where(
            DataQualityRun.trigger == "manual",
            DataQualityRun.status.in_(_OPEN),
            DataQualityRun.config_hash == config_hash,
        )
        .order_by(DataQualityRun.created_at)
    ).first()
    if inflight is not None:
        return inflight
    run = _new_run(
        trigger="manual",
        import_job_id=None,
        requested_by=requested_by,
        scope=scope,
        checks=checks,
        idempotency_key=key.strip() if isinstance(key, str) and key.strip() else None,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValidationError(
            "idempotency_key already exists", field="idempotency_key"
        ) from exc
    return run


def process_run(session: Session, run_id: UUID, message_id: str = "") -> bool:
    """Claim a run and advance checks. False asks SQS to deliver the message again."""
    run = session.get(DataQualityRun, run_id)
    if run is None or run.status == "done":
        return True
    seen = [str(item) for item in (run.processed_message_ids or []) if item]
    if message_id and message_id in seen:
        return True
    run.attempts = int(run.attempts or 0) + 1
    if run.started_at is None:
        run.started_at = datetime.now(timezone.utc)
    run.status = "running"
    checks = [dict(item) for item in (run.checks or [])]
    work: list[dict[str, Any]] = []
    busy = False
    for check in checks:
        if check.get("status") in {"done", "unchanged", "skipped"}:
            continue
        outcome = run_check(session, run, check)
        check["status"] = outcome["status"]
        check["detail"] = outcome.get("detail") or {}
        if outcome.get("batches"):
            work.append(outcome)
        if outcome["status"] == "busy":
            busy = True
            break
        session.flush()
    run.checks = checks
    run.updated_at = datetime.now(timezone.utc)
    if busy and int(run.attempts or 0) < _BUSY_LIMIT:
        run.status = "queued"
        session.flush()
        return False
    if work and not _enqueue_children(work):
        run.status = "running"
        session.flush()
        return False
    if message_id:
        seen.append(message_id)
        run.processed_message_ids = seen[-200:]
    for check in checks:
        refresh_check(session, run, check)
    run.status = _aggregate(checks)
    if run.status in {"done", "partial", "failed", "busy"}:
        run.finished_at = datetime.now(timezone.utc)
    session.flush()
    return True


def refresh_run(session: Session, run: DataQualityRun) -> DataQualityRun:
    """Update child-scan checkpoints when a run is read."""
    if run.status not in _OPEN and run.status != "running":
        return run
    checks = [dict(item) for item in (run.checks or [])]
    for check in checks:
        refresh_check(session, run, check)
    status = _aggregate(checks)
    if status != run.status or checks != list(run.checks or []):
        run.checks = checks
        run.status = status
        run.updated_at = datetime.now(timezone.utc)
        if status in {"done", "partial", "failed", "busy"}:
            run.finished_at = run.finished_at or datetime.now(timezone.utc)
        session.flush()
    return run


def retry_run(session: Session, run: DataQualityRun) -> DataQualityRun:
    """Queue a finished run again. The same row keeps its child scans."""
    if run.status in _OPEN:
        return run
    checks = []
    for item in run.checks or []:
        check = dict(item)
        if check.get("status") not in {"done", "unchanged", "skipped"}:
            check["status"] = "queued"
        checks.append(check)
    run.checks = checks
    run.status = "queued"
    run.finished_at = None
    run.updated_at = datetime.now(timezone.utc)
    session.flush()
    return run


def serialize_run(run: DataQualityRun) -> dict[str, Any]:
    """JSON shape for a data-quality run."""
    return {
        "id": str(run.id),
        "trigger": run.trigger,
        "import_job_id": None if run.import_job_id is None else str(run.import_job_id),
        "requested_by": run.requested_by,
        "scope": run.scope or {},
        "checks": list(run.checks or []),
        "status": run.status,
        "attempt": int(run.attempt or 1),
        "attempts": int(run.attempts or 0),
        "config_hash": run.config_hash,
        "as_of": _iso(run.as_of),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
    }


def scope_from_results(results: list[dict[str, Any]] | None) -> dict[str, list[str]]:
    """Organization and activity ids written by an import."""
    orgs: list[str] = []
    activities: list[str] = []
    for item in results or []:
        if not isinstance(item, dict) or item.get("status") not in {
            "created",
            "updated",
        }:
            continue
        entity_id = item.get("id")
        if not entity_id:
            continue
        if item.get("type") == "organizations":
            orgs.append(str(entity_id))
        elif item.get("type") == "activities":
            activities.append(str(entity_id))
    return {
        "organization_ids": sorted(set(orgs)),
        "activity_ids": sorted(set(activities)),
    }


def resolve_scope(session: Session, scope: dict[str, Any]) -> dict[str, list[str]]:
    """Turn a manual scope into sorted organization and activity ids."""
    kind = str(scope.get("kind") or "pending_review")
    if kind == "organization":
        org_id = _uuid(scope.get("org_id"), "org_id")
        if session.get(Organization, org_id) is None:
            raise ValidationError("org_id not found", field="org_id")
        return _ids([org_id], _activity_ids(session, [org_id]))
    if kind == "import":
        job_id = _uuid(scope.get("import_job_id"), "import_job_id")
        job = session.get(ImportJob, job_id)
        if job is None:
            raise NotFoundError("imports", str(job_id))
        return scope_from_results(job.results)
    if kind == "all":
        org_ids = list(
            session.scalars(select(Organization.id).order_by(Organization.id)).all()
        )
        return _ids(org_ids, _activity_ids(session, org_ids))
    if kind != "pending_review":
        raise ValidationError("Invalid scope", field="scope")
    org_ids = list(
        session.scalars(
            select(Organization.id)
            .where(Organization.review_status == "pending_review")
            .order_by(Organization.id)
        ).all()
    )
    return _ids(org_ids, _activity_ids(session, org_ids))


def _new_run(**kwargs: Any) -> DataQualityRun:
    checks = list(kwargs.pop("checks"))
    scope = kwargs.pop("scope")
    now = datetime.now(timezone.utc)
    return DataQualityRun(
        trigger=kwargs["trigger"],
        import_job_id=kwargs.get("import_job_id"),
        requested_by=kwargs.get("requested_by"),
        scope=scope,
        checks=[{"name": name, "status": "queued"} for name in checks],
        status="queued",
        config_hash=_config_hash(checks, scope),
        check_versions={name: CHECK_VERSIONS[name] for name in checks},
        idempotency_key=kwargs.get("idempotency_key"),
        as_of=now,
        created_at=now,
        updated_at=now,
    )


def _manual_checks(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValidationError("checks are required", field="checks")
    chosen = []
    for item in raw:
        if item not in _MANUAL:
            raise ValidationError("Unknown check", field="checks")
        if item not in chosen:
            chosen.append(item)
    return [name for name in _MANUAL if name in chosen]


def _config_hash(checks: list[str], scope: dict[str, Any]) -> str:
    return fingerprint(
        {
            "checks": list(checks),
            "scope": {
                "organization_ids": list(scope.get("organization_ids") or []),
                "activity_ids": list(scope.get("activity_ids") or []),
            },
            "versions": {name: CHECK_VERSIONS[name] for name in checks},
        }
    )


def _aggregate(checks: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("status") or "queued") for item in checks]
    if any(status in _OPEN for status in statuses):
        return "running"
    if any(status == "busy" for status in statuses):
        return "busy"
    if any(status == "failed" for status in statuses):
        return (
            "failed"
            if all(status in {"failed", "skipped"} for status in statuses)
            else "partial"
        )
    if any(status not in _TERMINAL_OK for status in statuses):
        return "partial"
    return "done"


def _enqueue_children(work: list[dict[str, Any]]) -> bool:
    from app.services.category_suggestions.events import (
        enqueue_location_batches,
        enqueue_scan_batches,
    )

    if not os.getenv("CATEGORY_SUGGESTION_QUEUE_URL", "").strip():
        logger.warning("CATEGORY_SUGGESTION_QUEUE_URL is not configured")
        return True
    try:
        for item in work:
            batches = item.get("batches") or []
            detail = item.get("detail") or {}
            scan_id = str(detail.get("scan_run_id") or "")
            if not scan_id or not batches:
                continue
            if item.get("batch_kind") == "location":
                enqueue_location_batches(scan_id, batches)
            else:
                enqueue_scan_batches(scan_id, batches)
    except Exception:
        logger.exception("Data quality child batches were not enqueued")
        return False
    return True


def _scope_empty(scope: dict[str, Any]) -> bool:
    return not scope.get("organization_ids") and not scope.get("activity_ids")


def _activity_ids(session: Session, org_ids: list) -> list:
    if not org_ids:
        return []
    return list(
        session.scalars(
            select(Activity.id)
            .where(Activity.org_id.in_(org_ids))
            .order_by(Activity.id)
        ).all()
    )


def _ids(org_ids, activity_ids) -> dict[str, list[str]]:
    return {
        "organization_ids": sorted(str(item) for item in org_ids),
        "activity_ids": sorted(str(item) for item in activity_ids),
    }


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a UUID", field=field) from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
