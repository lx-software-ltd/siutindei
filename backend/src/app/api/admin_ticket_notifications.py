"""Ticket notification helpers."""

from __future__ import annotations

import os

from botocore.exceptions import BotoCoreError, ClientError

from app.db.models import Ticket, TicketType
from app.services.email import send_email, send_templated_email
from app.templates import (
    build_request_decision_template_data,
    render_request_decision_email,
)
from app.utils.logging import get_logger, mask_email

logger = get_logger(__name__)


def _send_ticket_decision_email(
    ticket: Ticket,
    action: str,
    admin_notes: str,
) -> None:
    """Send email notification to submitter about their ticket decision."""
    sender_email = os.getenv("SES_SENDER_EMAIL")

    if not sender_email:
        logger.warning("Email notification skipped: SES_SENDER_EMAIL not configured")
        return

    if not ticket.submitter_email or ticket.submitter_email == "unknown":
        logger.warning(
            f"Email notification skipped: No valid email for ticket {ticket.ticket_id}"
        )
        return

    try:
        if ticket.ticket_type == TicketType.ACCESS_REQUEST:
            template_name = os.getenv("SES_TEMPLATE_REQUEST_DECISION", "")
            template_data = build_request_decision_template_data(
                ticket_id=ticket.ticket_id,
                organization_name=ticket.organization_name,
                reviewed_at=(
                    ticket.reviewed_at.isoformat() if ticket.reviewed_at else "Unknown"
                ),
                action=action,
                admin_message=admin_notes if admin_notes else None,
            )
            email_content = render_request_decision_email(
                ticket_id=ticket.ticket_id,
                organization_name=ticket.organization_name,
                reviewed_at=(
                    ticket.reviewed_at.isoformat() if ticket.reviewed_at else "Unknown"
                ),
                action=action,
                admin_message=admin_notes if admin_notes else None,
            )

            if template_name:
                send_templated_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    template_name=template_name,
                    template_data=template_data,
                )
            else:
                send_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    subject=email_content.subject,
                    body_text=email_content.body_text,
                    body_html=email_content.body_html,
                )
        elif ticket.ticket_type == TicketType.ORGANIZATION_SUGGESTION:
            if action == "approve":
                subject = f"Your place suggestion {ticket.ticket_id} has been approved!"
                status_text = "APPROVED"
                status_message = (
                    "Great news! Your suggestion for "
                    f"'{ticket.organization_name}' has been approved "
                    "and added to our platform."
                )
            else:
                subject = f"Update on your place suggestion {ticket.ticket_id}"
                status_text = "DECLINED"
                status_message = (
                    f"Thank you for suggesting '{ticket.organization_name}'. "
                    "Unfortunately, we were unable to add this place "
                    "to our platform at this time."
                )

            body_text = f"{status_message}\n\n"
            if admin_notes:
                body_text += f"Note from admin: {admin_notes}\n"
            body_text += (
                "\nWe appreciate your contribution and encourage "
                "you to submit other suggestions in the future!"
            )

            template_name = os.getenv("SES_TEMPLATE_SUGGESTION_DECISION", "")
            if template_name:
                send_templated_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    template_name=template_name,
                    template_data={
                        "ticket_id": ticket.ticket_id,
                        "organization_name": ticket.organization_name,
                        "status_text": status_text,
                        "status_message": status_message,
                        "admin_message": admin_notes or "",
                    },
                )
            else:
                send_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    subject=subject,
                    body_text=body_text,
                )
        else:
            if action == "approve":
                subject = f"Your feedback has been approved! [{ticket.ticket_id}]"
                status_message = (
                    f"Thanks for your feedback about '{ticket.organization_name}'. "
                    "It has been approved by our team."
                )
            else:
                subject = f"Update on your feedback [{ticket.ticket_id}]"
                status_message = (
                    "Thank you for your feedback. "
                    "Unfortunately, we were unable to approve it at this time."
                )

            body_text = f"{status_message}\n\n"
            if admin_notes:
                body_text += f"Note from admin: {admin_notes}\n"
            body_text += (
                "\nYou can submit another feedback entry now that this "
                "one has been reviewed."
            )

            template_name = os.getenv("SES_TEMPLATE_FEEDBACK_DECISION", "")
            if template_name:
                send_templated_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    template_name=template_name,
                    template_data={
                        "ticket_id": ticket.ticket_id,
                        "organization_name": ticket.organization_name,
                        "status_message": status_message,
                        "admin_message": admin_notes or "",
                    },
                )
            else:
                send_email(
                    source=sender_email,
                    to_addresses=[ticket.submitter_email],
                    subject=subject,
                    body_text=body_text,
                )

        logger.info(
            f"Ticket decision email sent to "
            f"{mask_email(ticket.submitter_email)} "
            f"for {ticket.ticket_id}"
        )
    except (ClientError, BotoCoreError, ValueError) as exc:
        logger.error(f"Failed to send ticket decision email: {exc}")
