"""Ticket management handlers for admin APIs."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.api.admin_auth import (
    _get_user_email,
    _get_user_sub,
    _set_session_audit_context,
)
from app.api.admin_request import (
    _encode_cursor,
    _parse_body,
    _parse_cursor,
    _parse_uuid,
    _query_param,
    parse_limit,
)
from app.api.admin_ticket_notifications import _send_ticket_decision_email
from app.api.admin_ticket_review import apply_ticket_approval
from app.api.admin_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
)
from app.db.engine import get_engine
from app.db.models import (
    Ticket,
    TicketStatus,
    TicketType,
)
from app.db.repositories import (
    OrganizationRepository,
    TicketRepository,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.aws_clients import get_sns_client
from app.utils import json_response
from app.utils.feedback import safe_adjust_feedback_stars
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _handle_user_access_request(
    event: Mapping[str, Any],
    method: str,
) -> dict[str, Any]:
    """Handle user access request operations."""
    user_sub = _get_user_sub(event)
    user_email = _get_user_email(event)

    if not user_sub:
        return json_response(401, {"error": "User identity not found"}, event=event)

    if method == "GET":
        with Session(get_engine()) as session:
            _set_session_audit_context(session, event)
            org_repo = OrganizationRepository(session)
            ticket_repo = TicketRepository(session)

            user_orgs = org_repo.find_by_manager(user_sub)

            pending_ticket = ticket_repo.find_pending_by_submitter(
                user_sub, TicketType.ACCESS_REQUEST
            )

            return json_response(
                200,
                {
                    "has_pending_request": pending_ticket is not None,
                    "pending_request": _serialize_ticket(pending_ticket)
                    if pending_ticket
                    else None,
                    "organizations_count": len(user_orgs),
                },
                event=event,
            )

    if method == "POST":
        body = _parse_body(event)

        organization_name_validated = _validate_string_length(
            body.get("organization_name"),
            "organization_name",
            MAX_NAME_LENGTH,
            required=True,
        )
        if organization_name_validated is None:
            raise ValidationError(
                "organization_name is required", field="organization_name"
            )
        organization_name: str = organization_name_validated
        request_message = _validate_string_length(
            body.get("request_message"),
            "request_message",
            MAX_DESCRIPTION_LENGTH,
            required=False,
        )

        topic_arn = os.getenv("MANAGER_REQUEST_TOPIC_ARN")
        if not topic_arn:
            logger.error("MANAGER_REQUEST_TOPIC_ARN not configured")
            return json_response(
                500,
                {"error": "Service configuration error. Please contact support."},
                event=event,
            )

        with Session(get_engine()) as session:
            _set_session_audit_context(session, event)
            ticket_repo = TicketRepository(session)

            existing = ticket_repo.find_pending_by_submitter(
                user_sub, TicketType.ACCESS_REQUEST
            )
            if existing:
                return json_response(
                    409,
                    {
                        "error": "You already have a pending access request",
                        "request": _serialize_ticket(existing),
                    },
                    event=event,
                )

            ticket_id = _generate_ticket_id(session)

        return _publish_manager_request_to_sns(
            event=event,
            topic_arn=topic_arn,
            ticket_id=ticket_id,
            user_sub=user_sub,
            user_email=user_email or "unknown",
            organization_name=organization_name,
            request_message=request_message,
        )

    return json_response(405, {"error": "Method not allowed"}, event=event)


def _publish_manager_request_to_sns(
    event: Mapping[str, Any],
    topic_arn: str,
    ticket_id: str,
    user_sub: str,
    user_email: str,
    organization_name: str,
    request_message: str | None,
) -> dict[str, Any]:
    """Publish manager request to SNS for async processing."""
    sns_client = get_sns_client()

    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(
                {
                    "event_type": "manager_request.submitted",
                    "ticket_id": ticket_id,
                    "requester_id": user_sub,
                    "requester_email": user_email,
                    "organization_name": organization_name,
                    "request_message": request_message,
                }
            ),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "manager_request.submitted",
                },
            },
        )

        logger.info(f"Published manager request to SNS: {ticket_id}")

        return json_response(
            202,
            {
                "message": "Your request has been submitted and is being processed",
                "ticket_id": ticket_id,
            },
            event=event,
        )

    except (ClientError, BotoCoreError) as exc:
        logger.exception(f"Failed to publish manager request to SNS: {exc}")
        return json_response(
            500,
            {"error": "Failed to submit request. Please try again."},
            event=event,
        )


def _generate_ticket_id(session: Session) -> str:
    """Generate a unique progressive ticket ID in format R + 5 digits."""
    result = session.execute(
        sa_text(
            "SELECT MAX(CAST(SUBSTRING(ticket_id FROM 2) AS BIGINT)) "
            "FROM tickets "
            "WHERE ticket_id LIKE 'R%'"
        )
    ).scalar()

    next_number = (result or 0) + 1
    return f"R{next_number:05d}"


def _serialize_ticket(ticket: Ticket | None) -> dict[str, Any] | None:
    """Serialize a ticket for the API response."""
    if ticket is None:
        return None
    return {
        "id": str(ticket.id),
        "ticket_id": ticket.ticket_id,
        "ticket_type": ticket.ticket_type.value,
        "organization_name": ticket.organization_name,
        "message": ticket.message,
        "status": ticket.status.value,
        "submitter_email": ticket.submitter_email,
        "submitter_id": ticket.submitter_id,
        "created_at": (ticket.created_at.isoformat() if ticket.created_at else None),
        "reviewed_at": (ticket.reviewed_at.isoformat() if ticket.reviewed_at else None),
        "reviewed_by": ticket.reviewed_by,
        "admin_notes": ticket.admin_notes,
        "description": ticket.description,
        "suggested_district": ticket.suggested_district,
        "suggested_address": ticket.suggested_address,
        "suggested_lat": (
            float(ticket.suggested_lat) if ticket.suggested_lat else None
        ),
        "suggested_lng": (
            float(ticket.suggested_lng) if ticket.suggested_lng else None
        ),
        "media_urls": ticket.media_urls or [],
        "organization_id": (
            str(ticket.organization_id) if ticket.organization_id else None
        ),
        "feedback_stars": ticket.feedback_stars,
        "feedback_label_ids": [
            str(label_id) for label_id in (ticket.feedback_label_ids or [])
        ],
        "feedback_text": ticket.feedback_text,
        "created_organization_id": (
            str(ticket.created_organization_id)
            if ticket.created_organization_id
            else None
        ),
    }


def _handle_admin_tickets(
    event: Mapping[str, Any],
    method: str,
    ticket_id_param: str | None,
) -> dict[str, Any]:
    """Handle admin ticket management."""
    if method == "GET":
        return _list_admin_tickets(event)
    if method == "PUT" and ticket_id_param:
        return _review_ticket(event, ticket_id_param)
    return json_response(405, {"error": "Method not allowed"}, event=event)


def _list_admin_tickets(event: Mapping[str, Any]) -> dict[str, Any]:
    """List all tickets for admin review."""
    limit = parse_limit(event)

    status_filter = _query_param(event, "status")
    status = None
    if status_filter:
        try:
            status = TicketStatus(status_filter)
        except ValueError:
            raise ValidationError(
                f"Invalid status: {status_filter}. "
                "Must be pending, approved, or rejected",
                field="status",
            ) from None

    type_filter = _query_param(event, "ticket_type")
    ticket_type = None
    if type_filter:
        try:
            ticket_type = TicketType(type_filter)
        except ValueError:
            raise ValidationError(
                f"Invalid ticket_type: {type_filter}. "
                "Must be access_request, organization_suggestion, or "
                "organization_feedback",
                field="ticket_type",
            ) from None

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = TicketRepository(session)
        cursor = _parse_cursor(_query_param(event, "cursor"))
        rows = repo.find_all(
            ticket_type=ticket_type,
            status=status,
            limit=limit + 1,
            cursor=cursor,
        )
        has_more = len(rows) > limit
        trimmed = list(rows)[:limit]
        next_cursor = _encode_cursor(trimmed[-1].id) if has_more and trimmed else None

        pending_count = repo.count_pending(ticket_type=ticket_type)

        return json_response(
            200,
            {
                "items": [_serialize_ticket(row) for row in trimmed],
                "next_cursor": next_cursor,
                "pending_count": pending_count,
            },
            event=event,
        )


def _review_ticket(
    event: Mapping[str, Any],
    ticket_id_param: str,
) -> dict[str, Any]:
    """Approve or reject a ticket."""
    body = _parse_body(event)
    action = body.get("action")
    admin_notes = body.get("admin_notes") or body.get("message", "")

    if action not in ("approve", "reject"):
        raise ValidationError(
            "action must be 'approve' or 'reject'",
            field="action",
        )

    reviewer_sub = _get_user_sub(event)
    if not reviewer_sub:
        return json_response(401, {"error": "User identity not found"}, event=event)

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = TicketRepository(session)
        ticket = repo.get_by_id(_parse_uuid(ticket_id_param))

        if ticket is None:
            raise NotFoundError("ticket", ticket_id_param)

        if ticket.status != TicketStatus.PENDING:
            return json_response(
                409,
                {"error": f"Ticket has already been {ticket.status.value}"},
                event=event,
            )

        organization = None
        feedback_star_delta = 0

        if action == "approve":
            organization, feedback_star_delta = apply_ticket_approval(
                session,
                ticket,
                body,
                reviewer_sub,
            )

        new_status = (
            TicketStatus.APPROVED if action == "approve" else TicketStatus.REJECTED
        )
        ticket.status = new_status
        ticket.reviewed_at = datetime.now(UTC)
        ticket.reviewed_by = reviewer_sub
        ticket.admin_notes = admin_notes

        repo.update(ticket)
        session.commit()
        session.refresh(ticket)

        if organization:
            session.refresh(organization)

        if feedback_star_delta and ticket.submitter_id:
            safe_adjust_feedback_stars(ticket.submitter_id, feedback_star_delta)

        logger.info(f"Ticket {ticket_id_param} {action}d by {reviewer_sub}")

        _send_ticket_decision_email(ticket, action, admin_notes)

        response_data: dict[str, Any] = {
            "message": f"Ticket has been {action}d",
            "ticket": _serialize_ticket(ticket),
        }

        if organization:
            response_data["organization"] = {
                "id": str(organization.id),
                "name": organization.name,
            }

        return json_response(200, response_data, event=event)
