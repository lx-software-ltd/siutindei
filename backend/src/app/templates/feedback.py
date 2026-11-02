"""Feedback email templates."""

from __future__ import annotations

from collections.abc import Iterable

from app.templates.types import EmailContent

NEW_FEEDBACK_SUBJECT = "[Siu Tin Dei] [{ticket_id}] New Feedback: {organization_name}"

NEW_FEEDBACK_TEXT = """
[Siu Tin Dei] Organization Feedback [{ticket_id}]

A user has submitted feedback for an organization.

Ticket ID: {ticket_id}
Submitter Email: {submitter_email}
Organization Name: {organization_name}
Stars: {stars}
Labels: {labels}
Description: {description}
Submitted At: {submitted_at}

Please review this feedback in the admin dashboard.
"""

NEW_FEEDBACK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 10px 0; color: #1a1a1a;">[Siu Tin Dei] Organization Feedback</h2>
        <p style="margin: 0; font-size: 14px; color: #666;">
            Ticket ID: <strong style="font-family: monospace;">{ticket_id}</strong>
        </p>
    </div>

    <p style="margin-bottom: 20px;">A user has submitted feedback for an organization.</p>

    <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa; width: 140px;">
                Submitter Email
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                <a href="mailto:{submitter_email}" style="color: #0066cc;">{submitter_email}</a>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Organization
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {organization_name}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Stars
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {stars}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                Labels
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {labels}
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
                Submitted At
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {submitted_at}
            </td>
        </tr>
    </table>

    <div style="background-color: #e7f3ff; padding: 15px; border-radius: 5px; border-left: 4px solid #0066cc;">
        <p style="margin: 0; font-size: 14px;">
            Please review this feedback in the admin dashboard and approve or reject it.
        </p>
    </div>

    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">

    <p style="font-size: 12px; color: #666; margin: 0;">
        This is an automated message from Siu Tin Dei. Please do not reply directly to this email.
    </p>
</body>
</html>
"""


def render_new_feedback_email(
    ticket_id: str,
    submitter_email: str,
    organization_name: str,
    stars: int | None,
    labels: Iterable[str] | None,
    description: str | None,
    submitted_at: str,
) -> EmailContent:
    """Render the new feedback notification email."""
    label_text = _format_labels(labels)
    desc = description or "Not provided"
    stars_text = str(stars) if stars is not None else "Not provided"

    subject = NEW_FEEDBACK_SUBJECT.format(
        ticket_id=ticket_id,
        organization_name=organization_name,
    )

    body_text = NEW_FEEDBACK_TEXT.format(
        ticket_id=ticket_id,
        submitter_email=submitter_email,
        organization_name=organization_name,
        stars=stars_text,
        labels=label_text,
        description=desc,
        submitted_at=submitted_at,
    )

    body_html = NEW_FEEDBACK_HTML.format(
        ticket_id=ticket_id,
        submitter_email=submitter_email,
        organization_name=organization_name,
        stars=stars_text,
        labels=label_text,
        description=desc,
        submitted_at=submitted_at,
    )

    return EmailContent(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


def build_new_feedback_template_data(
    ticket_id: str,
    submitter_email: str,
    organization_name: str,
    stars: int | None,
    labels: Iterable[str] | None,
    description: str | None,
    submitted_at: str,
) -> dict[str, str]:
    """Build template data for a new feedback email."""
    return {
        "ticket_id": ticket_id,
        "submitter_email": submitter_email,
        "organization_name": organization_name,
        "stars": str(stars) if stars is not None else "Not provided",
        "labels": _format_labels(labels),
        "description": description or "Not provided",
        "submitted_at": submitted_at,
    }


def _format_labels(labels: Iterable[str] | None) -> str:
    if not labels:
        return "None"
    cleaned = [label for label in labels if label]
    return ", ".join(cleaned) if cleaned else "None"
