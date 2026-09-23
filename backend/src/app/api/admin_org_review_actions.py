"""Approve, reject, reopen, and bulk-edit organizations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_imports_catalog import apply_listing_status, parse_org_status
from app.api.admin_request import _parse_body
from app.api.admin_resource_organization import (
    _serialize_organization,
    _update_organization,
)
from app.db.engine import get_engine
from app.db.models import Organization
from app.db.repositories import OrganizationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.org_review import (
    BULK_ORG_LIMIT,
    MAX_REVIEW_NOTES_LENGTH,
    ReviewIssue,
    snapshot_for_org,
)
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ACTIONS = ("approve", "reject", "reopen", "set_fields")
_DECISIONS = ("approve", "reject", "reopen")
_BULK_FIELDS = {
    "status",
    "manager_id",
    "source",
    "description_source",
    "review_notes",
    "phone_country_code",
    "phone_number",
    "email",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
}


class ReviewBlockedError(ValidationError):
    """Approve refused because release blockers are still present."""

    def __init__(self, issues: list[ReviewIssue]):
        super().__init__(
            "Organization has details that must be fixed before release",
            field="review_status",
        )
        self.issues = issues


def handle_decision(
    event: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    """POST /v1/admin/org-review/{id}/decision."""
    body = _require_object(_parse_body(event))
    action = _require_action(body.get("action"), _DECISIONS)
    org_id = _parse_uuid(resource_id, "id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        organization = session.get(Organization, org_id)
        if organization is None:
            raise NotFoundError("organizations", resource_id)
        try:
            _apply_decision(
                session,
                organization,
                action,
                force=_parse_force(body.get("force")),
                notes=body.get("notes") if "notes" in body else None,
                status=body.get("status"),
                reviewer_sub=_reviewer_sub(event),
                notes_provided="notes" in body,
            )
        except ReviewBlockedError as exc:
            return json_response(
                400,
                {
                    "error": exc.message,
                    "issues": [issue.to_dict() for issue in exc.issues],
                },
                event=event,
            )
        session.commit()
        session.refresh(organization)
        logger.info(
            "Organization review decision",
            extra={"action": action, "org_id": str(organization.id)},
        )
        return json_response(
            200,
            _serialize_organization(organization),
            event=event,
        )


def handle_bulk(event: Mapping[str, Any]) -> dict[str, Any]:
    """POST /v1/admin/org-review/bulk."""
    body = _require_object(_parse_body(event))
    action = _require_action(body.get("action"), _ACTIONS)
    org_ids = _parse_org_ids(body.get("org_ids"))
    fields = body.get("fields") if action == "set_fields" else None
    if action == "set_fields":
        fields = _parse_fields(fields)
    force = _parse_force(body.get("force"))
    notes = body.get("notes") if "notes" in body else None
    notes_provided = "notes" in body
    status = body.get("status")
    reviewer = _reviewer_sub(event)
    results: list[dict[str, Any]] = []
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = OrganizationRepository(session)
        for org_id in org_ids:
            results.append(
                _apply_one(
                    session,
                    repo,
                    org_id,
                    action=action,
                    force=force,
                    notes=notes,
                    notes_provided=notes_provided,
                    status=status,
                    fields=fields,
                    reviewer_sub=reviewer,
                )
            )
        session.commit()
    ok_count = sum(1 for item in results if item["status"] == "ok")
    logger.info(
        "Bulk organization review",
        extra={"action": action, "count": len(org_ids), "ok": ok_count},
    )
    return json_response(
        200,
        {"results": results},
        event=event,
    )


def _apply_one(
    session: Session,
    repo: OrganizationRepository,
    org_id: UUID,
    *,
    action: str,
    force: bool,
    notes: Any,
    notes_provided: bool,
    status: Any,
    fields: dict[str, Any] | None,
    reviewer_sub: str | None,
) -> dict[str, Any]:
    organization = session.get(Organization, org_id)
    if organization is None:
        return {
            "org_id": str(org_id),
            "status": "error",
            "message": "Organization not found",
        }
    try:
        with session.begin_nested():
            if action == "set_fields":
                _apply_fields(repo, organization, fields or {})
            else:
                _apply_decision(
                    session,
                    organization,
                    action,
                    force=force,
                    notes=notes,
                    status=status,
                    reviewer_sub=reviewer_sub,
                    notes_provided=notes_provided,
                )
            session.flush()
    except ReviewBlockedError as exc:
        return {
            "org_id": str(org_id),
            "status": "blocked",
            "message": exc.message,
            "issues": [issue.to_dict() for issue in exc.issues],
        }
    except ValidationError as exc:
        return {
            "org_id": str(org_id),
            "status": "error",
            "message": exc.message,
        }
    return {
        "org_id": str(org_id),
        "status": "ok",
        "review_status": organization.review_status,
    }


def _apply_decision(
    session: Session,
    organization: Organization,
    action: str,
    *,
    force: bool,
    notes: Any,
    status: Any,
    reviewer_sub: str | None,
    notes_provided: bool,
) -> None:
    if action == "approve":
        snapshot = snapshot_for_org(session, organization)
        blockers = [issue for issue in snapshot.issues if issue.severity == "blocker"]
        if blockers and not force:
            raise ReviewBlockedError(blockers)
        organization.review_status = "approved"
    elif action == "reject":
        organization.review_status = "rejected"
    else:
        organization.review_status = "pending_review"
    organization.reviewed_at = datetime.now(timezone.utc)
    organization.reviewed_by = reviewer_sub
    if notes_provided:
        organization.review_notes = _parse_notes(notes)
    if status not in (None, ""):
        parsed = parse_org_status(status)
        if parsed is None:
            raise ValidationError("Invalid status", field="status")
        apply_listing_status(organization, parsed, "owner")


def _apply_fields(
    repo: OrganizationRepository,
    organization: Organization,
    fields: dict[str, Any],
) -> None:
    notes = fields.get("review_notes") if "review_notes" in fields else None
    body = {key: value for key, value in fields.items() if key != "review_notes"}
    if "status" in body and "status_source" not in body:
        body["status_source"] = "owner"
    if body:
        _update_organization(repo, organization, body)
    if "review_notes" in fields:
        organization.review_notes = _parse_notes(notes)


def _parse_fields(fields: Any) -> dict[str, Any]:
    if not isinstance(fields, dict) or not fields:
        raise ValidationError("fields is required", field="fields")
    unknown = sorted(set(fields) - _BULK_FIELDS)
    if unknown:
        raise ValidationError(
            "Unsupported bulk fields: " + ", ".join(unknown),
            field="fields",
        )
    return fields


def _parse_org_ids(value: Any) -> list[UUID]:
    if not isinstance(value, list) or not value:
        raise ValidationError("org_ids is required", field="org_ids")
    if len(value) > BULK_ORG_LIMIT:
        raise ValidationError(
            f"org_ids cannot exceed {BULK_ORG_LIMIT}",
            field="org_ids",
        )
    return [_parse_uuid(item, "org_ids") for item in value]


def _require_action(value: Any, allowed: tuple[str, ...]) -> str:
    action = str(value or "").strip()
    if action not in allowed:
        raise ValidationError("Invalid action", field="action")
    return action


def _parse_force(value: Any) -> bool:
    if value in (None, False):
        return False
    if value is True:
        return True
    raise ValidationError("force must be a boolean", field="force")


def _parse_notes(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("notes must be a string", field="notes")
    text = value.strip()
    if len(text) > MAX_REVIEW_NOTES_LENGTH:
        raise ValidationError(
            f"notes exceeds {MAX_REVIEW_NOTES_LENGTH} characters",
            field="notes",
        )
    return text or None


def _reviewer_sub(event: Mapping[str, Any]) -> str | None:
    sub = _get_user_sub(event)
    return sub or None


def _require_object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    return body


def _parse_uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a UUID", field=field) from exc
