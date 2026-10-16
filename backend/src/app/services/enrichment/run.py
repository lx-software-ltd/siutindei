"""Crawl then extract. Each stage is one queue delivery."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.organization import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.services.enrichment.constants import EXTRACT_TIMEOUT_SECONDS
from app.services.enrichment.extract import (
    MODEL_INSTRUCTIONS,
    merge_proposals,
    prompt_pages,
    proposals_from_pages,
    validate_model_sheet,
)
from app.services.enrichment.queue import enqueue_enrichment
from app.services.enrichment.store import load_settings, month_spend, save_proposals
from app.utils.logging import get_logger

logger = get_logger(__name__)

CrawlFn = Callable[[OrgEnrichmentRun, Any], dict[str, Any]]
ModelFn = Callable[[str], tuple[dict[str, Any], Decimal, str]]


def process_enrichment(
    session: Session,
    run_id: UUID,
    message_id: str,
    *,
    receive_count: int,
    stage: str,
    crawl: CrawlFn | None = None,
    complete: ModelFn | None = None,
) -> bool:
    """Return True when the message should be acknowledged."""
    run = session.get(OrgEnrichmentRun, run_id)
    if run is None:
        logger.warning("Enrichment run is missing")
        return True
    seen = list(run.processed_message_ids or [])
    if message_id and message_id in seen:
        return True
    if run.status in {"ready", "failed", "render_required"}:
        return True
    try:
        if stage == "extract" or run.status == "extracting":
            _extract(session, run, complete=complete)
        else:
            _crawl(session, run, crawl=crawl)
    except Exception:
        logger.exception("Enrichment run will retry", extra={"run_id": str(run_id)})
        if receive_count >= 3:
            run.status = "failed"
            run.error = "enrichment failed"
            run.finished_at = datetime.now(timezone.utc)
            session.flush()
        return False
    if message_id:
        run.processed_message_ids = seen + [message_id]
    session.flush()
    return True


def _crawl(
    session: Session,
    run: OrgEnrichmentRun,
    *,
    crawl: CrawlFn | None,
) -> None:
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
        run.finished_at = datetime.now(timezone.utc)
        return
    if status != "ok" or not run.pages:
        run.status = "failed"
        run.error = str(crawled.get("error") or "website returned no readable page")
        run.finished_at = datetime.now(timezone.utc)
        return
    run.input_hash = _hash_pages(run.pages)
    run.status = "extracting"
    session.flush()
    enqueue_enrichment(run.id, stage="extract")


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
        run.finished_at = datetime.now(timezone.utc)
        return
    org = session.get(Organization, run.org_id)
    snapshot = _org_snapshot(org)
    pages = list(run.pages or [])
    deterministic = proposals_from_pages(pages, snapshot)
    copied = _copy_cached(session, run)
    if copied is None:
        sheet, cost, model = (complete or _model)(prompt_pages(pages))
        checked = validate_model_sheet(sheet, pages, snapshot)
        run.cost_usd = cost
        run.model = model
    else:
        checked = copied
        run.cost_usd = Decimal("0")
        run.model = "cache"
    save_proposals(
        session,
        run,
        merge_proposals(deterministic, checked),
        min_confidence=Decimal(str(settings.min_confidence_shown)),
    )
    run.status = "ready"
    run.finished_at = datetime.now(timezone.utc)


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


def _model(user_content: str) -> tuple[dict[str, Any], Decimal, str]:
    from app.services.openrouter_client import (
        extract_message_text,
        openrouter_chat_completion,
        usage_from_body,
    )
    import json

    from app.services.openrouter_json_parse import openrouter_json_text_candidates

    body = openrouter_chat_completion(
        system_prompt=MODEL_INSTRUCTIONS,
        user_content=user_content or "No page text.",
        timeout=EXTRACT_TIMEOUT_SECONDS,
        workload="org-enrichment",
        max_attempts=1,
    )
    candidates = openrouter_json_text_candidates(extract_message_text(body))
    sheet = json.loads(candidates[0]) if candidates else {}
    if not isinstance(sheet, dict):
        sheet = {}
    usage = usage_from_body(body)
    return (
        sheet,
        Decimal(str(usage.get("cost_usd") or 0)),
        str(usage.get("model") or ""),
    )


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


def _hash_pages(pages: list[Any]) -> str:
    blob = "\n".join(
        str(page.get("text") or "") for page in pages if isinstance(page, dict)
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _org_snapshot(org: Organization | None) -> dict[str, Any]:
    if org is None:
        return {}
    return {
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
