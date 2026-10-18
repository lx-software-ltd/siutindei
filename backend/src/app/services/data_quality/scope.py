"""Organization and activity scope for a data-quality run."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, ImportJob, Organization
from app.exceptions import NotFoundError, ValidationError


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


def scope_is_empty(scope: dict[str, Any]) -> bool:
    """True when the scope names no organization and no activity."""
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
