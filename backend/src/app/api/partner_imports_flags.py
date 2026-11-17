"""Parent verification, approval, and the stored partner import response."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_org_review_actions import (
    ReviewBlockedError,
    apply_review_decision,
)
from app.api.admin_request import _query_param
from app.api.admin_resource_organization import apply_parent_verified
from app.db.models import ImportJob, Organization
from app.exceptions import ValidationError

_FLAG_NAMES = ("dry_run", "mark_parent_verified", "approve")
_TRUE = frozenset({"true", "1"})
_FALSE = frozenset({"false", "0"})


def partner_import_object_key(
    payload: Mapping[str, Any],
    manager_id: str,
    flags: Mapping[str, bool],
) -> str:
    """Stable job key for one file, manager, and flag set.

    A repeat of that request finds the stored job. There is no S3
    object. The key stays outside ``admin/imports/``, so import history
    does not offer a download.
    """
    body = {
        "manager_id": manager_id,
        "dry_run": bool(flags["dry_run"]),
        "mark_parent_verified": bool(flags["mark_parent_verified"]),
        "approve": bool(flags["approve"]),
        "payload": payload,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"partner/imports/{digest}.json"


def import_flags(event: Mapping[str, Any]) -> dict[str, bool]:
    """Read the three query flags. Blank means false."""
    return {name: _flag(event, name) for name in _FLAG_NAMES}


def apply_import_flags(
    session: Session,
    results: list[dict[str, Any]],
    *,
    mark_parent_verified: bool,
    approve: bool,
    reviewer: str,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Verify and approve organisations this request created.

    An organisation that is already verified is left out of
    ``parent_verified``. Approval runs only while the review status is
    ``pending_review``. A rejected organisation stays rejected.
    """
    verified: list[str] = []
    approved: list[str] = []
    blocked: list[dict[str, Any]] = []
    if not mark_parent_verified and not approve:
        return verified, approved, blocked
    for org_id in _created_ids(results):
        organization = session.get(Organization, UUID(org_id))
        if organization is None:
            continue
        if mark_parent_verified and not organization.parent_verified:
            apply_parent_verified(organization, {"parent_verified": True})
            verified.append(org_id)
        if not approve:
            continue
        if organization.review_status == "rejected":
            blocked.append(
                {
                    "org_id": org_id,
                    "message": "Organization is rejected",
                    "issues": [],
                }
            )
            continue
        if organization.review_status == "approved":
            continue
        try:
            with session.begin_nested():
                apply_review_decision(
                    session,
                    organization,
                    "approve",
                    force=False,
                    notes=None,
                    status=None,
                    reviewer_sub=reviewer,
                    notes_provided=False,
                )
                session.flush()
        except ReviewBlockedError as exc:
            blocked.append(
                {
                    "org_id": org_id,
                    "message": exc.message,
                    "issues": [issue.to_dict() for issue in exc.issues],
                }
            )
            continue
        approved.append(org_id)
    return verified, approved, blocked


def partner_result(
    results: list[dict[str, Any]],
    verified: list[str],
    approved: list[str],
    blocked: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lists stored on the job and returned on the response."""
    return {
        "parent_verified": verified,
        "approved": approved,
        "blocked": blocked,
        "failed": _outcome_rows(results, "failed"),
        "skipped": _outcome_rows(results, "skipped"),
    }


def stamp_summary(summary: dict[str, Any], partner_result_body: dict[str, Any]) -> None:
    """Mark the summary as a partner import."""
    summary["allow_updates"] = False
    summary["source"] = "partner"
    summary["partner_result"] = partner_result_body


def public_body(job: ImportJob, *, replayed: bool) -> dict[str, Any]:
    """Response body for a stored or just-finished import job."""
    summary = dict(job.summary or {})
    partner = dict(summary.pop("partner_result", {}) or {})
    body = {
        "id": str(job.id),
        "object_key": job.object_key,
        "replayed": replayed,
        "summary": summary,
        "results": list(job.results or []),
        "file_warnings": list(job.file_warnings or []),
        "parent_verified": list(partner.get("parent_verified") or []),
        "approved": list(partner.get("approved") or []),
        "blocked": list(partner.get("blocked") or []),
        "failed": list(partner.get("failed") or []),
        "skipped": list(partner.get("skipped") or []),
    }
    run_id = summary.get("data_quality_run_id")
    if run_id:
        body["data_quality_run_id"] = run_id
    return body


def _created_ids(results: list[dict[str, Any]]) -> list[str]:
    return [
        str(result["id"])
        for result in results
        if result.get("type") == "organizations"
        and result.get("status") == "created"
        and result.get("id")
    ]


def _outcome_rows(results: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.get("status") != status:
            continue
        rows.append(
            {
                "type": result.get("type"),
                "id": result.get("id"),
                "key": result.get("key"),
                "path": result.get("path"),
                "status": status,
                "errors": result.get("errors") or [],
            }
        )
    return rows


def _flag(event: Mapping[str, Any], name: str) -> bool:
    raw = _query_param(event, name)
    if raw is None or raw == "":
        return False
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValidationError(f"{name} must be true or false", field=name)
