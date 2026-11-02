"""Suggestion email templates."""

from __future__ import annotations

from app.templates.types import EmailContent

NEW_SUGGESTION_SUBJECT = (
    "[Siu Tin Dei] [{ticket_id}] New Place Suggestion: {organization_name}"
)

NEW_SUGGESTION_TEXT = """
[Siu Tin Dei] Place Suggestion [{ticket_id}]

A user has suggested a new organization/place.

Ticket ID: {ticket_id}
Suggester Email: {suggester_email}
Organization Name: {organization_name}
Description: {description}
District: {district}
Address: {address}
Additional Notes: {additional_notes}
Submitted At: {submitted_at}

Please review this suggestion in the admin dashboard.
"""

NEW_SUGGESTION_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 10px 0; color: #1a1a1a;">[Siu Tin Dei] Place Suggestion</h2>
        <p style="margin: 0; font-size: 14px; color: #666;">
            Ticket ID: <strong style="font-family: monospace;">{ticket_id}</strong>
        </p>
    </div>

    <p style="margin-bottom: 20px;">A user has suggested a new organization/place for the platform.</p>

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
                Suggester Email
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                <a href="mailto:{suggester_email}" style="color: #0066cc;">{suggester_email}</a>
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
                Description
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {description}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                District
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {district}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Address
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {address}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Additional Notes
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {additional_notes}
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
            Please review this suggestion in the admin dashboard and approve or reject it.
        </p>
    </div>

    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">

    <p style="font-size: 12px; color: #666; margin: 0;">
        This is an automated message from Siu Tin Dei. Please do not reply directly to this email.
    </p>
</body>
</html>
"""


def render_new_suggestion_email(
    ticket_id: str,
    suggester_email: str,
    organization_name: str,
    description: str | None,
    district: str | None,
    address: str | None,
    additional_notes: str | None,
    submitted_at: str,
) -> EmailContent:
    """Render the new organization suggestion notification email."""
    desc = description or "Not provided"
    dist = district or "Not provided"
    addr = address or "Not provided"
    notes = additional_notes or "No additional notes"

    subject = NEW_SUGGESTION_SUBJECT.format(
        ticket_id=ticket_id,
        organization_name=organization_name,
    )

    body_text = NEW_SUGGESTION_TEXT.format(
        ticket_id=ticket_id,
        suggester_email=suggester_email,
        organization_name=organization_name,
        description=desc,
        district=dist,
        address=addr,
        additional_notes=notes,
        submitted_at=submitted_at,
    )

    body_html = NEW_SUGGESTION_HTML.format(
        ticket_id=ticket_id,
        suggester_email=suggester_email,
        organization_name=organization_name,
        description=desc,
        district=dist,
        address=addr,
        additional_notes=notes,
        submitted_at=submitted_at,
    )

    return EmailContent(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


def build_new_suggestion_template_data(
    ticket_id: str,
    suggester_email: str,
    organization_name: str,
    description: str | None,
    district: str | None,
    address: str | None,
    additional_notes: str | None,
    submitted_at: str,
) -> dict[str, str]:
    """Build template data for a new organization suggestion."""
    return {
        "ticket_id": ticket_id,
        "suggester_email": suggester_email,
        "organization_name": organization_name,
        "description": description or "Not provided",
        "district": district or "Not provided",
        "address": address or "Not provided",
        "additional_notes": additional_notes or "No additional notes",
        "submitted_at": submitted_at,
    }
