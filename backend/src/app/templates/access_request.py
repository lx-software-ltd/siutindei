"""Access request email templates."""

from __future__ import annotations

from app.templates.types import EmailContent

NEW_REQUEST_SUBJECT = (
    "[Siu Tin Dei] [{ticket_id}] New Access Request: {organization_name}"
)

NEW_REQUEST_TEXT = """
[Siu Tin Dei] Access Request [{ticket_id}]

A new organization access request has been submitted.

Ticket ID: {ticket_id}
Requester Email: {requester_email}
Organization Name: {organization_name}
Request Message: {request_message}
Submitted At: {submitted_at}

Please review this request in the admin dashboard.
"""

NEW_REQUEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 10px 0; color: #1a1a1a;">[Siu Tin Dei] Access Request</h2>
        <p style="margin: 0; font-size: 14px; color: #666;">
            Ticket ID: <strong style="font-family: monospace;">{ticket_id}</strong>
        </p>
    </div>

    <p style="margin-bottom: 20px;">A new organization access request has been submitted and requires your review.</p>

    <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa; width: 140px;">
                Ticket ID
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-family: monospace;">
                <strong>{ticket_id}</strong>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Requester Email
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                <a href="mailto:{requester_email}" style="color: #0066cc;">{requester_email}</a>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Organization Name
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {organization_name}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Request Message
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {request_message}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Submitted At
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {submitted_at}
            </td>
        </tr>
    </table>

    <div style="background-color: #e7f3ff; padding: 15px; border-radius: 5px; border-left: 4px solid #0066cc;">
        <p style="margin: 0; font-size: 14px;">
            Please review this request in the admin dashboard and take appropriate action.
        </p>
    </div>

    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">

    <p style="font-size: 12px; color: #666; margin: 0;">
        This is an automated message from Siu Tin Dei. Please do not reply directly to this email.
    </p>
</body>
</html>
"""


def render_new_request_email(
    ticket_id: str,
    requester_email: str,
    organization_name: str,
    request_message: str | None,
    submitted_at: str,
) -> EmailContent:
    """Render the new access request notification email."""
    message = request_message or "No message provided"

    subject = NEW_REQUEST_SUBJECT.format(
        ticket_id=ticket_id,
        organization_name=organization_name,
    )

    body_text = NEW_REQUEST_TEXT.format(
        ticket_id=ticket_id,
        requester_email=requester_email,
        organization_name=organization_name,
        request_message=message,
        submitted_at=submitted_at,
    )

    body_html = NEW_REQUEST_HTML.format(
        ticket_id=ticket_id,
        requester_email=requester_email,
        organization_name=organization_name,
        request_message=message,
        submitted_at=submitted_at,
    )

    return EmailContent(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


def build_new_request_template_data(
    ticket_id: str,
    requester_email: str,
    organization_name: str,
    request_message: str | None,
    submitted_at: str,
) -> dict[str, str]:
    """Build template data for a new access request."""
    return {
        "ticket_id": ticket_id,
        "requester_email": requester_email,
        "organization_name": organization_name,
        "request_message": request_message or "No message provided",
        "submitted_at": submitted_at,
    }
