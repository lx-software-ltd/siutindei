"""Lambda handler for processing ticket submissions from SQS.

This Lambda is triggered by SQS messages that originate from the SNS topic.
It processes submissions asynchronously:
1. Parses the SNS message from SQS
2. Stores the ticket in the database (with idempotency check)
3. Sends email notification to support/admin

The decoupled architecture provides:
- Automatic retries (3 attempts before DLQ)
- Fault tolerance (email failures don't block DB writes)
- Scalability (can process multiple submissions concurrently)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import Ticket, TicketType
from app.db.repositories import FeedbackLabelRepository, TicketRepository
from app.services.email import send_email, send_templated_email
from app.templates import (
    build_new_feedback_template_data,
    build_new_request_template_data,
    build_new_suggestion_template_data,
    render_new_feedback_email,
    render_new_request_email,
    render_new_suggestion_email,
)
from app.utils.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Map SNS event types to ticket types
EVENT_TYPE_MAP = {
    "manager_request.submitted": TicketType.ACCESS_REQUEST,
    "organization_suggestion.submitted": TicketType.ORGANIZATION_SUGGESTION,
    "organization_feedback.submitted": TicketType.ORGANIZATION_FEEDBACK,
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process ticket messages from SQS.

    Each SQS message contains an SNS notification with an event_type field
    that maps to a ticket_type in the unified tickets table.

    Args:
        event: SQS event containing records to process.
        context: Lambda context object.

    Returns:
        Response with processing statistics.

    Raises:
        Exception: If processing fails (triggers SQS retry).
    """
    processed = 0
    skipped = 0

    for record in event.get("Records", []):
        try:
            # Parse SNS message wrapped in SQS record
            sqs_body = json.loads(record["body"])

            # SNS wraps the actual message in a "Message" field
            message_str = sqs_body.get("Message", "{}")
            message = json.loads(message_str)

            event_type = message.get("event_type")
            ticket_type = EVENT_TYPE_MAP.get(event_type)
            if ticket_type is None:
                logger.info(f"Skipping unsupported event type: {event_type}")
                skipped += 1
                continue

            ticket_id = message.get("ticket_id")
            if not ticket_id:
                logger.warning("Message missing ticket_id, skipping")
                skipped += 1
                continue

            logger.info(f"Processing {event_type}: {ticket_id}")

            # Store in database with idempotency check
            ticket = _store_ticket(message, ticket_type)

            if ticket is None:
                logger.info(f"Ticket {ticket_id} already exists, skipping")
                skipped += 1
                continue

            # Send email notification (non-blocking)
            _send_notification_email(ticket)

            processed += 1
            logger.info(f"Successfully processed {event_type}: {ticket_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            # Re-raise to trigger retry
            raise
        except Exception as e:
            logger.exception(f"Failed to process record: {e}")
            # Re-raise to trigger SQS retry / DLQ
            raise

    result = {
        "statusCode": 200,
        "body": json.dumps(
            {
                "processed": processed,
                "skipped": skipped,
            }
        ),
    }
    logger.info(f"Processing complete: {result}")
    return result


def _store_ticket(
    message: dict[str, Any],
    ticket_type: TicketType,
) -> Ticket | None:
    """Store ticket in database with idempotency check.

    Args:
        message: Parsed SNS message containing ticket data.
        ticket_type: The type of ticket to create.

    Returns:
        The created Ticket, or None if already exists.
    """
    ticket_id = message["ticket_id"]

    # Normalize field names: access requests use requester_*, suggestions
    # use suggester_*. The unified model uses submitter_*.
    submitter_id = (
        message.get("submitter_id")
        or message.get("requester_id")
        or message.get("suggester_id")
    )
    submitter_email = (
        message.get("submitter_email")
        or message.get("requester_email")
        or message.get("suggester_email")
    )

    with Session(get_engine()) as session:
        repo = TicketRepository(session)

        # Idempotency check: skip if already processed
        existing = repo.find_by_ticket_id(ticket_id)
        if existing:
            return None

        # Build the ticket
        ticket = Ticket(
            ticket_id=ticket_id,
            ticket_type=ticket_type,
            submitter_id=submitter_id,
            submitter_email=submitter_email,
            organization_name=message["organization_name"],
            message=message.get("request_message")
            or message.get("additional_notes")
            or message.get("message"),
        )

        # Suggestion-specific fields
        if ticket_type == TicketType.ORGANIZATION_SUGGESTION:
            ticket.description = message.get("description")
            ticket.suggested_district = message.get("suggested_district")
            ticket.suggested_address = message.get("suggested_address")
            ticket.suggested_lat = message.get("suggested_lat")
            ticket.suggested_lng = message.get("suggested_lng")
            ticket.media_urls = message.get("media_urls", [])
        if ticket_type == TicketType.ORGANIZATION_FEEDBACK:
            ticket.organization_id = message.get("organization_id")
            ticket.feedback_stars = message.get("feedback_stars")
            ticket.feedback_label_ids = message.get("feedback_label_ids", [])
            ticket.feedback_text = message.get("feedback_text")

        repo.create(ticket)
        session.commit()
        session.refresh(ticket)

        logger.info(
            f"Stored ticket in database: {ticket_id} (type={ticket_type.value})"
        )
        return ticket


def _send_notification_email(ticket: Ticket) -> None:
    """Send email notification for a new ticket.

    Dispatches to the appropriate email template based on ticket type.
    This is a best-effort operation - failures are logged but don't
    cause the overall processing to fail (DB write already succeeded).

    Args:
        ticket: The ticket to notify about.
    """
    support_email = os.getenv("SUPPORT_EMAIL")
    sender_email = os.getenv("SES_SENDER_EMAIL")

    if not support_email or not sender_email:
        logger.warning(
            "Email notification skipped: SUPPORT_EMAIL or "
            "SES_SENDER_EMAIL not configured"
        )
        return

    try:
        submitted_at = (
            ticket.created_at.isoformat()
            if ticket.created_at
            else datetime.now(UTC).isoformat()
        )

        if ticket.ticket_type == TicketType.ACCESS_REQUEST:
            template_name = os.getenv("SES_TEMPLATE_NEW_ACCESS_REQUEST", "")
            template_data = build_new_request_template_data(
                ticket_id=ticket.ticket_id,
                requester_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                request_message=ticket.message,
                submitted_at=submitted_at,
            )
            email_content = render_new_request_email(
                ticket_id=ticket.ticket_id,
                requester_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                request_message=ticket.message,
                submitted_at=submitted_at,
            )
        elif ticket.ticket_type == TicketType.ORGANIZATION_SUGGESTION:
            template_name = os.getenv("SES_TEMPLATE_NEW_SUGGESTION", "")
            template_data = build_new_suggestion_template_data(
                ticket_id=ticket.ticket_id,
                suggester_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                description=ticket.description,
                district=ticket.suggested_district,
                address=ticket.suggested_address,
                additional_notes=ticket.message,
                submitted_at=submitted_at,
            )
            email_content = render_new_suggestion_email(
                ticket_id=ticket.ticket_id,
                suggester_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                description=ticket.description,
                district=ticket.suggested_district,
                address=ticket.suggested_address,
                additional_notes=ticket.message,
                submitted_at=submitted_at,
            )
        else:
            label_names = _resolve_feedback_labels(ticket.feedback_label_ids or [])
            template_name = os.getenv("SES_TEMPLATE_NEW_FEEDBACK", "")
            template_data = build_new_feedback_template_data(
                ticket_id=ticket.ticket_id,
                submitter_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                stars=ticket.feedback_stars,
                labels=label_names,
                description=ticket.feedback_text,
                submitted_at=submitted_at,
            )
            email_content = render_new_feedback_email(
                ticket_id=ticket.ticket_id,
                submitter_email=ticket.submitter_email,
                organization_name=ticket.organization_name,
                stars=ticket.feedback_stars,
                labels=label_names,
                description=ticket.feedback_text,
                submitted_at=submitted_at,
            )

        if template_name:
            send_templated_email(
                source=sender_email,
                to_addresses=[support_email],
                template_name=template_name,
                template_data=template_data,
            )
        else:
            send_email(
                source=sender_email,
                to_addresses=[support_email],
                subject=email_content.subject,
                body_text=email_content.body_text,
                body_html=email_content.body_html,
            )
        logger.info(f"Notification email sent for {ticket.ticket_id}")

    except Exception as e:
        # Log but don't re-raise - DB write succeeded, email is secondary
        logger.error(f"Failed to send notification email for {ticket.ticket_id}: {e}")


def _resolve_feedback_labels(label_ids: list[Any]) -> list[str]:
    """Resolve feedback label IDs to names for email output."""
    if not label_ids:
        return []
    parsed_ids: list[UUID] = []
    for label_id in label_ids:
        try:
            parsed_ids.append(UUID(str(label_id)))
        except (TypeError, ValueError):
            continue
    if not parsed_ids:
        return []
    with Session(get_engine()) as session:
        repo = FeedbackLabelRepository(session)
        labels = repo.get_by_ids(parsed_ids)
        return [label.name for label in labels if label.name]
