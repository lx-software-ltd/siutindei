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
        from app.services.enrichment.leaflet_objects import release_leaflet_run

        release_leaflet_run(run)
        run.status = "failed"
        run.error = "The leaflet has no readable text"
        run.finished_at = datetime.now(UTC)
        return None
    if any(
        isinstance(page, dict) and (page.get("vision_keys") or page.get("vision_urls"))
        for page in run.pages
    ):
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
) -> str | None:
    """Fill page text from the vision model, then queue extract."""
    from app.services.enrichment.leaflet_objects import (
        release_leaflet_run,
        release_rasters,
    )
    from app.services.enrichment.run import _hash_pages, _openrouter_settings
    from app.services.enrichment.store import month_spend

    settings = load_settings(session)
    if month_spend(session) >= Decimal(str(settings.monthly_cost_limit_usd)):
        release_leaflet_run(run)
        run.status = "failed"
        run.error = "The monthly enrichment budget is spent"
        run.finished_at = datetime.now(UTC)
        session.flush()
        return None
    deny = True
    if transcribe is None:
        _model_name, _fallbacks, deny = _openrouter_settings(session)
    stored_pages = list(run.pages or [])
    pages, cost, model = transcribe_pages(
        stored_pages,
        model_name=resolved_leaflet_model(settings.leaflet_model),
        fallback_models=[],
        deny_data_collection=deny,
        complete=transcribe,
    )
    run.pages = pages
    release_rasters(run.org_id, stored_pages)
    run.cost_usd = Decimal(str(run.cost_usd or 0)) + cost
    if model:
        run.model = model
    run.input_hash = _hash_pages(pages)
    run.status = "extracting"
    session.flush()
    return "extract"


def _prepare_leaflet(run: OrgEnrichmentRun) -> dict[str, Any]:
    return read_leaflets(run.org_id, list(run.leaflet_items or []))
