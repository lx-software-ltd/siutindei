"""SES email sending helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from app.services.aws_clients import get_ses_client


def send_email(
    *,
    source: str,
    to_addresses: Iterable[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    """Send a plain or HTML email via SES."""
    message: dict[str, Any] = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
    }
    if body_html:
        message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    get_ses_client().send_email(
        Source=source,
        Destination={"ToAddresses": list(to_addresses)},
        Message=message,
    )


def send_templated_email(
    *,
    source: str,
    to_addresses: Iterable[str],
    template_name: str,
    template_data: dict[str, Any],
) -> None:
    """Send a templated email via SES."""
    get_ses_client().send_templated_email(
        Source=source,
        Destination={"ToAddresses": list(to_addresses)},
        Template=template_name,
        TemplateData=json.dumps(template_data),
    )
