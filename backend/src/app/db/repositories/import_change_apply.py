"""Write one accepted import field through the admin update path."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ImportChangeProposal
from app.exceptions import ValidationError


def write_accepted_field(
    session: Session, row: ImportChangeProposal, entity: Any
) -> None:
    """Apply one queued field. Owner listing status is left alone."""
    writer = {
        "organization": _write_organization,
        "location": _write_location,
        "activity": _write_activity,
        "pricing": _write_pricing,
    }.get(row.entity_type, _write_schedule)
    writer(session, row, entity)


def _write_organization(
    session: Session, row: ImportChangeProposal, entity: Any
) -> None:
    from app.api.admin_resource_organization import _update_organization
    from app.db.repositories import OrganizationRepository

    if row.field == "status" and entity.status_source == "owner":
        raise ValidationError(
            "owner listing status preserved; importer status ignored",
            field="status",
        )
    body = {row.field: row.proposed_value}
    if row.field == "status":
        body["status_source"] = "importer"
    if row.field == "phone_number":
        body.setdefault("phone_country_code", entity.phone_country_code)
    if row.field == "phone_country_code":
        body.setdefault("phone_number", entity.phone_number)
    repo = OrganizationRepository(session)
    repo.update(_update_organization(repo, entity, body))


def _write_location(session: Session, row: ImportChangeProposal, entity: Any) -> None:
    from app.api.admin_resource_location import _update_location
    from app.db.repositories import LocationRepository

    repo = LocationRepository(session)
    repo.update(_update_location(repo, entity, {row.field: row.proposed_value}))


def _write_activity(session: Session, row: ImportChangeProposal, entity: Any) -> None:
    from app.api.admin_resource_activity import _update_activity
    from app.db.age_bounds import inclusive_age_bounds
    from app.db.repositories import ActivityRepository

    body = {row.field: row.proposed_value}
    if row.field in {"age_min", "age_max"}:
        age_min, age_max = inclusive_age_bounds(entity.age_range)
        body.setdefault("age_min", age_min)
        body.setdefault("age_max", age_max)
    _resolve_accepted_category(session, row, body)
    repo = ActivityRepository(session)
    repo.update(_update_activity(repo, entity, body))


def _resolve_accepted_category(
    session: Session, row: ImportChangeProposal, body: dict[str, Any]
) -> None:
    if row.field != "source_category_name" or not row.proposed_value:
        return
    from app.db.models.category_suggestion import PENDING_CATEGORY_ID
    from app.services.category_suggestions.capture import ensure_pending_category
    from app.services.category_suggestions.resolve import resolve_category_name

    resolution = resolve_category_name(session, str(row.proposed_value))
    if resolution.category_id is not None:
        body["category_id"] = str(resolution.category_id)
        return
    if resolution.capture:
        ensure_pending_category(session)
        body["category_id"] = str(PENDING_CATEGORY_ID)


def _write_pricing(session: Session, row: ImportChangeProposal, entity: Any) -> None:
    from app.api.admin_resource_pricing import _update_pricing
    from app.db.repositories import ActivityPricingRepository

    repo = ActivityPricingRepository(session)
    repo.update(_update_pricing(repo, entity, {row.field: row.proposed_value}))


def _write_schedule(session: Session, row: ImportChangeProposal, entity: Any) -> None:
    from app.api.admin_resource_schedule import _update_schedule
    from app.db.repositories import ActivityScheduleRepository

    repo = ActivityScheduleRepository(session)
    repo.update(_update_schedule(repo, entity, {row.field: row.proposed_value}))
