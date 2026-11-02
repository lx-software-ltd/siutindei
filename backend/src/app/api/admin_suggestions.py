"""Organization suggestion handlers."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.api.admin_auth import (
    _get_user_email,
    _get_user_sub,
    _set_session_audit_context,
)
from app.api.admin_request import _parse_body
from app.api.admin_resource_location import _validate_coordinates
from app.api.admin_tickets import _serialize_ticket
from app.api.admin_validators import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    _parse_media_urls,
    _validate_media_urls,
    _validate_string_length,
)
from app.db.engine import get_engine
from app.db.models import TicketType
from app.db.repositories import TicketRepository
from app.exceptions import ValidationError
from app.services.aws_clients import get_sns_client
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)
MAX_SUGGESTED_DISTRICT_LENGTH = 100


def _handle_user_organization_suggestion(
    event: Mapping[str, Any],
    method: str,
) -> dict[str, Any]:
    """Handle user organization suggestion operations."""
    user_sub = _get_user_sub(event)
    user_email = _get_user_email(event)

    if not user_sub:
        return json_response(401, {"error": "User identity not found"}, event=event)

    if method == "GET":
        return _get_user_suggestions(event, user_sub)

    if method == "POST":
        return _submit_organization_suggestion(event, user_sub, user_email)

    return json_response(405, {"error": "Method not allowed"}, event=event)


def _get_user_suggestions(
    event: Mapping[str, Any],
    user_sub: str,
) -> dict[str, Any]:
    """Get the current user's suggestion history."""
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = TicketRepository(session)

        suggestions = repo.find_by_submitter(
            user_sub, ticket_type=TicketType.ORGANIZATION_SUGGESTION, limit=50
        )

        pending = repo.find_pending_by_submitter(
            user_sub, TicketType.ORGANIZATION_SUGGESTION
        )

        return json_response(
            200,
            {
                "has_pending_suggestion": pending is not None,
                "suggestions": [_serialize_ticket(s) for s in suggestions],
            },
            event=event,
        )


def _submit_organization_suggestion(
    event: Mapping[str, Any],
    user_sub: str,
    user_email: str | None,
) -> dict[str, Any]:
    """Submit a new organization suggestion."""
    body = _parse_body(event)

    organization_name = _validate_string_length(
        body.get("organization_name"),
        "organization_name",
        MAX_NAME_LENGTH,
        required=True,
    )
    if organization_name is None:
        raise ValidationError(
            "organization_name is required", field="organization_name"
        )

    description = _validate_string_length(
        body.get("description"),
        "description",
        MAX_DESCRIPTION_LENGTH,
        required=False,
    )
    suggested_district = _validate_string_length(
        body.get("suggested_district"),
        "suggested_district",
        MAX_SUGGESTED_DISTRICT_LENGTH,
        required=False,
    )
    suggested_address = _validate_string_length(
        body.get("suggested_address"),
        "suggested_address",
        MAX_ADDRESS_LENGTH,
        required=False,
    )
    additional_notes = _validate_string_length(
        body.get("additional_notes"),
        "additional_notes",
        MAX_DESCRIPTION_LENGTH,
        required=False,
    )

    suggested_lat = body.get("suggested_lat")
    suggested_lng = body.get("suggested_lng")
    if suggested_lat is not None or suggested_lng is not None:
        _validate_coordinates(suggested_lat, suggested_lng)

    media_urls = _parse_media_urls(body.get("media_urls"))
    if media_urls:
        media_urls = _validate_media_urls(media_urls)

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = TicketRepository(session)

        existing = repo.find_pending_by_submitter(
            user_sub, TicketType.ORGANIZATION_SUGGESTION
        )
        if existing:
            return json_response(
                409,
                {
                    "error": "You already have a pending suggestion",
                    "suggestion": _serialize_ticket(existing),
                },
                event=event,
            )

        ticket_id = _generate_suggestion_ticket_id(session)

    topic_arn = os.getenv("SUGGESTION_TOPIC_ARN") or os.getenv(
        "MANAGER_REQUEST_TOPIC_ARN"
    )
    if not topic_arn:
        logger.error("SUGGESTION_TOPIC_ARN not configured")
        return json_response(
            500,
            {"error": "Service configuration error. Please contact support."},
            event=event,
        )

    return _publish_suggestion_to_sns(
        event=event,
        topic_arn=topic_arn,
        ticket_id=ticket_id,
        user_sub=user_sub,
        user_email=user_email or "unknown",
        organization_name=organization_name,
        description=description,
        suggested_district=suggested_district,
        suggested_address=suggested_address,
        suggested_lat=suggested_lat,
        suggested_lng=suggested_lng,
        additional_notes=additional_notes,
        media_urls=media_urls,
    )


def _generate_suggestion_ticket_id(session: Session) -> str:
    """Generate a unique progressive ticket ID in format S + 5 digits."""
    result = session.execute(
        sa_text(
            "SELECT MAX(CAST(SUBSTRING(ticket_id FROM 2) AS BIGINT)) "
            "FROM tickets "
            "WHERE ticket_id LIKE 'S%'"
        )
    ).scalar()

    next_number = (result or 0) + 1
    return f"S{next_number:05d}"


def _publish_suggestion_to_sns(
    event: Mapping[str, Any],
    topic_arn: str,
    ticket_id: str,
    user_sub: str,
    user_email: str,
    organization_name: str,
    description: str | None,
    suggested_district: str | None,
    suggested_address: str | None,
    suggested_lat: float | None,
    suggested_lng: float | None,
    additional_notes: str | None,
    media_urls: list[str],
) -> dict[str, Any]:
    """Publish organization suggestion to SNS."""
    sns_client = get_sns_client()
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(
                {
                    "event_type": "organization_suggestion.submitted",
                    "ticket_id": ticket_id,
                    "suggester_id": user_sub,
                    "suggester_email": user_email,
                    "organization_name": organization_name,
                    "description": description,
                    "suggested_district": suggested_district,
                    "suggested_address": suggested_address,
                    "suggested_lat": suggested_lat,
                    "suggested_lng": suggested_lng,
                    "additional_notes": additional_notes,
                    "media_urls": media_urls,
                }
            ),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "organization_suggestion.submitted",
                },
            },
        )
        logger.info(f"Published suggestion to SNS: {ticket_id}")
        return json_response(
            202,
            {
                "message": "Your suggestion has been submitted and is being processed",
                "ticket_id": ticket_id,
            },
            event=event,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.exception(f"Failed to publish suggestion to SNS: {exc}")
        return json_response(
            500,
            {"error": "Failed to submit suggestion. Please try again."},
            event=event,
        )
