"""Leaflet queue stages: store the files, then transcribe pictures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.org_enrichment import OrgEnrichmentRun
from app.services.enrichment.leaflet import read_leaflets
from app.services.enrichment.leaflet_vision import (
    resolved_leaflet_model,
    transcribe_pages,
)
from app.services.enrichment.store import load_settings

PrepareFn = Callable[[OrgEnrichmentRun], dict[str, Any]]
TranscribeFn = Callable[[list[str], str], tuple[list[str], Decimal, str]]


def prepare_leaflet_run(
    session: Session,
    run: OrgEnrichmentRun,
    *,
    prepare: PrepareFn | None,
) -> str | None:
    """Store the leaflet and either queue transcription or extract."""
    from app.services.enrichment.run import _hash_pages

    run.status = "running"
    session.flush()
    prepared = (prepare or _prepare_leaflet)(run)
    run.pages = list(prepared.get("pages") or [])
    run.leaflet_items = list(prepared.get("items") or run.leaflet_items or [])
    run.pages_fetched = len(run.pages)
    run.bytes_fetched = int(prepared.get("bytes_fetched") or 0)
    if not run.pages:
        run.status = "failed"
        run.error = "The leaflet has no readable text"
        run.finished_at = datetime.now(UTC)
        return None
    if any(page.get("vision_urls") for page in run.pages if isinstance(page, dict)):
        return "transcribe"
    run.input_hash = _hash_pages(run.pages)
    run.status = "extracting"
    session.flush()
    return "extract"


def transcribe_leaflet_run(
    session: Session,
    run: OrgEnrichmentRun,
    *,
    transcribe: TranscribeFn | None,
) -> str:
    """Fill page text from the vision model, then queue extract."""
    from app.services.enrichment.run import _hash_pages, _openrouter_settings

    settings = load_settings(session)
    if transcribe is None:
        _model_name, fallbacks, deny = _openrouter_settings(session)
    else:
        fallbacks, deny = [], True
    pages, cost, model = transcribe_pages(
        list(run.pages or []),
        model_name=resolved_leaflet_model(settings.leaflet_model),
        fallback_models=fallbacks,
        deny_data_collection=deny,
        complete=transcribe,
    )
    run.pages = pages
    run.cost_usd = Decimal(str(run.cost_usd or 0)) + cost
    if model:
        run.model = model
    run.input_hash = _hash_pages(pages)
    run.status = "extracting"
    session.flush()
    return "extract"


def _prepare_leaflet(run: OrgEnrichmentRun) -> dict[str, Any]:
    return read_leaflets(run.org_id, list(run.leaflet_items or []))
