"""Run one OpenRouter enrichment for a category suggestion."""

from __future__ import annotations

import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
)
from app.services.category_suggestions.prompt import build_enrichment_prompt
from app.services.category_suggestions.settings import get_settings
from app.services.openrouter_client import (
    WORKLOAD_CATEGORY_SUGGESTION,
    OpenRouterError,
    usage_from_body,
)
from app.services.openrouter_json_parse import loads_openrouter_json
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _timeout_seconds() -> int:
    raw = os.getenv("CATEGORY_SUGGESTION_OPENROUTER_TIMEOUT_SECONDS", "90")
    try:
        return max(10, int(raw))
    except ValueError:
        return 90


def _lambda_timeout_seconds() -> int:
    raw = os.getenv("CATEGORY_SUGGESTION_LAMBDA_TIMEOUT_SECONDS", "120")
    try:
        return max(30, int(raw))
    except ValueError:
        return 120


def process_suggestion(
    suggestion_id: UUID,
    *,
    force: bool = False,
    receive_count: int = 1,
) -> bool:
    """Enrich one suggestion. Return True when the SQS message can be deleted."""
    stale_after = timedelta(seconds=_lambda_timeout_seconds() * 2 + 60)
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            logger.warning(
                "Category suggestion missing",
                extra={"suggestion_id": str(suggestion_id)},
            )
            return True
        if suggestion.enrichment_status == "done" and not force:
            return True
        if suggestion.enrichment_status == "running" and not force:
            updated = suggestion.updated_at
            if (
                updated is not None
                and datetime.now(timezone.utc) - updated < stale_after
            ):
                return False
            suggestion.enrichment_status = "failed"
            suggestion.enrichment_error = "Previous enrichment attempt did not finish"
            session.commit()
            return True
        suggestion.enrichment_status = "running"
        suggestion.enrichment_error = None
        suggestion.updated_at = datetime.now(timezone.utc)
        session.commit()

    try:
        _generate(suggestion_id)
    except OpenRouterError as exc:
        _fail_or_requeue(suggestion_id, str(exc), receive_count=receive_count)
        if receive_count >= 3:
            return True
        raise
    except Exception as exc:
        logger.exception(
            "Category suggestion enrichment failed",
            extra={"suggestion_id": str(suggestion_id)},
        )
        _mark_failed(suggestion_id, str(exc) or type(exc).__name__)
        return True
    return True


def _generate(suggestion_id: UUID) -> None:
    from app.services.openrouter_client import (
        extract_message_text,
        openrouter_chat_completion,
    )

    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            return
        settings = get_settings(session)
        system, user = build_enrichment_prompt(
            session,
            suggestion,
            max_evidence=int(settings.max_evidence_items),
        )
        deny = bool(settings.deny_data_collection)
    body = openrouter_chat_completion(
        system_prompt=system,
        user_content=user,
        timeout=_timeout_seconds(),
        workload=WORKLOAD_CATEGORY_SUGGESTION,
        temperature=0,
        deny_data_collection=deny,
    )
    text = extract_message_text(body)
    parsed = loads_openrouter_json(text, context="category suggestion")
    usage = usage_from_body(body)
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            return
        _apply_parsed(session, suggestion, parsed, usage)
        session.commit()


def _apply_parsed(
    session: Session,
    suggestion: CategorySuggestion,
    parsed: Any,
    usage: dict[str, Any],
) -> None:
    if not isinstance(parsed, dict):
        raise OpenRouterError("Model response payload is not an object")
    maps = parsed.get("maps_to_existing")
    maps_id = None
    if isinstance(maps, dict):
        maps_id = _existing_category(session, maps.get("category_id"))
    propose = parsed.get("propose") if isinstance(parsed.get("propose"), dict) else {}
    parent_id = _existing_category(session, propose.get("parent_id"))
    name = _clean_name(propose.get("name_en"))
    name_zh = _clean_name(propose.get("name_zh"))
    confidence = _confidence(parsed.get("confidence"))
    suggestion.maps_to_category_id = maps_id
    suggestion.suggested_name = name
    suggestion.name_translations = {"zh": name_zh} if name_zh else {}
    suggestion.suggested_parent_id = parent_id
    suggestion.rationale = _clean_text(
        parsed.get("rationale") or propose.get("rationale")
    )
    suggestion.confidence = confidence
    suggestion.alternatives = {
        "items": _alternatives(session, parsed.get("alternatives")),
        "display_order_hint": _order_hint(propose.get("display_order_hint")),
    }
    suggestion.model_used = str(usage.get("model") or "") or None
    suggestion.usage = _merge_usage(suggestion.usage, usage)
    suggestion.enrichment_status = "done"
    suggestion.enrichment_error = None
    suggestion.enriched_at = datetime.now(timezone.utc)
    suggestion.updated_at = suggestion.enriched_at


def _existing_category(session: Session, raw: Any) -> UUID | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        category_id = UUID(raw.strip())
    except ValueError:
        return None
    if category_id == PENDING_CATEGORY_ID:
        return None
    if session.get(ActivityCategory, category_id) is None:
        return None
    return category_id


def _alternatives(session: Session, raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw[:5]:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "name_en": _clean_name(entry.get("name_en")),
                "parent_id": (
                    str(parent)
                    if (parent := _existing_category(session, entry.get("parent_id")))
                    else None
                ),
                "confidence": _confidence(entry.get("confidence")),
            }
        )
    return items


def _merge_usage(existing: Any, delta: dict[str, Any]) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    return {
        "prompt_tokens": int(base.get("prompt_tokens") or 0)
        + int(delta.get("prompt_tokens") or 0),
        "completion_tokens": int(base.get("completion_tokens") or 0)
        + int(delta.get("completion_tokens") or 0),
        "cost_usd": round(
            float(base.get("cost_usd") or 0) + float(delta.get("cost_usd") or 0),
            6,
        ),
    }


def _clean_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 200:
        return text[:200] if text else None
    return text


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:2000] if text else None


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < 0 or number > 1:
        return None
    return round(number, 3)


def _order_hint(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _fail_or_requeue(suggestion_id: UUID, message: str, *, receive_count: int) -> None:
    if receive_count >= 3:
        _mark_failed(suggestion_id, message)
        return
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            return
        suggestion.enrichment_status = "queued"
        suggestion.enrichment_error = message[:500]
        suggestion.updated_at = datetime.now(timezone.utc)
        session.commit()


def _mark_failed(suggestion_id: UUID, message: str) -> None:
    with Session(get_engine()) as session:
        suggestion = session.get(CategorySuggestion, suggestion_id)
        if suggestion is None:
            return
        if suggestion.enrichment_status == "done":
            return
        suggestion.enrichment_status = "failed"
        suggestion.enrichment_error = message[:500]
        suggestion.updated_at = datetime.now(timezone.utc)
        session.commit()
