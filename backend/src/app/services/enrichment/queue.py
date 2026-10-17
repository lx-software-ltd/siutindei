"""Publish enrichment work on the category-suggestion queue."""

from __future__ import annotations

import json
import os
from uuid import UUID

from app.services.aws_clients import get_client


def enqueue_enrichment(run_id: UUID | str, *, stage: str) -> None:
    queue_url = os.getenv("CATEGORY_SUGGESTION_QUEUE_URL", "").strip()
    if not queue_url:
        raise RuntimeError("CATEGORY_SUGGESTION_QUEUE_URL is not configured")
    get_client("sqs").send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"enrichment_run_id": str(run_id), "stage": stage}),
    )
