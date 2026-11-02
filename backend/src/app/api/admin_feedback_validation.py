"""Validation helpers shared by admin feedback handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.api.admin_request import _parse_uuid
from app.api.admin_validators import MAX_FEEDBACK_LABELS_COUNT
from app.db.repositories import FeedbackLabelRepository, OrganizationRepository
from app.exceptions import NotFoundError, ValidationError


def parse_feedback_stars(value: Any) -> int:
    """Parse feedback stars from request payload."""
    try:
        stars = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("stars must be an integer", field="stars") from exc
    if stars < 0 or stars > 5:
        raise ValidationError("stars must be between 0 and 5", field="stars")
    return stars


def parse_label_ids(value: Any) -> list[UUID]:
    """Normalize feedback label IDs."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("label_ids must be a list", field="label_ids")
    ids: list[UUID] = []
    seen: set[str] = set()
    for item in value:
        parsed = _parse_uuid(str(item))
        key = str(parsed)
        if key in seen:
            continue
        seen.add(key)
        ids.append(parsed)
    if len(ids) > MAX_FEEDBACK_LABELS_COUNT:
        raise ValidationError(
            f"label_ids cannot exceed {MAX_FEEDBACK_LABELS_COUNT} items",
            field="label_ids",
        )
    return ids


def validate_feedback_labels(
    repo: FeedbackLabelRepository,
    label_ids: list[UUID],
) -> None:
    """Validate that feedback labels exist."""
    if not label_ids:
        return
    labels = list(repo.get_by_ids(label_ids))
    if len(labels) != len(label_ids):
        raise ValidationError("One or more labels do not exist", field="label_ids")


def require_org_id(body: Mapping[str, Any]) -> UUID:
    """Parse and require an organization_id."""
    org_id_raw = body.get("organization_id")
    if not org_id_raw:
        raise ValidationError("organization_id is required", field="organization_id")
    return _parse_uuid(str(org_id_raw))


def ensure_organization(repo: OrganizationRepository, org_id: UUID) -> None:
    """Raise if organization does not exist."""
    if repo.get_by_id(org_id) is None:
        raise NotFoundError("organization", str(org_id))
