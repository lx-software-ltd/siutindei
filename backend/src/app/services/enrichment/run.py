"""Crawl then extract. Each stage is one queue delivery."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.db.models.organization import Organization
from app.services.aws_proxy import AwsProxyError
from app.services.enrichment.constants import (
    EXTRACT_TIMEOUT_SECONDS,
    EXTRACTION_VERSION,
    MAX_REPLY_TOKENS,
)
from app.services.enrichment.extract import (
    merge_proposals,
    proposals_from_pages,
    validate_model_sheet,
    without_cached_leaflet_media,
)
from app.services.enrichment.leaflet import LeafletReadError
from app.services.enrichment.leaflet_stage import (
    prepare_leaflet_run,
    transcribe_leaflet_run,
)
from app.services.enrichment.leaflet_vision import media_from_pages
from app.services.enrichment.match import prepare_proposals
from app.services.enrichment.prompt import (
    MODEL_INSTRUCTIONS,
    instructions_for,
    prompt_pages,
)
from app.services.enrichment.queue import enqueue_enrichment
from app.services.enrichment.refine import annotate, catalog_names
from app.services.enrichment.sheet import SECTIONS, read_sheet, section_rows
from app.services.enrichment.store import load_settings, month_spend, save_proposals
from app.services.openrouter_client import _RETRYABLE_HTTP_STATUSES, OpenRouterError
from app.utils.logging import get_logger

logger = get_logger(__name__)

PROVIDER_BUSY_ERROR = "The model provider was busy. Try again later."

CrawlFn = Callable[[OrgEnrichmentRun, Any], dict[str, Any]]
ModelFn = Callable[[str], tuple[dict[str, Any], Decimal, str]]
PrepareFn = Callable[[OrgEnrichmentRun], dict[str, Any]]
TranscribeFn = Callable[[list[str], str], tuple[list[str], Decimal, str]]


@dataclass
class EnrichmentStep:
    acked: bool
    run_id: UUID | str | None = None
    enqueue_stage: str | None = None


def commit_and_queue(session: Session, step: EnrichmentStep) -> None:
    """Commit the stage, then publish the next one."""
    if step.acked:
        session.commit()
    else:
        session.rollback()
    if step.acked and step.enqueue_stage and step.run_id is not None:
        try:
            enqueue_enrichment(step.run_id, stage=step.enqueue_stage)
        except Exception:
            logger.exception(
                "Enrichment follow-up was not queued",
                extra={"run_id": str(step.run_id)},
            )
            fail_enrichment_run(step.run_id, "Enrichment queue is not configured")


def _proxy_failure_message(exc: AwsProxyError, *, leaflet: bool) -> str:
    if exc.code == "CrawlRefused" and exc.message:
        return exc.message
    if leaflet:
        return "The leaflet could not be read"
    return "The website could not be read"


def _fail_open_run(session: Session, run_id: UUID | str, error: str) -> None:
    row = session.get(OrgEnrichmentRun, run_id)
    if row is None or row.status in {"ready", "failed", "render_required"}:
        return
    if row.source == "leaflet":
        from app.services.enrichment.leaflet_objects import release_leaflet_run

        release_leaflet_run(row)
    row.status = "failed"
    row.error = error
    row.finished_at = datetime.now(UTC)
    session.flush()


def fail_enrichment_run(run_id: UUID | str, error: str = "enrichment failed") -> None:
    from app.db.engine import get_engine

    with Session(get_engine()) as session:
        row = session.get(OrgEnrichmentRun, run_id)
        if row is None or row.status in {"ready", "failed", "render_required"}:
            return
        if row.source == "leaflet":
            from app.services.enrichment.leaflet_objects import release_leaflet_run

            release_leaflet_run(row)
        row.status = "failed"
        row.error = error
        row.finished_at = datetime.now(UTC)
        session.commit()


def process_enrichment(
    session: Session,
    run_id: UUID,
    message_id: str,
    *,
    receive_count: int,
    stage: str,
    crawl: CrawlFn | None = None,
    complete: ModelFn | None = None,
    prepare: PrepareFn | None = None,
    transcribe: TranscribeFn | None = None,
) -> EnrichmentStep:
    """Return whether the message should be acknowledged, and any follow-up."""
    run = session.get(OrgEnrichmentRun, run_id)
    if run is None:
        logger.warning("Enrichment run is missing")
        return EnrichmentStep(acked=True)
    seen = list(run.processed_message_ids or [])
    if message_id and message_id in seen:
        return EnrichmentStep(acked=True)
    if run.status in {"ready", "failed", "render_required"}:
        return EnrichmentStep(acked=True)
    step = EnrichmentStep(acked=True, run_id=run.id)
    try:
        if stage == "extract" or run.status == "extracting":
            _extract(session, run, complete=complete)
        elif stage == "transcribe":
            step.enqueue_stage = transcribe_leaflet_run(
                session, run, transcribe=transcribe
            )
        elif stage == "leaflet" or run.source == "leaflet":
            step.enqueue_stage = prepare_leaflet_run(session, run, prepare=prepare)
        else:
            step.enqueue_stage = _crawl(session, run, crawl=crawl)
    except LeafletReadError as exc:
        logger.exception("Leaflet could not be read", extra={"run_id": str(run_id)})
        _fail_open_run(session, run_id, exc.message)
        return EnrichmentStep(acked=True)
    except AwsProxyError as exc:
        if exc.code == "TimeoutError":
            logger.exception("Enrichment run will retry", extra={"run_id": str(run_id)})
            session.rollback()
            if receive_count >= 3:
                fail_enrichment_run(run_id)
                return EnrichmentStep(acked=True)
            return EnrichmentStep(acked=False)
        logger.exception("Enrichment crawl failed", extra={"run_id": str(run_id)})
        _fail_open_run(
            session,
            run_id,
            _proxy_failure_message(exc, leaflet=run.source == "leaflet"),
        )
        return EnrichmentStep(acked=True)
    except OpenRouterError as exc:
        logger.exception(
            "Enrichment run will retry",
            extra={
                "extra": {
                    "run_id": str(run_id),
                    "status": exc.status,
                    "receive_count": receive_count,
                }
            },
        )
        session.rollback()
        if receive_count >= 3:
            message = (
                PROVIDER_BUSY_ERROR
                if exc.status in _RETRYABLE_HTTP_STATUSES
                else "enrichment failed"
            )
            fail_enrichment_run(run_id, message)
            return EnrichmentStep(acked=True)
        return EnrichmentStep(acked=False)
    except Exception:
        logger.exception("Enrichment run will retry", extra={"run_id": str(run_id)})
        session.rollback()
        if receive_count >= 3:
            fail_enrichment_run(run_id)
            return EnrichmentStep(acked=True)
        return EnrichmentStep(acked=False)
    if message_id:
        run.processed_message_ids = seen + [message_id]
    session.flush()
    return step


def _crawl(
    session: Session,
    run: OrgEnrichmentRun,
    *,
    crawl: CrawlFn | None,
) -> str | None:
    run.status = "running"
    session.flush()
    settings = load_settings(session)
    crawled = (crawl or _proxy_crawl)(run, settings)
    status = str(crawled.get("status") or "failed")
    run.pages_fetched = int(crawled.get("pages_fetched") or 0)
    run.bytes_fetched = int(crawled.get("bytes_fetched") or 0)
    run.pages = list(crawled.get("pages") or [])
    if status == "render_required":
        run.status = "render_required"
        run.error = str(crawled.get("error") or "")
        run.finished_at = datetime.now(UTC)
        return None
    if status != "ok" or not run.pages:
        run.status = "failed"
        run.error = str(crawled.get("error") or "website returned no readable page")
        run.finished_at = datetime.now(UTC)
        return None
    run.input_hash = _hash_pages(run.pages)
    run.status = "extracting"
    session.flush()
    return "extract"


def _extract(
    session: Session,
    run: OrgEnrichmentRun,
    *,
    complete: ModelFn | None,
) -> None:
    settings = load_settings(session)
    if month_spend(session) >= Decimal(str(settings.monthly_cost_limit_usd)):
        run.status = "failed"
        run.error = "The monthly enrichment budget is spent"
        run.finished_at = datetime.now(UTC)
        return
    org = session.get(Organization, run.org_id)
    snapshot = _org_snapshot(org)
    pages = list(run.pages or [])
    deterministic = proposals_from_pages(pages, snapshot)
    copied = _copy_cached(session, run)
    if copied is not None:
        copied = without_cached_leaflet_media(copied) or None
    if copied is None:
        prompt = instructions_for(catalog_names(session)) + prompt_pages(pages)
        if complete is None:
            model_name, fallbacks, deny = _openrouter_settings(session)
            sheet, cost, model = _model(
                prompt,
                model_name=model_name,
                fallback_models=fallbacks,
                deny_data_collection=deny,
            )
        else:
            sheet, cost, model = complete(prompt)
        checked = validate_model_sheet(sheet, pages, snapshot)
        run.cost_usd = Decimal(str(run.cost_usd or 0)) + cost
        run.model = model
        # StructuredLogFormatter prints only a field named "extra".
        logger.info(
            "Enrichment model sheet checked",
            extra={
                "extra": {
                    "run_id": str(run.id),
                    "pages": len(pages),
                    "prompt_chars": len(prompt),
                    "model_rows": {
                        section: len(section_rows(sheet, section))
                        for section in SECTIONS
                    },
                    "kept": _section_counts(checked),
                }
            },
        )
    else:
        checked = copied
        run.model = "cache"
    merged = merge_proposals(media_from_pages(pages), deterministic, checked)
    if org is not None:
        merged = annotate(session, org, merged)
        merged = prepare_proposals(session, org, merged)
    save_proposals(
        session,
        run,
        merged,
        min_confidence=Decimal(str(settings.min_confidence_shown)),
    )
    run.status = "ready"
    run.finished_at = datetime.now(UTC)
    if run.source == "leaflet":
        from app.services.enrichment.leaflet_objects import release_finished_leaflet

        release_finished_leaflet(run)


def _proxy_crawl(run: OrgEnrichmentRun, settings: Any) -> dict[str, Any]:
    from app.services.aws_proxy import crawl_invoke
    from app.services.enrichment.constants import CRAWL_TIME_BUDGET_SECONDS

    return crawl_invoke(
        {
            "op": "site",
            "seed_url": run.seed_url,
            "max_pages": settings.max_pages,
            "max_page_bytes": settings.max_page_bytes,
            "time_budget_seconds": CRAWL_TIME_BUDGET_SECONDS,
        }
    )


def _openrouter_settings(session: Session) -> tuple[str, list[str], bool]:
    """Model, fallbacks, and the data-collection flag from this session.

    The admin function keeps one database connection. Loading these
    through another session waits out the pool timeout and then drops
    the saved model, so the client never opens that second session.
    """
    from app.services.category_suggestions.settings import (
        get_settings,
        resolved_fallback_models,
        resolved_model_name,
    )

    row = get_settings(session)
    return (
        resolved_model_name(row.openrouter_model),
        resolved_fallback_models(row.fallback_models),
        bool(row.deny_data_collection),
    )


def _model(
    user_content: str,
    *,
    model_name: str,
    fallback_models: list[str],
    deny_data_collection: bool,
) -> tuple[dict[str, Any], Decimal, str]:
    from app.services.openrouter_client import (
        extract_message_text,
        openrouter_chat_completion,
        usage_from_body,
    )

    request: dict[str, Any] = {
        "system_prompt": MODEL_INSTRUCTIONS,
        "user_content": user_content or "No page text.",
        "timeout": EXTRACT_TIMEOUT_SECONDS,
        "workload": "org-enrichment",
        "max_attempts": 1,
        "model": model_name,
        "fallback_models": fallback_models,
        "deny_data_collection": deny_data_collection,
    }
    started = time.monotonic()
    try:
        body = openrouter_chat_completion(
            **request, max_tokens=MAX_REPLY_TOKENS, reasoning_off=True
        )
    except OpenRouterError as exc:
        # An admin-chosen model may require reasoning or allow a shorter reply.
        # Its refusal is quick, so one plain retry still fits the function.
        if exc.status not in {400, 404} or time.monotonic() - started > 15:
            raise
        logger.warning(
            "Enrichment model refused reply settings; retrying without them",
            extra={"extra": {"status": exc.status}},
        )
        body = openrouter_chat_completion(**request)
    text = extract_message_text(body)
    sheet, parsed = read_sheet(text)
    usage = usage_from_body(body)
    logger.info(
        "Enrichment model reply",
        extra={
            "extra": {
                "model": str(usage.get("model") or ""),
                "finish_reason": _finish_reason(body),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reply_chars": len(text),
                "sheet": parsed,
            }
        },
    )
    return (
        sheet,
        Decimal(str(usage.get("cost_usd") or 0)),
        str(usage.get("model") or ""),
    )


def _finish_reason(body: str) -> str:
    """``length`` means the reply hit the model's output limit."""
    try:
        payload = json.loads(body)
        return str(payload["choices"][0].get("finish_reason") or "")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return ""


