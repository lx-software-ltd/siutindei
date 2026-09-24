"""Ticket approval workflow helpers."""

from __future__ import annotations

from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_cognito import _add_user_to_manager_group
from app.db.models import (
    Location,
    Organization,
    OrganizationFeedback,
    Ticket,
    TicketType,
)
from app.db.repositories import (
    GeographicAreaRepository,
    LocationRepository,
    OrganizationFeedbackRepository,
    OrganizationRepository,
)
from app.exceptions import NotFoundError, ValidationError
from app.utils.feedback import feedback_stars_per_approval
from app.utils.logging import get_logger

logger = get_logger(__name__)


def apply_ticket_approval(
    session: Session,
    ticket: Ticket,
    body: Mapping[str, Any],
    reviewer_sub: str,
) -> tuple[Optional[Organization], int]:
    """Apply approval side-effects for a ticket and return derived outputs."""
    if ticket.ticket_type == TicketType.ACCESS_REQUEST:
        organization = _approve_access_request(session, ticket, body)
        return organization, 0

    if ticket.ticket_type == TicketType.ORGANIZATION_SUGGESTION:
        organization = _approve_suggestion(session, ticket, body, reviewer_sub)
        return organization, 0

    if ticket.ticket_type == TicketType.ORGANIZATION_FEEDBACK:
        feedback_star_delta = _approve_feedback(session, ticket)
        return None, feedback_star_delta

    return None, 0


def _approve_access_request(
    session: Session,
    ticket: Ticket,
    body: Mapping[str, Any],
) -> Optional[Organization]:
    """Approve an access request by assigning or creating an organization."""
    organization_id = body.get("organization_id")
    create_organization = body.get("create_organization", False)
    if not organization_id and not create_organization:
        raise ValidationError(
            "When approving an access request, you must either provide "
            "organization_id or set create_organization to true",
            field="organization_id",
        )
    if organization_id and create_organization:
        raise ValidationError(
            "Cannot both select an existing organization and create a new one",
            field="organization_id",
        )

    org_repo = OrganizationRepository(session)
    organization: Optional[Organization] = None
    if organization_id:
        try:
            parsed_org_id = UUID(str(organization_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Invalid organization_id",
                field="organization_id",
            ) from exc
        organization = org_repo.get_by_id(parsed_org_id)
        if organization is None:
            raise NotFoundError("organization", str(organization_id))
        organization.manager_id = ticket.submitter_id
        org_repo.update(organization)
        logger.info(
            f"Assigned organization {organization_id} to user {ticket.submitter_id}"
        )
    elif create_organization:
        organization = Organization(
            name=ticket.organization_name,
            description=None,
            manager_id=ticket.submitter_id,
            media_urls=[],
            review_status="approved",
        )
        org_repo.create(organization)
        logger.info(
            f"Created organization '{ticket.organization_name}' "
            f"for user {ticket.submitter_id}"
        )

    _add_user_to_manager_group(ticket.submitter_id)
    return organization


def _approve_suggestion(
    session: Session,
    ticket: Ticket,
    body: Mapping[str, Any],
    reviewer_sub: str,
) -> Optional[Organization]:
    """Approve an organization suggestion and optionally create an org."""
    create_organization = body.get("create_organization", False)
    if not create_organization:
        return None

    organization = _approve_org_creation(session, ticket, reviewer_sub)
    _approve_location_creation(session, ticket, organization)
    ticket.created_organization_id = organization.id
    logger.info(
        f"Created organization '{ticket.organization_name}' "
        f"from suggestion {ticket.ticket_id}"
    )
    return organization


def _approve_feedback(session: Session, ticket: Ticket) -> int:
    """Approve a feedback ticket and return star delta to apply."""
    if not ticket.organization_id:
        raise ValidationError(
            "organization_id is required for feedback tickets",
            field="organization_id",
        )
    if ticket.feedback_stars is None:
        raise ValidationError(
            "feedback_stars is required for feedback tickets",
            field="feedback_stars",
        )

    feedback_repo = OrganizationFeedbackRepository(session)
    feedback = OrganizationFeedback(
        organization_id=ticket.organization_id,
        submitter_id=ticket.submitter_id,
        submitter_email=ticket.submitter_email,
        stars=ticket.feedback_stars,
        label_ids=list(ticket.feedback_label_ids or []),
        description=ticket.feedback_text,
        source_ticket_id=ticket.ticket_id,
    )
    feedback_repo.create(feedback)
    if ticket.submitter_id:
        return feedback_stars_per_approval()
    return 0


def _approve_org_creation(
    session: Session,
    ticket: Ticket,
    reviewer_sub: str,
) -> Organization:
    """Create an organization from a suggestion ticket."""
    org_repo = OrganizationRepository(session)
    organization = Organization(
        name=ticket.organization_name,
        description=ticket.description,
        manager_id=reviewer_sub,
        media_urls=ticket.media_urls or [],
        review_status="approved",
    )
    org_repo.create(organization)
    return organization


def _approve_location_creation(
    session: Session,
    ticket: Ticket,
    organization: Organization,
) -> None:
    """Create a location for an approved suggestion when a district is present."""
    if not ticket.suggested_district:
        return

    geo_repo = GeographicAreaRepository(session)
    location_repo = LocationRepository(session)
    all_areas = geo_repo.get_all_flat(active_only=False)
    matched_area = next(
        (
            area
            for area in all_areas
            if area.level == "district" and area.name == ticket.suggested_district
        ),
        None,
    )
    if matched_area is None:
        matched_area = next(
            (area for area in all_areas if area.level == "district"),
            None,
        )

    if matched_area is None:
        return

    location = Location(
        org_id=organization.id,
        area_id=matched_area.id,
        address=ticket.suggested_address,
        lat=ticket.suggested_lat,
        lng=ticket.suggested_lng,
    )
    location_repo.create(location)
