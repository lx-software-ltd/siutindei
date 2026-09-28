"""Queue category suggestions for OpenRouter enrichment."""

from __future__ import annotations

import json
import os
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models.category_suggestion import CategorySuggestion
from app.services.aws_clients import get_client
from app.utils.logging import get_logger

logger = get_logger(__name__)


def enqueue_enrichment(
    suggestion_ids: list[str],
    *,
    force: bool = False,
) -> None:
    """Mark suggestions queued and publish one SQS message each."""
    ids = [item for item in suggestion_ids if item]
    if not ids:
        return
    with Session(get_engine()) as session:
        rows = list(
            session.scalars(
                select(CategorySuggestion).where(
                    CategorySuggestion.id.in_([UUID(item) for item in ids])
                )
            ).all()
        )
        queued: list[str] = []
        for row in rows:
            if row.enrichment_status == "running" and not force:
                continue
            row.enrichment_status = "queued"
            row.enrichment_error = None
            queued.append(str(row.id))
        session.commit()
    queue_url = os.getenv("CATEGORY_SUGGESTION_QUEUE_URL", "").strip()
    if not queue_url or not queued:
        if not queue_url and queued:
            logger.warning("CATEGORY_SUGGESTION_QUEUE_URL is not configured")
        return
    client = get_client("sqs")
    for suggestion_id in queued:
        client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"suggestion_id": suggestion_id, "force": force}),
        )