def _copy_cached(
    session: Session, run: OrgEnrichmentRun
) -> list[dict[str, Any]] | None:
    if not run.input_hash:
        return None
    previous = session.scalar(
        select(OrgEnrichmentRun)
        .where(
            OrgEnrichmentRun.org_id == run.org_id,
            OrgEnrichmentRun.input_hash == run.input_hash,
            OrgEnrichmentRun.status == "ready",
            OrgEnrichmentRun.id != run.id,
        )
        .limit(1)
    )
    if previous is None:
        return None
    rows = session.scalars(
        select(OrgEnrichmentProposal).where(OrgEnrichmentProposal.run_id == previous.id)
    ).all()
    return [
        {
            "section": row.section,
            "kind": row.kind,
            "field": row.field,
            "label": row.label,
            "current": row.current_value,
            "proposed": row.proposed_value,
            "confidence": float(row.confidence),
            "unverified": row.unverified,
            "evidence": row.evidence,
        }
        for row in rows
    ]


def _section_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        section = str(item.get("section") or "")
        counts[section] = counts.get(section, 0) + 1
    return counts


def _hash_pages(pages: list[Any]) -> str:
    """Key for reusing an earlier run's proposals.

    Covers the page text and the extraction code, so a run made with an
    older prompt or parser is not copied after the code changes.
    """
    blob = "\n".join(
        str(page.get("text") or "") for page in pages if isinstance(page, dict)
    )
    digest = hashlib.sha256(blob.encode("utf-8"))
    digest.update(b"\x00extraction:")
    digest.update(EXTRACTION_VERSION.encode("utf-8"))
    digest.update(MODEL_INSTRUCTIONS.encode("utf-8"))
    return digest.hexdigest()


def _org_snapshot(org: Organization | None) -> dict[str, Any]:
    if org is None:
        return {}
    return {
        "name": org.name,
        "name_translations": dict(org.name_translations or {}),
        "description": org.description,
        "description_translations": dict(org.description_translations or {}),
        "email": org.email,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "whatsapp": org.whatsapp,
        "facebook": org.facebook,
        "instagram": org.instagram,
        "tiktok": org.tiktok,
        "twitter": org.twitter,
        "xiaohongshu": org.xiaohongshu,
        "wechat": org.wechat,
        "website": org.website,
        "review_status": org.review_status,
    }
