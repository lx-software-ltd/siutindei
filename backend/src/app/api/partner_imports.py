"""Catalog import for a full-access crud partner key."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_imports_fields import manager_ids_match
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_jobs import (
    begin_import_job,
    fail_import_job,
    find_import_job_by_key,
    finish_import_job,
    store_import_job,
)
from app.api.admin_request import _parse_body, _query_param
from app.api.partner_auth import (
    PartnerContext,
    partner_actor,
    require_crud,
    require_full_access,
)
from app.api.partner_imports_flags import (
    apply_import_flags,
    import_flags,
    partner_import_object_key,
    partner_result,
    public_body,
    stamp_summary,
)
from app.db.engine import get_engine
from app.db.models import ImportJob
from app.exceptions import ValidationError
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

# The admin Lambda stops at 120 seconds. A running job older than that
# plus a short buffer belongs to a request that can no longer finish.
_RUNNING_STALE_AFTER = timedelta(seconds=150)


def handle_partner_imports(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    partner: PartnerContext,
) -> dict[str, Any]:
    """Import a catalog file with the full-access crud partner key.

    The body is the admin import JSON. ``manager_id``, ``dry_run``,
    ``mark_parent_verified``, and ``approve`` are query parameters.
    The file cannot set the parent-verified flag or the review status.
    Those flags apply only to organisations this request creates.
    The same file and flags return the stored import job.
    """
    require_full_access(partner)
    require_crud(partner)
    if method != "POST" or resource_id:
        return json_response(404, {"error": "Not found"}, event=event)

    flags = import_flags(event)
    payload = _parse_body(event)
    if not isinstance(payload, dict):
        raise ValidationError("Import file must be a JSON object")
    manager_id = resolve_import_manager(
        payload,
        _query_param(event, "manager_id"),
        _catalog_manager_id(),
    )
    if flags["dry_run"] and (flags["mark_parent_verified"] or flags["approve"]):
        raise ValidationError(
            "mark_parent_verified and approve require a live import",
            field="dry_run",
        )

    object_key = partner_import_object_key(payload, manager_id, flags)
    actor = partner_actor(event, partner)
    if flags["dry_run"]:
        return _dry_run(event, payload, manager_id, object_key)
    return _live(
        event,
        payload,
        manager_id,
        flags,
        object_key,
        actor,
    )


def resolve_import_manager(
    payload: dict[str, Any],
    requested: str | None,
    catalog: str | None,
) -> str:
    """Fill ``default_manager_id`` and return the catalog manager.

    A placeholder or blank file value is absent. The query value wins,
    then a UUID already in the file, then ``BOARD_CATALOG_MANAGER_ID``.
    When the environment variable is set, every other value must match
    it. The check happens before the import writes.
    """
    file_manager = _uuid_or_none(payload.get("default_manager_id"))
    chosen = _uuid_or_none(requested) or file_manager or _uuid_or_none(catalog)
    if chosen is None:
        raise ValidationError(
            "default_manager_id must be a UUID",
            field="default_manager_id",
        )
    if catalog and not manager_ids_match(chosen, catalog):
        raise ValidationError(
            "manager_id must be the catalog manager",
            field="manager_id",
        )
    if file_manager and not manager_ids_match(file_manager, chosen):
        raise ValidationError(
            "manager_id must match default_manager_id",
            field="manager_id",
        )
    payload["default_manager_id"] = chosen
    return chosen


def _live(
    event: Mapping[str, Any],
    payload: dict[str, Any],
    manager_id: str,
    flags: Mapping[str, bool],
    object_key: str,
    actor: str,
) -> dict[str, Any]:
    with Session(get_engine()) as session:
        state, job = _claim(session, object_key)
        if state == "running":
            return json_response(
                409,
                {
                    "error": "Import is already running",
                    "id": str(job.id),
                    "object_key": object_key,
                },
                event=event,
            )
        if state == "done":
            return json_response(
                200,
                public_body(job, replayed=True),
                event=event,
            )
        job_id = str(job.id)
        session.commit()

    enqueue_ids: list[str] = []
    run_id = None
    try:
        with Session(get_engine()) as session:
            _set_session_audit_context(session, event, user_id=actor)
            from app.services.catalog_version_match import set_import_job_context

            set_import_job_context(session, job_id)
            file_warnings: list[str] = []
            summary, results = process_import_payload(
                session,
                payload,
                file_warnings,
                dry_run=False,
                allow_org_updates=False,
                catalog_manager_id=manager_id,
                import_job_id=job_id,
                commit_batch=False,
            )
            from app.services.category_suggestions.resolve import (
                import_enrichment_ids,
            )

            enqueue_ids = import_enrichment_ids(dry_run=False)
            verified, approved, blocked = apply_import_flags(
                session,
                results,
                mark_parent_verified=flags["mark_parent_verified"],
                approve=flags["approve"],
                reviewer=actor,
            )
            stamp_summary(
                summary,
                partner_result(results, verified, approved, blocked),
            )
            job = finish_import_job(
                session,
                job_id,
                summary=summary,
                results=results,
                file_warnings=file_warnings,
            )
            from app.services.data_quality.runs import stage_import_run

            run_id = stage_import_run(
                session,
                import_job_id=job.id,
                results=results,
                requested_by=actor,
            )
            if run_id:
                summary["data_quality_run_id"] = run_id
                job.summary = dict(summary)
            body = public_body(job, replayed=False)
            session.commit()
    except Exception as exc:
        from app.services.category_suggestions.resolve import (
            take_import_category_enqueues,
        )

        take_import_category_enqueues()
        _record_failure(job_id, exc)
        raise

    _enqueue_follow_up(enqueue_ids, run_id)
    _log_import(
        dry_run=False,
        summary=body["summary"],
        verified=body["parent_verified"],
        approved=body["approved"],
        blocked=body["blocked"],
    )
    return json_response(200, body, event=event)


def _dry_run(
    event: Mapping[str, Any],
    payload: dict[str, Any],
    manager_id: str,
    object_key: str,
) -> dict[str, Any]:
    with Session(get_engine()) as session:
        existing = find_import_job_by_key(session, object_key)
        if existing is not None and existing.dry_run and existing.status == "completed":
            return json_response(
                200,
                public_body(existing, replayed=True),
                event=event,
            )
        file_warnings: list[str] = []
        summary, results = process_import_payload(
            session,
            payload,
            file_warnings,
            dry_run=True,
            allow_org_updates=False,
            catalog_manager_id=manager_id,
        )
        from app.services.category_suggestions.resolve import import_enrichment_ids

        import_enrichment_ids(dry_run=True)
        session.rollback()
        stamp_summary(summary, partner_result(results, [], [], []))
        job = store_import_job(
            session,
            object_key,
            dry_run=True,
            summary=summary,
            results=results,
            file_warnings=file_warnings,
        )
        body = public_body(job, replayed=False)
        session.commit()

    _log_import(
        dry_run=True,
        summary=body["summary"],
        verified=[],
        approved=[],
        blocked=[],
    )
    return json_response(200, body, event=event)


def _claim(session: Session, object_key: str) -> tuple[str, ImportJob]:
    """Return ``running``, ``done``, or ``start`` for this file and flags."""
    existing = find_import_job_by_key(session, object_key)
    if existing is not None:
        return _claim_existing(session, existing)
    try:
        with session.begin_nested():
            job = begin_import_job(session, object_key, source="partner")
        return "start", job
    except IntegrityError:
        existing = find_import_job_by_key(session, object_key)
        if existing is None:
            raise
        return _claim_existing(session, existing)


def _claim_existing(session: Session, job: ImportJob) -> tuple[str, ImportJob]:
    if job.status == "completed":
        return "done", job
    if job.status == "running" and _running_is_live(job):
        return "running", job
    started = begin_import_job(session, job.object_key, source="partner")
    return "start", started


def _running_is_live(job: ImportJob) -> bool:
    updated = job.updated_at
    if updated is None:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return datetime.now(UTC) - updated < _RUNNING_STALE_AFTER


def _enqueue_follow_up(enqueue_ids: list[str], run_id: str | None) -> None:
    if enqueue_ids:
        from app.services.category_suggestions.events import enqueue_enrichment

        try:
            enqueue_enrichment(enqueue_ids)
        except Exception:
            logger.exception("Category suggestion enqueue failed")
    if run_id:
        from app.services.data_quality.runs import enqueue_staged_run

        enqueue_staged_run(run_id)


def _record_failure(job_id: str, exc: BaseException) -> None:
    logger.info(
        "Partner catalog import failed",
        extra={"error_type": type(exc).__name__},
    )
    try:
        with Session(get_engine()) as session:
            fail_import_job(session, job_id, type(exc).__name__)
            session.commit()
    except Exception:
        logger.info(
            "Partner catalog import failure status was not saved",
            extra={"error_type": type(exc).__name__},
        )


def _log_import(
    *,
    dry_run: bool,
    summary: Mapping[str, Any],
    verified: list[str],
    approved: list[str],
    blocked: list[dict[str, Any]],
) -> None:
    organizations = summary.get("organizations")
    created = organizations.get("created", 0) if isinstance(organizations, dict) else 0
    logger.info(
        "Partner catalog import",
        extra={
            "dry_run": dry_run,
            "organizations_created": created,
            "verified": len(verified),
            "approved": len(approved),
            "blocked": len(blocked),
        },
    )


def _catalog_manager_id() -> str | None:
    value = os.getenv("BOARD_CATALOG_MANAGER_ID", "").strip()
    return value or None


def _uuid_or_none(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return str(UUID(value.strip()))
    except (ValueError, TypeError):
        return None
