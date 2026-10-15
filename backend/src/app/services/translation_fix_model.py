"""OpenRouter batches that fill missing translations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_validators import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH
from app.db.engine import get_engine
from app.db.models.translation_fix import TranslationScanRun
from app.services.category_suggestions.settings import (
    get_settings,
    resolved_fallback_models,
    resolved_model_name,
)
from app.services.data_quality.answers import (
    TRANSLATION_PROMPT_VERSION,
    recorded_completion,
)
from app.services.data_quality.sweep_support import (
    advance_scan_batch,
    confidence_score,
    fail_open_run,
    openrouter_timeout_seconds,
    rationale_text,
)
from app.services.openrouter_client import (
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
)
from app.services.openrouter_json_parse import loads_openrouter_json
from app.services.translation_fix_prompt import build_prompt
from app.services.translation_fix_query import catalog_model, over_budget
from app.services.translation_fixes import upsert_proposal
from app.services.translation_gaps import LANGUAGES, entity_gaps, text_value
from app.utils.logging import get_logger

logger = get_logger(__name__)

WORKLOAD_TRANSLATION_FIX = "translation-fix"


def process_translation_batch(
    scan_run_id: UUID,
    entity_type: str,
    entity_ids: list[str],
    *,
    message_id: str = "",
    receive_count: int = 1,
) -> bool:
    """Propose missing languages for one batch. Return True when SQS can delete it."""
    prepared = _prepare(scan_run_id, entity_type, entity_ids, message_id)
    if prepared is None:
        return True
    system, user, model_name, fallbacks, deny = prepared
    try:
        reply = recorded_completion(
            record=False,
            refresh=False,
            prompt_version=TRANSLATION_PROMPT_VERSION,
            model=model_name,
            system_prompt=system,
            user_content=user,
            invoke=lambda: openrouter_chat_completion(
                system_prompt=system,
                user_content=user,
                timeout=openrouter_timeout_seconds(),
                workload=WORKLOAD_TRANSLATION_FIX,
                temperature=0,
                max_attempts=1,
                model=model_name,
                fallback_models=fallbacks,
                deny_data_collection=deny,
            ),
        )
        parsed = loads_openrouter_json(
            extract_message_text(reply.body),
            context="translation sweep",
        )
        usage = reply.usage
    except OpenRouterError as exc:
        if receive_count >= 3:
            record_batch_failure(
                scan_run_id, entity_ids, str(exc), message_id=message_id
            )
        raise
    except Exception as exc:
        logger.exception(
            "Translation sweep batch failed",
            extra={"scan_run_id": str(scan_run_id)},
        )
        record_batch_failure(
            scan_run_id,
            entity_ids,
            str(exc) or type(exc).__name__,
            message_id=message_id,
        )
        return True
    with Session(get_engine()) as session:
        store_model_items(
            session,
            scan_run_id,
            entity_type,
            entity_ids,
            parsed if isinstance(parsed, dict) else {},
        )
        _finish_batch(session, scan_run_id, usage, message_id, failed=False)
        session.commit()
    return True


def store_model_items(
    session: Session,
    scan_run_id: UUID,
    entity_type: str,
    entity_ids: list[str],
    payload: dict[str, Any],
) -> None:
    """Persist translations for languages that are still missing."""
    created = 0
    updated = 0
    wanted = []
    for raw in entity_ids:
        try:
            wanted.append(UUID(str(raw)))
        except ValueError:
            continue
    items = payload.get("items") if isinstance(payload, dict) else None
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("entity_id") or "")
            field = str(item.get("field") or "")
            if entity_id and field in {"name", "description"}:
                by_key[(entity_id, field)] = item
    model = catalog_model(entity_type)
    if model is None:
        return
    rows = {
        row.id: row
        for row in session.scalars(select(model).where(model.id.in_(wanted))).all()
    }
    for entity_id in wanted:
        entity = rows.get(entity_id)
        if entity is None:
            continue
        org_id = entity.id if entity_type == "organization" else entity.org_id
        for field, gap in entity_gaps(entity).items():
            item = by_key.get((str(entity_id), field), {})
            proposed = _accepted_translations(
                item.get("translations"),
                gap["missing"],
                field,
            )
            if not proposed:
                continue
            outcome = upsert_proposal(
                session,
                entity_type=entity_type,
                entity_id=entity.id,
                org_id=org_id,
                field=field,
                source_text=gap["source"],
                proposed_text=proposed,
                missing_languages=list(gap["missing"]),
                confidence=confidence_score(item.get("confidence")),
                rationale=rationale_text(item.get("rationale")),
                scan_run_id=scan_run_id,
            )
            if outcome == "created":
                created += 1
            elif outcome == "updated":
                updated += 1
    run = session.get(TranslationScanRun, scan_run_id)
    if run is not None and run.status not in {"done", "failed"}:
        run.created_count = int(run.created_count or 0) + created
        run.updated_count = int(run.updated_count or 0) + updated


def record_batch_failure(
    scan_run_id: UUID,
    entity_ids: list[str],
    message: str,
    *,
    message_id: str,
) -> None:
    with Session(get_engine()) as session:
        _finish_batch(
            session,
            scan_run_id,
            {},
            message_id,
            failed=True,
            failed_entities=len(entity_ids),
            error=message,
        )
        session.commit()


def _accepted_translations(raw: Any, missing: list[str], field: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    limit = MAX_NAME_LENGTH if field == "name" else MAX_DESCRIPTION_LENGTH
    found: dict[str, str] = {}
    for key in LANGUAGES:
        if key not in missing:
            continue
        value = text_value(raw.get(key))
        if value and len(value) <= limit:
            found[key] = value
    return found


def _prepare(scan_run_id, entity_type, entity_ids, message_id):
    with Session(get_engine()) as session:
        run = session.get(TranslationScanRun, scan_run_id)
        if run is None or run.status in {"done", "failed"}:
            return None
        seen = [str(item) for item in (run.processed_message_ids or [])]
        if message_id and message_id in seen:
            return None
        if over_budget(session):
            fail_open_run(run, "Monthly translation-sweep budget is used")
            session.commit()
            return None
        ids = []
        for raw in entity_ids:
            try:
                ids.append(UUID(str(raw)))
            except ValueError:
                continue
        model = catalog_model(entity_type)
        if model is None:
            return None
        rows = list(session.scalars(select(model).where(model.id.in_(ids))).all())
        if not rows:
            _finish_batch(session, scan_run_id, {}, message_id, failed=False)
            session.commit()
            return None
        system, user, item_count = build_prompt(entity_type, rows)
        if item_count == 0:
            _finish_batch(session, scan_run_id, {}, message_id, failed=False)
            session.commit()
            return None
        settings = get_settings(session)
        return (
            system,
            user,
            resolved_model_name(settings.openrouter_model),
            resolved_fallback_models(settings.fallback_models),
            bool(settings.deny_data_collection),
        )


def _finish_batch(
    session: Session,
    scan_run_id: UUID,
    usage: dict[str, Any],
    message_id: str,
    *,
    failed: bool,
    failed_entities: int = 0,
    error: str | None = None,
) -> None:
    run = session.get(TranslationScanRun, scan_run_id)
    advance_scan_batch(
        run,
        usage,
        message_id,
        failed=failed,
        failed_entities=failed_entities,
        error=error,
        default_error="Translation sweep batch failed",
    )
