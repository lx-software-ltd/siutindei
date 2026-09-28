"""Partial-batch responses for SQS-triggered Lambdas."""

from __future__ import annotations


def failure_response(message_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    """Build the SQS batchItemFailures payload."""
    return {
        "batchItemFailures": [
            {"itemIdentifier": message_id} for message_id in message_ids if message_id
        ]
    }
