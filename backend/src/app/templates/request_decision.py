"""Access request decision email templates."""

from __future__ import annotations

from app.templates.types import EmailContent

DECISION_APPROVED_SUBJECT = (
    "[Siu Tin Dei] [{ticket_id}] Your Access Request Has Been Approved"
)
DECISION_REJECTED_SUBJECT = (
    "[Siu Tin Dei] [{ticket_id}] Your Access Request Has Been Declined"
)

DECISION_TEXT = """
[Siu Tin Dei] Access Request Update [{ticket_id}]

Your organization access request has been reviewed.

Status: {status_text}

Ticket ID: {ticket_id}
Organization Name: {organization_name}
Reviewed At: {reviewed_at}{admin_message_section}

{status_message}

If you have any questions, please contact support.
"""

DECISION_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 10px 0; color: #1a1a1a;">[Siu Tin Dei] Access Request Update</h2>
        <p style="margin: 0; font-size: 14px; color: #666;">
            Ticket ID: <strong style="font-family: monospace;">{ticket_id}</strong>
        </p>
    </div>

    <div style="background-color: {message_bg_color}; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
        <h3 style="margin: 0; color: {status_color};">Status: {status_text}</h3>
    </div>

    <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa; width: 140px;">
                Organization Name
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {organization_name}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Reviewed At
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {reviewed_at}
            </td>
        </tr>
        {admin_message_row}
    </table>

    <div style="background-color: {message_bg_color}; padding: 15px; border-radius: 5px; border-left: 4px solid {status_color};">
        <p style="margin: 0; font-size: 14px;">
            {status_message}
        </p>
    </div>

    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">

    <p style="font-size: 12px; color: #666; margin: 0;">
        If you have any questions, please contact support.
    </p>
</body>
</html>
"""

ADMIN_MESSAGE_ROW_HTML = """
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Admin Message
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {admin_message}
            </td>
        </tr>
"""


def render_request_decision_email(
    ticket_id: str,
    organization_name: str,
    reviewed_at: str,
    action: str,
    admin_message: str | None = None,
) -> EmailContent:
    """Render the request decision notification email."""
    is_approved = action == "approve"

    if is_approved:
        subject = DECISION_APPROVED_SUBJECT.format(ticket_id=ticket_id)
        status_text = "APPROVED"
        status_color = "#28a745"
        message_bg_color = "#d4edda"
        status_message = (
            "Congratulations! Your organization access request has been approved. "
            "You can now log in to the admin system and manage your organization."
        )
    else:
        subject = DECISION_REJECTED_SUBJECT.format(ticket_id=ticket_id)
        status_text = "DECLINED"
        status_color = "#dc3545"
        message_bg_color = "#f8d7da"
        status_message = (
            "We regret to inform you that your organization access request has been declined. "
            "If you believe this was a mistake, please contact support for more information."
        )

    if admin_message:
        admin_message_section_text = f"\nAdmin Message: {admin_message}"
    else:
        admin_message_section_text = ""

    if admin_message:
        admin_message_row = ADMIN_MESSAGE_ROW_HTML.format(admin_message=admin_message)
    else:
        admin_message_row = ""

    body_text = DECISION_TEXT.format(
        ticket_id=ticket_id,
        status_text=status_text,
        organization_name=organization_name,
        reviewed_at=reviewed_at,
        admin_message_section=admin_message_section_text,
        status_message=status_message,
    )

    body_html = DECISION_HTML.format(
        ticket_id=ticket_id,
        status_text=status_text,
        status_color=status_color,
        message_bg_color=message_bg_color,
        organization_name=organization_name,
        reviewed_at=reviewed_at,
        admin_message_row=admin_message_row,
        status_message=status_message,
    )

    return EmailContent(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


def build_request_decision_template_data(
    ticket_id: str,
    organization_name: str,
    reviewed_at: str,
    action: str,
    admin_message: str | None,
) -> dict[str, str]:
    """Build template data for an access request decision."""
    is_approved = action == "approve"
    if is_approved:
        status_text = "APPROVED"
        status_color = "#28a745"
        message_bg_color = "#d4edda"
        status_message = (
            "Congratulations! Your organization access request has been approved. "
            "You can now log in to the admin system and manage your organization."
        )
    else:
        status_text = "DECLINED"
        status_color = "#dc3545"
        message_bg_color = "#f8d7da"
        status_message = (
            "We regret to inform you that your organization access request has been declined. "
            "If you believe this was a mistake, please contact support for more information."
        )

    if admin_message:
        admin_message_section_text = f"\nAdmin Message: {admin_message}"
        admin_message_row = ADMIN_MESSAGE_ROW_HTML.format(admin_message=admin_message)
    else:
        admin_message_section_text = ""
        admin_message_row = ""

    return {
        "ticket_id": ticket_id,
        "organization_name": organization_name,
        "reviewed_at": reviewed_at,
        "status_text": status_text,
        "status_color": status_color,
        "message_bg_color": message_bg_color,
        "status_message": status_message,
        "admin_message_section": admin_message_section_text,
        "admin_message_row": admin_message_row,
    }
